// Flujo del módulo Consolidado institucional (ConsolidadoModule completo) con respuestas con la forma real de
// GET /consolidado y POST /consolidado/tabla (datos sintéticos, sin personas reales). Verifica la página certificada
// (4 métricas, control de consistencia abierto, resumen por departamento, selector de 9 tablas), la carga de cada tabla
// bajo demanda, el buscador por tabla (se aplica con Enter, como st.text_input), el CSV de la tabla completa, el Excel
// de la vista filtrada y del resumen, los estados vacíos y los errores genéricos (incluido el rechazo por rol).
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ConsolidadoModule } from "@/components/consolidado-module";
import type { Consolidado, TablaVisor } from "@/lib/consolidado";

const TABLAS = ["docentes", "designaciones", "comisiones", "inscriptos_asignatura_periodo", "asignaciones_docentes_comision",
  "investigacion_docente", "extension_docente", "disposiciones", "movimientos"];
const m = (label: string, valor: string) => ({ label, valor, delta: null, delta_color: "normal" as const, caption: null });

const TABLERO: Consolidado = {
  titulo: "🏛️ Consolidado institucional",
  contexto: { institucion: { id: 1, nombre: "Universidad de Prueba" } },
  estado: "tablero",
  metricas: [m("Departamentos", "3"), m("Docentes únicos por CUIL", "5"), m("Designaciones del período", "7"), m("Horas de las designaciones", "120.0")],
  caption: "Fuente única: **Designaciones del período** parte exactamente del listado departamental.",
  control: {
    titulo: "🔎 Control de consistencia",
    abierto: true,
    metricas: [m("Docentes únicos por CUIL", "5"), m("Suma de docentes de los departamentos", "6"), m("Designaciones sumadas", "7"), m("Docentes compartidos · repeticiones", "1")],
    caption: "La segunda cifra suma únicamente los docentes con designación activa de cada Plantel por período.",
  },
  resumen: {
    titulo: "Resumen por departamento",
    tabla: {
      columnas: ["Departamento", "Período tomado", "Estado del período", "Docentes del período", "Designaciones del período", "Horas de designaciones"],
      filas: [["Depto A", "2026-2", "Abierto", 4, 5, 90], ["Depto B", "2026-1", "Abierto", 2, 2, 30], ["Posgrado X", "Sin períodos", "Sin períodos", 0, 0, 0]],
    },
    excel: true,
  },
  visor: {
    titulo: "Ver datos consolidados",
    label: "Tabla",
    opciones: TABLAS,
    default: "docentes",
    buscador: { label: "🔎 Buscar en esta tabla", placeholder: "Buscar por nombre, CUIL, cargo, materia, período, estado, departamento...", help: "Busca el texto ingresado en todas las columnas de la tabla seleccionada." },
    csv: "Descargar CSV consolidado",
  },
};

const DOCENTES = { columnas: ["cuil", "nombre_completo", "departamento_origen", "periodo_consolidado"], filas: [["20-00000001-1", "Persona Uno", "Depto A", "2026-2"], ["20-00000002-2", "Persona Dos", "Depto B", "2026-1"]] };

function tablaResp(tabla: string, buscar: string): TablaVisor {
  if (tabla === "inscriptos_asignatura_periodo") return { tabla, vacio: true, mensaje: "No hay datos para el criterio seleccionado." };
  const datos = tabla === "docentes" ? DOCENTES : { columnas: ["periodo_id", "departamento_origen", "id"], filas: [[9, "Depto A", 1], [6, "Depto B", 2]] };
  const filas = buscar ? datos.filas.filter((f) => f.join(" ").toLowerCase().includes(buscar.toLowerCase())) : datos.filas;
  return {
    tabla, vacio: false, busqueda: buscar, total: datos.filas.length, encontrados: filas.length,
    caption: buscar.trim() ? `Resultados encontrados: ${filas.length} de ${datos.filas.length} registros.` : null,
    sin_coincidencias: filas.length ? null : "No se encontraron registros que coincidan con la búsqueda.",
    datos: filas.length ? { columnas: datos.columnas, filas } : null, excel: filas.length > 0,
  };
}

