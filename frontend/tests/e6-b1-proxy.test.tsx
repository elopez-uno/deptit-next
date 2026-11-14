// @vitest-environment node
// Etapa 6A-B1: BFF same-origin (CSRF, allowlist, sin query strings, cookie), origen del cliente para el límite de
// login, health check mínimo y cabeceras de seguridad (docs/ETAPA6_6AB1_PRODUCTIVE_SOFTWARE_HARDENING.md).
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { clientIp, forwardToBackend, sameOrigin, trustedProxyHops } from "@/lib/backend-proxy";
import { contentSecurityPolicy, securityHeaders } from "@/lib/security-headers";
import { GET as health } from "@/app/api/backend-health/route";
import { POST as authPost } from "@/app/api/auth/[...path]/route";
import nextConfig from "../next.config";

const ORIGEN = "http://deptit.local";

function req(path: string, init: { method?: string; headers?: Record<string, string>; body?: string } = {}) {
  return new NextRequest(`${ORIGEN}${path}`, {
    method: init.method ?? "GET",
    headers: { host: "deptit.local", ...(init.headers ?? {}) },
    body: init.body,
  });
}

const mismoOrigen = { origin: ORIGEN, "sec-fetch-site": "same-origin" };
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => {
  vi.unstubAllGlobals();
  vi.unstubAllEnvs();
});

describe("sameOrigin (CSRF del BFF)", () => {
  it("acepta solo el mismo origen", () => {
    expect(sameOrigin(req("/api/x", { method: "POST", headers: mismoOrigen }))).toBe(true);
    expect(sameOrigin(req("/api/x", { method: "POST", headers: { origin: ORIGEN } }))).toBe(true);
  });
  it("rechaza cross-site, Origin ausente, inválido o de otro host", () => {
    expect(sameOrigin(req("/api/x", { method: "POST", headers: { origin: ORIGEN, "sec-fetch-site": "cross-site" } }))).toBe(false);
    expect(sameOrigin(req("/api/x", { method: "POST", headers: { origin: ORIGEN, "sec-fetch-site": "same-site" } }))).toBe(false);
    expect(sameOrigin(req("/api/x", { method: "POST" }))).toBe(false);
    expect(sameOrigin(req("/api/x", { method: "POST", headers: { origin: "https://evil.example" } }))).toBe(false);
    expect(sameOrigin(req("/api/x", { method: "POST", headers: { origin: "no es una url" } }))).toBe(false);
    expect(sameOrigin(req("/api/x", { method: "POST", headers: { origin: "http://deptit.local.evil.example" } }))).toBe(false);
  });
});

