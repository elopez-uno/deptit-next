// Flujo REAL del módulo Inicio (InicioModule completo) con las respuestas reales de GET /inicio para UNO (fixtures
// generadas por backend/tests/tools_inicio_frontend_fixtures.py con ROLLBACK; nombres, CUIL y correos anonimizados).
// La navegación usa el callback del shell; "🔄 Actualizar tablero" solo vuelve a pedir el tablero (D-AN3); la única
// descarga es el Excel de "Próximos vencimientos" (D-AN6). vega-embed se simula para comprobar las especificaciones.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { InicioModule } from "@/components/inicio-module";
import type { Inicio, Tablero } from "@/lib/inicio";

const specs: Record<string, unknown>[] = [];
vi.mock("@/lib/vega", () => ({
  cargarEmbed: async () => async (_el: HTMLElement, spec: Record<string, unknown>) => {
    specs.push(spec);
    return { finalize: () => {} };
  },
}));

type Fx = Record<"dep" | "lector" | "dep9" | "dep11" | "sin_periodo" | "coord", Inicio>;
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "inicio_uno.json"), "utf8"));

let respuesta: Inicio;
let llamadas: { url: string; method: string }[] = [];
let descargas: string[] = [];
let navegado: string[] = [];

beforeEach(() => {
  respuesta = fx.dep;
  llamadas = [];
  descargas = [];
  navegado = [];
  specs.length = 0;
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    descargas.push(this.download);
  });
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    llamadas.push({ url, method });
    expect(url.startsWith("/api/inicio")).toBe(true);
    if (url === "/api/inicio" && method === "GET") return new Response(JSON.stringify(respuesta), { status: 200 });
    if (url === "/api/inicio/descargas/vencimientos" && method === "POST") {
      const nombre = "Inicio_20261026_103000.xlsx";
      return new Response(new Blob(["PK"]), { status: 200, headers: { "content-disposition": `attachment; filename="${nombre}"; filename*=UTF-8''${nombre}` } });
    }
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function abrir(r: Inicio = fx.dep) {
  respuesta = r;
  render(<InicioModule onAuthError={() => {}} onNavigate={(c) => navegado.push(c)} />);
  await screen.findByText(r.titulo);
}

const tablero = (r: Inicio) => (r as Extract<Inicio, { estado: "tablero" }>).tablero;

test("tablero completo: encabezado, 5 tarjetas, 2 listas, acciones, 6 controles, 11 indicadores, 2 gráficos, vencimientos y ayuda", async () => {
  await abrir();
  const t = tablero(fx.dep);
  expect(screen.getByText("Inicio — Departamento de Informática e Ingeniería")).toBeTruthy();
  expect(screen.getByText("Período actual:")).toBeTruthy();
  expect(screen.getByRole("progressbar", { name: "Avance calendario del período" })).toBeTruthy();
  expect(screen.getByText(t.periodo.caption_progreso!)).toBeTruthy();
  const metricas = screen.getAllByTestId("metrica").map((m) => m.querySelector("p")!.textContent);
  expect(metricas).toEqual([
    "Docentes activos", "No docentes activos", "Comisiones abiertas", "Comisiones sin cubrir", "Alertas críticas",
    "Horas de designación · total", "Horas frente a comisión", "Horas no lectivas", "Horas investigación + extensión",
    "Horas funciones no docentes", "Cobertura de comisiones", "Comisiones cubiertas", "Docentes por comisión",
    "Productividad promedio", "Horas todavía disponibles", "Alumnos por docente",
  ]);
  expect(screen.getByText(/^🧭 Funciones no docentes del período \(6 designación\/es · 6 persona\/s\)$/)).toBeTruthy();
  expect(screen.getByText(/^👨‍🏫 Designaciones docentes del período/)).toBeTruthy();
  expect(screen.getByText("🟠 1 docente sin carga")).toBeTruthy();
  const controles = t.salud!.controles.map((c) => c.titulo);
  expect(controles).toHaveLength(6);
  for (const c of controles) expect(screen.getByText(c)).toBeTruthy();
  expect(screen.getByText("Estado general del período:", { exact: false })).toBeTruthy();
  expect(screen.getByRole("progressbar", { name: "Estado general del período" }).getAttribute("aria-valuenow")).toBe(String(t.salud!.porcentaje));
  await waitFor(() => expect(specs).toHaveLength(2));
  expect(specs.map((s) => s.mark)).toEqual([{ type: "bar", tooltip: true }, { type: "bar", tooltip: true }]);
  expect((specs[0].encoding as { y: { sort: string } }).y.sort).toBe("-x");
  expect(((specs[1].data as { values: { Concepto: string }[] }).values).map((v) => v.Concepto)).toEqual([
    "Horas contratadas", "Comisiones (lectivas)", "Horas no lectivas", "Investigación", "Extensión", "Funciones no docentes", "Horas disponibles",
  ]);
  expect(screen.getByText("No hay designaciones activas con vencimiento previsto dentro de los próximos 30 días.")).toBeTruthy();
  expect(screen.queryByText("📥 Descargar tabla en Excel")).toBeNull();
  expect(screen.getByText("▶️ Ayuda y flujo correcto de carga")).toBeTruthy();
  // sin selector de período, sin pestañas, sin acciones mutantes
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(screen.queryByRole("tab")).toBeNull();
  expect(screen.queryByText(/Guardar|Eliminar|Crear/)).toBeNull();
  expect(llamadas).toEqual([{ url: "/api/inicio", method: "GET" }]);
});

