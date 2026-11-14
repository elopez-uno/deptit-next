// Flujo REAL del módulo Análisis — incluye Productividad (AnalisisModule completo) con las respuestas reales de la API
// de NEXT para UNO, departamento 1 (fixtures generadas por backend/tests/tools_analisis_frontend_fixtures.py con
// ROLLBACK; nombres, CUIL y correos anonimizados). Las escrituras y descargas no llegan a ningún backend: se verifica el
// cuerpo exacto que enviaría la pantalla. vega-embed se simula para comprobar las especificaciones Vega-Lite (D-AM10).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { AnalisisModule } from "@/components/analisis-module";
import type { Comparacion, Overview, Periodo } from "@/lib/analisis";

const specs: Record<string, unknown>[] = [];
vi.mock("@/lib/vega", () => ({
  cargarEmbed: async () => async (_el: HTMLElement, spec: Record<string, unknown>) => {
    specs.push(spec);
    return { finalize: () => {} };
  },
}));

type Fx = { overview: Overview; super: Overview; lector: Overview; "periodo_2026-2": Periodo; "periodo_2026-1": Periodo; comparacion: Comparacion };
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "analisis_uno.json"), "utf8"));

let overview: Overview;
let envios: { path: string; body: unknown }[] = [];
let descargas: string[] = [];

beforeEach(() => {
  overview = fx.overview;
  envios = [];
  descargas = [];
  specs.length = 0;
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    descargas.push(this.download);
  });
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
    expect(url.startsWith("/api/analisis")).toBe(true); // ninguna llamada a servicios externos (D-AM9)
    if (url === "/api/analisis" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/analisis/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    envios.push({ path, body });
    if (path === "periodo") return ok(fx[`periodo_${body.periodo}` as "periodo_2026-2"]);
    if (path === "comparacion") return ok(fx.comparacion);
    if (path === "porcentaje") return ok({ mensaje: "Porcentaje guardado: 45 %. Se recalculará la productividad del departamento.", tono: "success" });
    if (path.startsWith("descargas/")) {
      const nombre = { "descargas/word": "informe_movimiento_docente_2026-2.docx", "descargas/indicador": "movimiento_altas_designaciones_2026-2.csv", "descargas/alertas": "alertas_x_2026-2.csv", "descargas/prompt": "prompt_analisis_ia_2026-2.txt" }[path];
      return new Response(new Blob(["x"]), { status: 200, headers: { "content-disposition": `attachment; filename="${nombre}"; filename*=UTF-8''${nombre}` } });
    }
    return ok({ error: { code: "NOT_FOUND", message: "no" } }, 404);
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function abrir(o: Overview = fx.overview) {
  overview = o;
  render(<AnalisisModule onAuthError={() => {}} />);
  await screen.findByRole("tab", { name: "📌 Dashboard de dotación" });
}

const tab = (name: string) => fireEvent.click(screen.getByRole("tab", { name }));

test("selector, parámetro y las 5 pestañas certificadas en orden; Productividad dentro de Análisis", async () => {
  await abrir();
  expect(screen.getByText("📊 Análisis")).toBeTruthy();
  const selector = screen.getByRole("combobox") as HTMLSelectElement;
  expect([...selector.options].map((o) => o.value)).toEqual(["2026-2", "2026-1"]);
  expect(selector.value).toBe("2026-2");
  expect(screen.getByText("⚙️ Parámetro de horas no lectivas")).toBeTruthy();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "📌 Dashboard de dotación", "👥 Plantel / dotación", "🔄 Movimiento docente", "🤖 Análisis automático / IA", "📈 Comparación de períodos",
  ]);
  expect(envios).toEqual([{ path: "periodo", body: { periodo: "2026-2" } }]);
  expect(screen.queryByText(/Productividad/, { selector: "[role=tab]" })).toBeNull();
});