describe("forwardToBackend", () => {
  const ALLOWED = { "": ["GET"], alta: ["POST"] } as const;

  it("ruta o método fuera de la allowlist: 404 sin tocar el backend", async () => {
    const r1 = await forwardToBackend(req("/api/m/otra"), "m", ["otra"], ALLOWED);
    const r2 = await forwardToBackend(req("/api/m", { method: "POST", headers: mismoOrigen }), "m", undefined, ALLOWED);
    expect([r1.status, r2.status]).toEqual([404, 404]);
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("escritura cross-site: 403 CSRF sin tocar el backend", async () => {
    const r = await forwardToBackend(
      req("/api/m/alta", { method: "POST", headers: { origin: "https://evil.example", cookie: "deptit_session=t" }, body: "{}" }),
      "m", ["alta"], ALLOWED);
    expect(r.status).toBe(403);
    expect((await r.json()).error.code).toBe("CSRF");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("escritura same-origin: cabecera propia, cookie, sin query string ni cabeceras del navegador", async () => {
    await forwardToBackend(
      req("/api/m/alta?institucion_id=9", {
        method: "POST",
        headers: { ...mismoOrigen, cookie: "deptit_session=t", "x-deptit-client-ip": "1.2.3.4", "x-forwarded-for": "1.2.3.4" },
        body: "{}",
      }),
      "m", ["alta"], ALLOWED);
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("http://127.0.0.1:8001/m/alta");
    expect(init.headers).toEqual({ accept: "application/json", cookie: "deptit_session=t", "content-type": "application/json", "x-deptit-request": "1" });
    expect(init.redirect).toBe("manual");
  });

  it("DEPTIT_BACKEND_URL configurable (server-only)", async () => {
    vi.stubEnv("DEPTIT_BACKEND_URL", "http://127.0.0.1:9101");
    await forwardToBackend(req("/api/m"), "m", undefined, ALLOWED);
    expect(fetchMock.mock.calls[0][0]).toBe("http://127.0.0.1:9101/m");
  });

  it("backend caído: 503 genérico", async () => {
    fetchMock.mockRejectedValueOnce(new Error("ECONNREFUSED 127.0.0.1:8001"));
    const r = await forwardToBackend(req("/api/m"), "m", undefined, ALLOWED);
    expect(r.status).toBe(503);
    expect(await r.text()).not.toContain("ECONNREFUSED");
  });
});

describe("origen del cliente (límite de login por IP)", () => {
  it("sin proxy confiable (default 0) nunca se deriva: X-Forwarded-For es falsificable", () => {
    expect(trustedProxyHops()).toBe(0);
    expect(clientIp(req("/api/auth/login", { headers: { "x-forwarded-for": "203.0.113.7" } }))).toBeNull();
  });
  it("con 1 proxy confiable se toma la entrada que agregó el proxy (la última)", () => {
    const r = req("/api/auth/login", { headers: { "x-forwarded-for": "6.6.6.6, 203.0.113.7" } });
    expect(clientIp(r, 1)).toBe("203.0.113.7");
    expect(clientIp(r, 2)).toBe("6.6.6.6");
    expect(clientIp(req("/x", { headers: { "x-forwarded-for": "basura" } }), 1)).toBeNull();
    expect(clientIp(req("/x"), 1)).toBeNull();
    expect(clientIp(req("/x", { headers: { "x-forwarded-for": "2001:db8::1" } }), 1)).toBe("2001:db8::1");
  });
  it("valores inválidos de DEPTIT_TRUSTED_PROXY_HOPS equivalen a 0", () => {
    for (const v of ["-1", "x", "99", ""]) {
      vi.stubEnv("DEPTIT_TRUSTED_PROXY_HOPS", v);
      expect(trustedProxyHops()).toBe(0);
    }
  });
  it("el proxy de login reenvía el origen solo si es confiable y nunca el del navegador", async () => {
    const ctx = { params: Promise.resolve({ path: ["login"] }) } as never;
    const body = JSON.stringify({ email: "a@b.c", password: "x" });
    const headers = { ...mismoOrigen, "x-forwarded-for": "203.0.113.7", "x-deptit-client-ip": "9.9.9.9" };
    await authPost(req("/api/auth/login", { method: "POST", headers, body }), ctx);
    expect(fetchMock.mock.calls[0][1].headers["x-deptit-client-ip"]).toBeUndefined();
    vi.stubEnv("DEPTIT_TRUSTED_PROXY_HOPS", "1");
    await authPost(req("/api/auth/login", { method: "POST", headers, body }), ctx);
    expect(fetchMock.mock.calls[1][1].headers["x-deptit-client-ip"]).toBe("203.0.113.7");
  });
});

describe("health check público", () => {
  it("no reexpone base, rol ni versiones del backend", async () => {
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({ status: "ok", database: "deptit_next_dev", db_user: "deptit_next_app" }), { status: 200 }));
    const r = await health();
    expect(await r.json()).toEqual({ status: "ok", service: "deptit-next-frontend" });
    fetchMock.mockRejectedValueOnce(new Error("down"));
    const r2 = await health();
    expect(r2.status).toBe(503);
    expect(await r2.json()).toEqual({ status: "error", service: "deptit-next-frontend" });
  });
});

describe("cabeceras de seguridad", () => {
  it("CSP productiva sin unsafe-eval, sin embebido y solo mismo origen", () => {
    const csp = contentSecurityPolicy(false);
    expect(csp).not.toContain("unsafe-eval");
    for (const d of ["default-src 'self'", "frame-ancestors 'none'", "object-src 'none'", "base-uri 'self'", "connect-src 'self'", "form-action 'self'"]) {
      expect(csp).toContain(d);
    }
    expect(contentSecurityPolicy(true)).toContain("'unsafe-eval'");
  });
  it("next.config aplica las cabeceras a todas las rutas y no anuncia X-Powered-By", async () => {
    const reglas = await nextConfig.headers!();
    expect(reglas).toHaveLength(1);
    expect(reglas[0].source).toBe("/:path*");
    const claves = reglas[0].headers.map((h) => h.key);
    expect(claves).toEqual(securityHeaders(false).map((h) => h.key));
    expect(claves).toEqual(expect.arrayContaining(["Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "X-Frame-Options", "Permissions-Policy"]));
    expect(claves).not.toContain("Strict-Transport-Security"); // HSTS: reverse proxy (6A-B4)
    expect(nextConfig.poweredByHeader).toBe(false);
  });
});

describe("configuración server-only y build reproducible", () => {
  const archivos = (dir: string): string[] =>
    readdirSync(dir).flatMap((n) => (statSync(join(dir, n)).isDirectory() ? archivos(join(dir, n)) : [join(dir, n)]));
  const fuentes = archivos(join(__dirname, "..", "src")).filter((f) => /\.(ts|tsx|css)$/.test(f));
  it("sin NEXT_PUBLIC_*, sin Google Fonts y sin backend fuera de lib/backend-proxy", () => {
    for (const f of fuentes) {
      const t = readFileSync(f, "utf8");
      expect(t, f).not.toMatch(/NEXT_PUBLIC_/);
      expect(t, f).not.toMatch(/next\/font\/google|fonts\.googleapis|fonts\.gstatic/);
      if (!f.endsWith("backend-proxy.ts")) expect(t, f).not.toMatch(/127\.0\.0\.1|localhost:8001|DEPTIT_BACKEND_URL/);
    }
  });
});