let overview: { status: number; body: unknown };
let llamadas: { url: string; body: Record<string, unknown> | null }[] = [];
let descargas: string[] = [];

beforeEach(() => {
  overview = { status: 200, body: TABLERO };
  llamadas = [];
  descargas = [];
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    descargas.push(this.download);
  });
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    llamadas.push({ url, body });
    expect(url.startsWith("/api/consolidado")).toBe(true);
    if (body) expect(Object.keys(body).every((k) => k === "tabla" || k === "buscar")).toBe(true); // nunca institución
    if (url === "/api/consolidado") return new Response(JSON.stringify(overview.body), { status: overview.status });
    if (url === "/api/consolidado/tabla") return new Response(JSON.stringify(tablaResp(body.tabla, body.buscar ?? "")), { status: 200 });
    if (url === "/api/consolidado/descargas/csv") {
      const n = `${body.tabla}_consolidado.csv`;
      return new Response(new Blob(["x"]), { status: 200, headers: { "content-disposition": `attachment; filename="${n}"; filename*=UTF-8''${n}` } });
    }
    if (url === "/api/consolidado/descargas/excel") {
      const n = `Consolidado_institucional_20261030_101500.xlsx`;
      return new Response(new Blob(["PK"]), { status: 200, headers: { "content-disposition": `attachment; filename="${n}"` } });
    }
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function abrir() {
  render(<ConsolidadoModule onAuthError={() => {}} />);
  await screen.findByText("🏛️ Consolidado institucional");
}

test("página: 4 métricas, caption, control de consistencia abierto, resumen con períodos por departamento y 9 tablas", async () => {
  await abrir();
  expect(screen.getByText("Universidad de Prueba")).toBeTruthy();
  expect(screen.getAllByTestId("metrica")).toHaveLength(8);
  expect(screen.getByText("Suma de docentes de los departamentos")).toBeTruthy();
  expect(screen.getByText("Docentes compartidos · repeticiones")).toBeTruthy();
  expect(screen.getByText("Designaciones del período", { selector: "strong" })).toBeTruthy();
  expect((screen.getByText("🔎 Control de consistencia").closest("details") as HTMLDetailsElement).open).toBe(true);
  const resumen = screen.getByRole("table", { name: "Resumen por departamento" });
  expect(resumen.textContent).toContain("2026-1");
  expect(resumen.textContent).toContain("Sin períodos");
  const select = screen.getByRole("combobox") as HTMLSelectElement;
  expect(Array.from(select.options).map((o) => o.value)).toEqual(TABLAS);
  expect(select.value).toBe("docentes");
  // carga inicial: solo la lectura institucional + la tabla por defecto (no las 9)
  await screen.findByRole("table", { name: "Tabla docentes" });
  expect(llamadas.map((l) => l.url)).toEqual(["/api/consolidado", "/api/consolidado/tabla"]);
  expect(llamadas[1].body).toEqual({ tabla: "docentes", buscar: "" });
});

test("cada tabla se pide al elegirla; tabla vacía muestra el mensaje certificado sin buscador ni CSV", async () => {
  await abrir();
  await screen.findByRole("table", { name: "Tabla docentes" });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "movimientos" } });
  await screen.findByRole("table", { name: "Tabla movimientos" });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "inscriptos_asignatura_periodo" } });
  await screen.findByText("No hay datos para el criterio seleccionado.");
  expect(screen.queryByPlaceholderText(/Buscar por nombre/)).toBeNull();
  expect(screen.queryByText("Descargar CSV consolidado")).toBeNull();
  expect(llamadas.filter((l) => l.url === "/api/consolidado/tabla").map((l) => l.body?.tabla)).toEqual(["docentes", "movimientos", "inscriptos_asignatura_periodo"]);
});