test("navegación: los botones certificados llevan a su módulo por el shell", async () => {
  await abrir();
  fireEvent.click(screen.getByRole("button", { name: "Ver docentes" }));
  fireEvent.click(screen.getByRole("button", { name: "Ver diagnóstico completo" }));
  expect(navegado).toEqual(["docentes", "analisis"]);
});

test("🔄 Actualizar tablero: habilitado también para solo lectura y solo vuelve a pedir el tablero", async () => {
  await abrir(fx.lector);
  const boton = screen.getByRole("button", { name: "🔄 Actualizar tablero" }) as HTMLButtonElement;
  expect(boton.disabled).toBe(false);
  expect(screen.getByText(tablero(fx.lector).periodo.actualizar.caption)).toBeTruthy();
  fireEvent.click(boton);
  await waitFor(() => expect(llamadas).toHaveLength(2));
  expect(llamadas.every((l) => l.url === "/api/inicio" && l.method === "GET")).toBe(true);
});

test("superposiciones y exceso (dep. 9): tablas de detalle sin Excel y sin columnas de materias (anomalía certificada)", async () => {
  await abrir(fx.dep9);
  const sup = screen.getByText("🔴 Superposiciones horarias — 25 casos").closest("details")!;
  const cols = within(sup).getAllByRole("columnheader").map((c) => c.textContent);
  expect(cols).toEqual(["Docente", "CUIL", "Día", "Comisión 1", "Horario 1", "Comisión 2", "Horario 2"]);
  expect(within(sup).queryByText(/Excel/)).toBeNull();
  expect(screen.getByText("🔴 Exceso de dedicación — 16 casos")).toBeTruthy();
});

test("período abierto vencido (dep. 11): barra completa y gráficos vacíos", async () => {
  await abrir(fx.dep11);
  expect(screen.getByText("El período ya alcanzó su fecha de finalización prevista.")).toBeTruthy();
  expect(screen.getAllByText("Todavía no hay datos para graficar.")).toHaveLength(2);
  expect(screen.getByText("No hay acciones prioritarias pendientes con las reglas actuales del sistema.")).toBeTruthy();
  expect(specs).toHaveLength(0);
});

test("sin período abierto: aviso, botón a Períodos y ayuda abierta", async () => {
  await abrir(fx.sin_periodo);
  expect(screen.getByText("No hay un período abierto. Para comenzar a operar, creá o abrí el período académico correspondiente.")).toBeTruthy();
  expect((screen.getByText("▶️ Ayuda y flujo recomendado").closest("details") as HTMLDetailsElement).open).toBe(true);
  fireEvent.click(screen.getByRole("button", { name: "🗓️ Ir a Períodos" }));
  expect(navegado).toEqual(["periodos"]);
  expect(screen.queryByText("🔄 Actualizar tablero")).toBeNull();
});

test("coordinador sin departamento: mensaje institucional y acceso a Consolidado (D-AN5), sin tablero", async () => {
  await abrir(fx.coord);
  expect(screen.getByText("Inicio — Departamento correspondiente")).toBeTruthy();
  expect(screen.getByText(/Estás en el ámbito institucional/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "🏛️ Ir al consolidado institucional" }));
  expect(navegado).toEqual(["consolidado"]);
  expect(screen.queryByText("Situación del período")).toBeNull();
});

test("Próximos vencimientos con filas: tabla visible, Excel bajo demanda y 'Ver todos los vencimientos'", async () => {
  const base = tablero(fx.dep);
  const filas = Array.from({ length: 8 }, (_, i) => [`ZZNEXT Persona V${i}`, "JTP · Simple · Interina", `0${i + 1}/11/2026`, i + 6]);
  const t: Tablero = {
    ...base,
    vencimientos: { titulo: "Próximos vencimientos", vacio: null, excel: true, tabla: { columnas: ["Docente", "Designación", "Vencimiento", "Días"], filas }, boton: { label: "Ver todos los vencimientos", destino: "designaciones", primario: false } },
  };
  await abrir({ ...fx.dep, tablero: t } as Inicio);
  expect(screen.getByText("ZZNEXT Persona V7")).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: "📥 Descargar tabla en Excel" }));
  await waitFor(() => expect(descargas).toEqual(["Inicio_20261026_103000.xlsx"]));
  expect(llamadas.at(-1)).toEqual({ url: "/api/inicio/descargas/vencimientos", method: "POST" });
  fireEvent.click(screen.getByRole("button", { name: "Ver todos los vencimientos" }));
  expect(navegado).toEqual(["designaciones"]);
});
