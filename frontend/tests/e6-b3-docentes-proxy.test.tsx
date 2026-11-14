// @vitest-environment node
// 6A-B3 (último ajuste): el proxy REAL de Docentes (route.ts) reenvía "designacion/acto-nuevo" como multipart en
// streaming (mismo transporte que la carga integral) y mantiene CSRF same-origin, tipo multipart y método POST.
import { NextRequest } from "next/server";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { GET, POST } from "@/app/api/docentes/[[...path]]/route";

const ORIGEN = "http://deptit.local";
const RUTA = ["designacion", "acto-nuevo"];
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const pedido = (contentType: string, origin = ORIGEN, method = "POST") =>
  new NextRequest(`${ORIGEN}/api/docentes/${RUTA.join("/")}`, {
    method,
    headers: { host: "deptit.local", origin, "sec-fetch-site": "same-origin", "content-type": contentType },
    body: method === "POST" ? "--b\r\nContent-Disposition: form-data; name=\"datos\"\r\n\r\n{}\r\n--b--\r\n" : undefined,
  });
const ctx = { params: Promise.resolve({ path: RUTA }) } as never;

test("multipart se reenvía al backend con su boundary y la cabecera del proxy", async () => {
  const r = await POST(pedido("multipart/form-data; boundary=b"), ctx);
  expect(r.status).toBe(200);
  const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit & { headers: Record<string, string> }];
  expect(url).toMatch(/\/docentes\/designacion\/acto-nuevo$/);
  expect(init.headers["content-type"]).toBe("multipart/form-data; boundary=b");
  expect(init.headers["x-deptit-request"]).toBe("1");
});

test("JSON (415), otro origen (403) y GET (405) no llegan al backend", async () => {
  expect((await POST(pedido("application/json"), ctx)).status).toBe(415);
  expect((await POST(pedido("multipart/form-data; boundary=b", "https://evil.example"), ctx)).status).toBe(403);
  expect((await GET(pedido("multipart/form-data; boundary=b", ORIGEN, "GET"), ctx)).status).toBe(405);
  expect(fetchMock).not.toHaveBeenCalled();
});