test("búsqueda por tabla (Enter): caption, sin coincidencias, CSV completo y Excel de la vista filtrada", async () => {
  await abrir();
  await screen.findByRole("table", { name: "Tabla docentes" });
  const input = screen.getByPlaceholderText(/Buscar por nombre/);
  fireEvent.change(input, { target: { value: "uno" } });
  fireEvent.keyDown(input, { key: "Enter" });
  await screen.findByText("Resultados encontrados: 1 de 2 registros.");
  expect(screen.getAllByText("📥 Descargar tabla en Excel")).toHaveLength(2); // resumen + vista filtrada
  fireEvent.click(screen.getAllByText("📥 Descargar tabla en Excel")[1]);
  await waitFor(() => expect(descargas).toContain("Consolidado_institucional_20261030_101500.xlsx"));
  expect(llamadas.find((l) => l.url.endsWith("/excel"))?.body).toEqual({ tabla: "docentes", buscar: "uno" });
  fireEvent.click(screen.getByText("Descargar CSV consolidado"));
  await waitFor(() => expect(descargas).toContain("docentes_consolidado.csv"));
  expect(llamadas.find((l) => l.url.endsWith("/csv"))?.body).toEqual({ tabla: "docentes" }); // sin búsqueda
  fireEvent.change(input, { target: { value: "zzz" } });
  fireEvent.blur(input);
  await screen.findByText("No se encontraron registros que coincidan con la búsqueda.");
  expect(screen.getAllByText("📥 Descargar tabla en Excel")).toHaveLength(1); // sin vista: solo el del resumen
  expect(screen.getByText("Descargar CSV consolidado")).toBeTruthy(); // el CSV se ofrece igual
  // el texto queda por tabla: al cambiar y volver, la búsqueda de docentes se conserva
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "comisiones" } });
  await screen.findByRole("table", { name: "Tabla comisiones" });
  expect((screen.getByPlaceholderText(/Buscar por nombre/) as HTMLInputElement).value).toBe("");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "docentes" } });
  await screen.findByText("No se encontraron registros que coincidan con la búsqueda.");
  expect((screen.getByPlaceholderText(/Buscar por nombre/) as HTMLInputElement).value).toBe("zzz");
});

test("Excel del resumen por departamento", async () => {
  await abrir();
  await screen.findByRole("table", { name: "Tabla docentes" });
  fireEvent.click(screen.getAllByText("📥 Descargar tabla en Excel")[0]);
  await waitFor(() => expect(llamadas.some((l) => l.url.endsWith("/excel") && l.body?.tabla === "resumen")).toBe(true));
  expect(llamadas.find((l) => l.url.endsWith("/excel"))?.body).toEqual({ tabla: "resumen" });
});

test("institución sin departamentos: 'Sin datos para consolidar.' y nada más", async () => {
  overview = { status: 200, body: { titulo: "🏛️ Consolidado institucional", contexto: { institucion: { id: 5, nombre: "Inst sin deptos" } }, estado: "sin_datos", mensaje: "Sin datos para consolidar." } };
  await abrir();
  expect(screen.getByText("Sin datos para consolidar.")).toBeTruthy();
  expect(screen.queryByRole("combobox")).toBeNull();
  expect(llamadas.map((l) => l.url)).toEqual(["/api/consolidado"]);
});

test("rol sin acceso y errores genéricos: solo el mensaje del backend, sin detalles internos", async () => {
  overview = { status: 403, body: { error: { code: "DENIED", message: "Esta vista es para coordinación institucional o superadmin." } } };
  render(<ConsolidadoModule onAuthError={() => {}} />);
  await screen.findByText("Esta vista es para coordinación institucional o superadmin.");
  expect(screen.queryByRole("table")).toBeNull();
  cleanup();
  overview = { status: 409, body: { error: { code: "SCOPE_NOT_VERIFIED", message: "No se pudo verificar la institución de la sesión." } } };
  render(<ConsolidadoModule onAuthError={() => {}} />);
  await screen.findByText("No se pudo verificar la institución de la sesión.");
  cleanup();
  const errores: number[] = [];
  overview = { status: 401, body: { error: { code: "UNAUTHENTICATED", message: "La sesión no es válida." } } };
  render(<ConsolidadoModule onAuthError={(e) => errores.push(e.status)} />);
  await waitFor(() => expect(errores).toEqual([401]));
});
