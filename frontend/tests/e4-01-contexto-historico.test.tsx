// E4-01 (D-AN9): aviso global "🕰️ Contexto histórico activo" en el shell. Los módulos se reemplazan por stubs para
// aislar el shell (ningún módulo tiene lógica paralela del aviso). El texto es el que entrega el backend.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Session } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/inicio-module", () => ({ InicioModule: () => <p>Módulo Inicio</p> }));
vi.mock("@/components/docentes-module", () => ({ DocentesModule: () => <p>Módulo Docentes</p> }));
vi.mock("@/components/periodos-module", () => ({ PeriodosModule: () => <p>Módulo Períodos</p> }));
let onChangedRef: ((s: Session) => void) | null = null;
vi.mock("@/components/context-switcher", () => ({
  ContextSwitcher: ({ onChanged }: { onChanged: (s: Session) => void }) => {
    onChangedRef = onChanged;
    return <span>selector</span>;
  },
}));

import { AppShell } from "@/components/app-shell";
import { LoginForm } from "@/app/login/login-form";

const TEXTO =
  "🕰️ **Contexto histórico activo: 2026-1** (2026-03-01 al 2026-07-31). Las vistas periodizadas muestran la foto exacta " +
  "de cómo estaba el sistema al finalizar el último día de este período. El último período cronológico sigue siendo " +
  "**2026-2**. La operatoria académica normal de Comisiones permanece protegida/bloqueada para el período anterior; " +
  "solo siguen disponibles las correcciones históricas ya previstas por la app.";

const SESSION: Session = {
  usuario: { id: 1, nombre: "Usuaria Test", email: "u@test.local", rol: "usuario_departamento", rol_original: null,
    modo_solo_lectura_comercial: false, es_superadmin: false },
  acceso: "normal",
  pertenencia: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep 1" } },
  contexto: { institucion_encabezado: "Inst", institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep 1" },
    vista: "departamento", problema: null, seleccionable: false },
  modulos: [
    { clave: "inicio", nombre: "🏠 Inicio", puede_escribir: false, puede_borrar: false },
    { clave: "docentes", nombre: "👨‍🏫 Docentes", puede_escribir: true, puede_borrar: false },
    { clave: "periodos", nombre: "🗓️ Períodos", puede_escribir: true, puede_borrar: false },
  ],
  sesion: { inactividad_max_segundos: 3600, expira_por_inactividad_en: 3600, expira_absoluta_en: 28800 },
};

let aviso: { texto: string } | null;
let falla: boolean;
let llamadas: string[];

beforeEach(() => {
  aviso = null;
  falla = false;
  llamadas = [];
  onChangedRef = null;
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    llamadas.push(`${init?.method ?? "GET"} ${url}`);
    if (url === "/api/auth/me") return new Response(JSON.stringify(SESSION), { status: 200 });
    if (url === "/api/contexto/periodo") {
      if (falla) return new Response(JSON.stringify({ error: { code: "DB_READ", message: "x" } }), { status: 503 });
      return new Response(JSON.stringify({ aviso }), { status: 200 });
    }
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const contextoCalls = () => llamadas.filter((l) => l === "GET /api/contexto/periodo").length;

async function abrirShell() {
  render(<AppShell />);
  await screen.findByText("Módulo Inicio");
  await waitFor(() => expect(contextoCalls()).toBeGreaterThan(0));
}

test("visible cuando el backend informa contexto histórico, con negritas y una sola vez", async () => {
  aviso = { texto: TEXTO };
  await abrirShell();
  const banner = await screen.findByTestId("aviso-contexto-historico");
  expect(banner.textContent).toBe(TEXTO.replaceAll("**", ""));
  expect(banner.querySelectorAll("strong")[0].textContent).toBe("Contexto histórico activo: 2026-1");
  expect(banner.querySelectorAll("strong")[1].textContent).toBe("2026-2");
  expect(screen.getAllByTestId("aviso-contexto-historico")).toHaveLength(1);
});

test("oculto cuando el contexto no es histórico", async () => {
  await abrirShell();
  expect(screen.queryByTestId("aviso-contexto-historico")).toBeNull();
});

test("si la lectura del aviso falla, no se muestra y el shell sigue operativo", async () => {
  aviso = { texto: TEXTO };
  falla = true;
  await abrirShell();
  expect(screen.queryByTestId("aviso-contexto-historico")).toBeNull();
  expect(screen.getByText("Módulo Inicio")).toBeTruthy();
});

test("no aparece en login (no se pide el aviso)", async () => {
  aviso = { texto: TEXTO };
  render(<LoginForm />);
  await new Promise((r) => setTimeout(r, 20));
  expect(screen.queryByTestId("aviso-contexto-historico")).toBeNull();
  expect(contextoCalls()).toBe(0);
});

test("al navegar entre módulos se recalcula, se conserva y no se duplica", async () => {
  aviso = { texto: TEXTO };
  await abrirShell();
  await screen.findByTestId("aviso-contexto-historico");
  const antes = contextoCalls();
  fireEvent.click(screen.getAllByRole("button", { name: /Docentes/ })[0]);
  await screen.findByText("Módulo Docentes");
  await waitFor(() => expect(contextoCalls()).toBeGreaterThan(antes));
  expect(screen.getAllByTestId("aviso-contexto-historico")).toHaveLength(1);
  // el backend deja de informar contexto histórico (p. ej. se volvió al período actual): al navegar desaparece
  aviso = null;
  const antes2 = contextoCalls();
  fireEvent.click(screen.getAllByRole("button", { name: /Períodos/ })[0]);
  await screen.findByText("Módulo Períodos");
  await waitFor(() => expect(contextoCalls()).toBeGreaterThan(antes2));
  await waitFor(() => expect(screen.queryByTestId("aviso-contexto-historico")).toBeNull());
});

test("un cambio legítimo de contexto recalcula el aviso", async () => {
  await abrirShell();
  expect(screen.queryByTestId("aviso-contexto-historico")).toBeNull();
  aviso = { texto: TEXTO };
  const antes = contextoCalls();
  onChangedRef!({ ...SESSION, contexto: { ...SESSION.contexto, departamento: { id: 2, nombre: "Dep 2" } } });
  await waitFor(() => expect(contextoCalls()).toBeGreaterThan(antes));
  expect(await screen.findByTestId("aviso-contexto-historico")).toBeTruthy();
});

test("el cliente no envía parámetros: el aviso lo decide la sesión", async () => {
  await abrirShell();
  expect(llamadas.filter((l) => l.includes("/api/contexto")).every((l) => l === "GET /api/contexto/periodo")).toBe(true);
});