test("Dashboard: métricas certificadas y tortas Vega-Lite (arc) con sus datos", async () => {
  await abrir();
  const d = fx["periodo_2026-2"].dashboard;
  for (const m of [...d.dotacion, ...d.operacion, ...d.horas]) expect(screen.getAllByText(m.label).length).toBeGreaterThan(0);
  expect(screen.getByText("Distribución de la dedicación contratada")).toBeTruthy();
  await waitFor(() => expect(specs.length).toBeGreaterThanOrEqual(2));
  const torta = specs.find((s) => JSON.stringify(s.data).includes("Comisiones (lectivas)"))!;
  expect(torta.mark).toEqual({ type: "arc", tooltip: true });
  expect(torta.encoding).toEqual(d.torta_horas.spec!.encoding);
  expect(screen.getByText("Resumen tabular")).toBeTruthy();
});

test("Guardar porcentaje: visible con permiso, envía la huella vista; oculto para solo lectura (D-AM4/D-AM5)", async () => {
  await abrir();
  fireEvent.click(screen.getByText("⚙️ Parámetro de horas no lectivas"));
  fireEvent.change(screen.getByLabelText("Horas no lectivas estimadas sobre horas de comisión (%)"), { target: { value: "45" } });
  fireEvent.click(screen.getByRole("button", { name: "💾 Guardar porcentaje de horas no lectivas" }));
  await waitFor(() => expect(envios.find((e) => e.path === "porcentaje")).toBeTruthy());
  expect(envios.find((e) => e.path === "porcentaje")!.body).toEqual({ porcentaje: 45, huella: fx.overview.parametro.huella });
  expect(await screen.findByText(/Porcentaje guardado: 45 %/)).toBeTruthy();
  cleanup();
  await abrir(fx.lector);
  expect(screen.queryByRole("button", { name: "💾 Guardar porcentaje de horas no lectivas" })).toBeNull();
  expect(screen.getAllByText("50 %").length).toBeGreaterThan(0);
});

test("Productividad: semáforo del código (colores certificados), filtro por diagnóstico y prompt sin IA real", async () => {
  await abrir();
  tab("🤖 Análisis automático / IA");
  const prod = fx["periodo_2026-2"].automatico.productividad!;
  const tabla = screen.getByRole("table", { name: "Productividad docente calculada" });
  const celdas = within(tabla).getAllByRole("cell").filter((c) => c.getAttribute("data-semaforo") !== null);
  expect(celdas.map((c) => c.getAttribute("data-semaforo"))).toEqual(prod.tabla.filas.map((f) => f.color));
  const roja = celdas.find((c) => c.getAttribute("data-semaforo") === "rojo");
  if (roja) expect(roja.className).toContain("bg-[#b91c1c]");
  const diag = prod.diagnosticos[0];
  fireEvent.click(within(screen.getByRole("group", { name: "Filtrar por diagnóstico" })).getByRole("button", { name: diag }));
  const restantes = prod.tabla.filas.filter((f) => f.diagnostico !== diag).length;
  expect(screen.getByText(`Filtro de diagnóstico activo: se muestran ${restantes} de ${prod.total} docentes.`)).toBeTruthy();
  expect((screen.getByLabelText("Prompt estructurado") as HTMLTextAreaElement).value).toContain("Departamento de Informática e Ingeniería");
  fireEvent.click(screen.getByRole("button", { name: "⬇️ Descargar prompt IA" }));
  await waitFor(() => expect(descargas).toContain("prompt_analisis_ia_2026-2.txt"));
  expect(envios.at(-1)).toEqual({ path: "descargas/prompt", body: { periodo: "2026-2" } });
});

test("Alertas: filtro por gravedad y CSV por categoría con los filtros visibles", async () => {
  await abrir();
  tab("🤖 Análisis automático / IA");
  const al = fx["periodo_2026-2"].automatico.alertas!;
  expect(screen.getByText("Alertas totales")).toBeTruthy();
  fireEvent.click(within(screen.getByRole("group", { name: "Filtrar por gravedad" })).getByRole("button", { name: "Baja" }));
  const cat = String(al.tabla.filas.find((f) => f[0] === "Alta")![1]);
  const boton = await screen.findByRole("button", { name: `⬇️ Descargar ${cat}` });
  fireEvent.click(boton);
  await waitFor(() => expect(envios.at(-1)?.path).toBe("descargas/alertas"));
  expect(envios.at(-1)!.body).toEqual({ periodo: "2026-2", categoria: cat, gravedades: ["Alta", "Media"] });
});

