// 6A-B4 (R-B3-10): antes del login el branding es neutro (ninguna universidad); dentro del sistema el encabezado es la
// institución ACTIVA que entrega el backend y se actualiza al cambiar de contexto.
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Session } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/inicio-module", () => ({ InicioModule: () => <p>Módulo Inicio</p> }));
let onChangedRef: ((s: Session) => void) | null = null;
vi.mock("@/components/context-switcher", () => ({
  ContextSwitcher: ({ onChanged }: { onChanged: (s: Session) => void }) => {
    onChangedRef = onChanged;
    return <span>selector</span>;
  },
}));

import { AppShell } from "@/components/app-shell";
import { metadata } from "@/app/layout";
import LoginPage from "@/app/login/page";

const UNO = "Universidad Nacional del Oeste";
const PRUEBA = "Universidad de Prueba";

function sesion(encabezado: string, inst: { id: number; nombre: string } | null): Session {
  return {
    usuario: { id: 1, nombre: "Super", email: "s@test.local", rol: "superadmin", rol_original: null,
      modo_solo_lectura_comercial: false, es_superadmin: true },
    acceso: "normal",
    // pertenencia a UNO aunque opere en otra institución: el encabezado no la usa
    pertenencia: { institucion: { id: 1, nombre: UNO }, departamento: null },
    contexto: { institucion_encabezado: encabezado, institucion: inst, departamento: inst ? { id: 1, nombre: "Dep" } : null,
      vista: inst ? "departamento" : "sin_ambito", problema: null, seleccionable: true },
    modulos: [{ clave: "inicio", nombre: "🏠 Inicio", puede_escribir: false, puede_borrar: false }],
    sesion: { inactividad_max_segundos: 3600, expira_por_inactividad_en: 3600, expira_absoluta_en: 28800 },
  };
}

let actual: Session;
beforeEach(() => {
  onChangedRef = null;
  actual = sesion(UNO, { id: 1, nombre: UNO });
  vi.stubGlobal("fetch", async (url: string) => {
    if (url === "/api/auth/me") return new Response(JSON.stringify(actual), { status: 200 });
    if (url === "/api/contexto/periodo") return new Response(JSON.stringify({ aviso: null }), { status: 200 });
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const LOGO = "/branding/deptit-logo-completo.png";
const ICONO = "/branding/deptit-icono.png";
const PUBLIC_DIR = join(__dirname, "..", "public");
const SRC_DIR = join(__dirname, "..", "src");

const srcs = (root: ParentNode) => Array.from(root.querySelectorAll("img")).map((i) => i.getAttribute("src") ?? "");

test("metadata neutra: DEPTIT sin institución fija, es-AR e isotipo como favicon", () => {
  expect(metadata.title).toBe("DEPTIT — Gestión académica");
  expect(metadata.applicationName).toBe("DEPTIT");
  expect(JSON.stringify(metadata)).not.toMatch(/Universidad|UNO|DEPTIT NEXT/);
  expect(JSON.stringify(metadata.icons)).toContain(ICONO);
  expect(readFileSync(join(SRC_DIR, "app", "layout.tsx"), "utf-8")).toContain('lang="es-AR"');
});

test("login neutro: logo completo DEPTIT, ninguna universidad ni logo institucional", () => {
  render(<LoginPage />);
  expect(document.body.textContent).not.toMatch(/Universidad|Oeste|DEPTIT NEXT/);
  const imgs = srcs(document.body);
  expect(imgs.length).toBeGreaterThan(0);
  expect(imgs.every((s) => s === LOGO)).toBe(true);
  expect(screen.getAllByAltText("DEPTIT — Gestión académica").length).toBeGreaterThan(0);
  // el logo ya contiene el nombre: no se repite "DEPTIT" como texto en el login
  expect(document.body.textContent).not.toMatch(/DEPTIT/);
});

test("sidebar usa el isotipo DEPTIT (no el logo completo) y ninguna institución fija", async () => {
  actual = sesion("", null);
  render(<AppShell />);
  await screen.findByText("Módulo Inicio");
  const aside = document.querySelector("aside")!;
  expect(srcs(aside)).toEqual([ICONO]);
  expect(document.body.textContent).not.toMatch(/Universidad|DEPTIT NEXT/);
});

test("assets DEPTIT existen en public/ (servibles) y no queda branding UNO en el código", () => {
  for (const asset of [LOGO, ICONO]) {
    const file = join(PUBLIC_DIR, asset);
    expect(existsSync(file), asset).toBe(true);
    // firma PNG
    expect(readFileSync(file).subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  }
  expect(existsSync(join(PUBLIC_DIR, "uno-logo-web.png"))).toBe(false);
  const walk = (dir: string): string[] =>
    readdirSync(dir, { withFileTypes: true }).flatMap((e) =>
      e.isDirectory() ? walk(join(dir, e.name)) : /\.(tsx?|css)$/.test(e.name) ? [join(dir, e.name)] : [],
    );
  for (const f of walk(SRC_DIR)) {
    const txt = readFileSync(f, "utf-8");
    expect(txt, f).not.toMatch(/Universidad Nacional del Oeste|uno-logo|UnoLogo|#009cd1/i);
  }
});

test("encabezado = institución activa; UNO → Prueba → UNO sin arrastre; sin institución activa, ningún nombre", async () => {
  render(<AppShell />);
  await screen.findByText("Módulo Inicio");
  const encabezado = () => screen.getByRole("banner").querySelector("p")?.textContent ?? "";
  // como el backend real: tras PUT /auth/context, /auth/me devuelve la sesión del contexto nuevo
  const cambiar = (s: Session) => {
    actual = s;
    onChangedRef!(s);
  };
  expect(encabezado()).toBe(UNO);
  cambiar(sesion(PRUEBA, { id: 846, nombre: PRUEBA }));
  await waitFor(() => expect(encabezado()).toBe(PRUEBA));
  expect(screen.getByRole("banner").textContent).not.toContain(UNO);
  cambiar(sesion(UNO, { id: 1, nombre: UNO }));
  await waitFor(() => expect(encabezado()).toBe(UNO));
  cambiar(sesion("", null));
  await waitFor(() => expect(encabezado()).toBe(""));
  expect(screen.getByRole("banner").textContent).not.toMatch(/Universidad/);
});