test("Movimiento docente: indicadores, CSV del indicador y Word en dos pasos", async () => {
  await abrir();
  tab("🔄 Movimiento docente");
  expect(screen.getByText("Resumen unitario")).toBeTruthy();
  fireEvent.click(screen.getByRole("radio", { name: "Bajas designaciones" }));
  const ind = fx["periodo_2026-2"].movimiento.indicadores!["Bajas designaciones"];
  expect(screen.getByText(/integran el indicador/).textContent).toContain(ind.caption.replace(/\*\*/g, "").slice(0, 20));
  fireEvent.click(screen.getByRole("radio", { name: "Altas designaciones" }));
  fireEvent.click(screen.getByRole("button", { name: "⬇️ Descargar detalle del indicador seleccionado" }));
  await waitFor(() => expect(envios.at(-1)).toEqual({ path: "descargas/indicador", body: { periodo: "2026-2", indicador: "Altas designaciones" } }));
  fireEvent.click(screen.getByRole("button", { name: "📄 Preparar informe Word del movimiento docente" }));
  const bajar = await screen.findByRole("button", { name: "⬇️ Descargar informe Word preparado" });
  expect(descargas).not.toContain("informe_movimiento_docente_2026-2.docx");
  fireEvent.click(bajar);
  expect(descargas).toContain("informe_movimiento_docente_2026-2.docx");
  expect(screen.getByText("Balance contra el mismo semestre del año anterior")).toBeTruthy();
});

test("Período histórico: relee 2026-1 y muestra el contexto histórico y los rótulos del período", async () => {
  await abrir();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "2026-1" } });
  expect(await screen.findByText(/Contexto histórico/)).toBeTruthy();
  expect(envios.at(-1)).toEqual({ path: "periodo", body: { periodo: "2026-1" } });
  expect(screen.getAllByText("Docentes del período").length).toBeGreaterThan(0);
});

test("Comparación: el actual es el último período; 3 subpestañas y 5 gráficos Vega-Lite", async () => {
  await abrir();
  tab("📈 Comparación de períodos");
  expect(screen.getByText("PERÍODO ACTUAL")).toBeTruthy();
  expect(screen.getAllByText(fx.overview.comparacion!.actual!.nombre).length).toBeGreaterThan(0);
  await waitFor(() => expect(envios.at(-1)).toEqual({ path: "comparacion", body: { periodos: ["2026-1"] } }));
  expect(await screen.findByRole("tab", { name: "🎯 Resumen ejecutivo" })).toBeTruthy();
  expect(screen.getByText("Síntesis del cambio")).toBeTruthy();
  specs.length = 0;
  fireEvent.click(screen.getByRole("tab", { name: "📊 Evolución visual" }));
  await waitFor(() => expect(specs.length).toBe(5));
  expect(specs.map((s) => (s.mark as { type: string }).type).sort()).toEqual(["bar", "bar", "bar", "line", "line"]);
  const horas = specs.find((s) => (s.mark as { opacity?: number }).opacity === 0.58)!;
  expect((horas.encoding as { x: { sort: string[] } }).x.sort).toEqual([
    "Horas de designación · total", "Horas frente a comisión", "Horas no lectivas", "Horas investigación + extensión", "Horas funciones no docentes",
  ]);
  fireEvent.click(screen.getByRole("tab", { name: "🔎 Detalle" }));
  expect(screen.getByText("Matriz completa de indicadores")).toBeTruthy();
});

test("sin períodos: aviso certificado y sin pestañas; sin exportaciones no certificadas", async () => {
  await abrir({ ...fx.overview, vacio: true, periodos: [], periodo: null }).catch(() => {});
  expect(await screen.findByText("Todavía no hay períodos registrados.")).toBeTruthy();
  expect(screen.queryAllByRole("tab")).toHaveLength(0);
  expect(screen.queryByText(/Excel|PDF|ZIP/)).toBeNull();
});
