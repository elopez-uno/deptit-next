// E4-02: pestaña "Plantel del período abierto" de Docentes y estado operativo histórico de la base maestra. Datos
// SINTÉTICOS con la forma exacta de POST /docentes/plantel (el contenido real lo cubre el diferencial del backend).
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";
import type { Docente, DocentesOverview, Plantel } from "@/lib/docentes";

const COLS = ["cuil", "legajo", "nombre_completo", "titulo", "titulo_posgrado", "email", "telefono", "tipo_docente",
  "estado_operativo_periodo", "fecha_alta_periodo", "fecha_finalizacion_periodo", "designaciones_del_periodo",
  "designaciones_activas", "horas_activas", "horas_registradas_periodo", "detalle_designaciones"];
const fila = (cuil: string, nombre: string, activas: number) =>
  [cuil, "L1", nombre, "Lic.", "", "x@test.local", "", "Propio", activas ? "Activo en el período" : "Finalizado",
    "2026-08-01", "", 1, activas, 10, 10, "Profesor Adjunto - Simple"];
const info = (p: string) =>
  `Este plantel se calcula desde **todas las designaciones registradas** del período **${p}**. La columna de estado ` +
  "operativo indica si el docente sigue activo o si ya quedó finalizado / sin designación activa en ese período.";
const PERIODOS = [{ id: 9, nombre: "2026-2" }, { id: 5, nombre: "2026-1" }];
const P9: Plantel = { periodos: PERIODOS, seleccionado: PERIODOS[0], sin_periodos: null, info: info("2026-2"), vacio: null,
  tabla: { columnas: COLS, filas: [fila("20-00000001-1", "Docente, Uno", 1), fila("20-00000002-2", "Docente, Dos", 0)] },
  total_activos: 1 };
const P5: Plantel = { periodos: PERIODOS, seleccionado: PERIODOS[1], sin_periodos: null, info: info("2026-1"),
  vacio: "No hay docentes con designaciones registradas en el período seleccionado.", tabla: null, total_activos: null };
const SIN: Plantel = { periodos: [], seleccionado: null,
  sin_periodos: "Todavía no hay períodos registrados. Creá uno en el módulo Períodos para ver el plantel." };

const docente = (cuil: string, estado: string): Docente => ({
  cuil, legajo: null, apellido: "Docente", nombres: cuil, nombre_completo: `Docente, ${cuil}`, titulo: null,
  titulo_posgrado: "", antiguedad_anios: null, nivel_posgrado_salarial: "", email: null, telefono: null,
  ref_legajo_fisico: null, tipo_docente: "Propio", observaciones: "", estado: "Activo", fecha_alta: "2026-03-01",
  fecha_finalizacion: "", estado_periodo_abierto: estado, huella: cuil });
const overview = (historico: boolean): DocentesOverview => ({
  contexto: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep" } },
  abierto: { id: historico ? 5 : 9, nombre: historico ? "2026-1" : "2026-2", fecha_inicio: null, fecha_fin: null, estado: "Abierto" },
  actual: { id: 9, nombre: "2026-2", fecha_inicio: null, fecha_fin: null, estado: historico ? "Cerrado" : "Abierto" },
  historico,
  docentes: historico
    ? [docente("20-1", "Vigente al cierre del período en contexto"), docente("20-2", "Fuera de la dotación al cierre del período en contexto")]
    : [docente("20-1", "Activo en período actual")],
  catalogos: { estados: [], estados_baja: [], tipos: [], niveles_posgrado: [], antiguedad_min: 0, antiguedad_max: 60 },
  permisos: { puede_escribir: false, puede_borrar: false, es_superadmin: false },
});

let plantelPorId: Record<string, Plantel | number>;
let ov: DocentesOverview;
let cuerpos: unknown[];

beforeEach(() => {
  plantelPorId = { null: P9, 9: P9, 5: P5 };
  ov = overview(false);
  cuerpos = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (url === "/api/docentes" && method === "GET") return new Response(JSON.stringify(ov), { status: 200 });
    if (url === "/api/docentes/plantel" && method === "POST") {
      const body = JSON.parse(String(init?.body));
      cuerpos.push(body);
      const r = plantelPorId[String(body.periodo_id)];
      if (typeof r === "number") return new Response(JSON.stringify({ error: { code: "DB_READ", message: "La lectura de la base de datos falló (no es un resultado vacío)." } }), { status: r });
      return new Response(JSON.stringify(r), { status: 200 });
    }
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("abre en Plantel (primera pestaña certificada), sin marca Pendiente, con selector, aviso, tabla y total", async () => {
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("Plantel por período");
  const tab = screen.getByRole("tab", { name: /Plantel del período abierto/ });
  expect(tab.getAttribute("aria-selected")).toBe("true");
  expect(within(tab).queryByText("Pendiente")).toBeNull();
  // E4-03 y E4-05 habilitaron Equipos y Resumen docente: ninguna pestaña queda "Pendiente".
  expect(within(screen.getByRole("tablist")).queryByText("Pendiente")).toBeNull();
  await screen.findByText("Docente, Uno");
  expect(cuerpos).toEqual([{ periodo_id: null }]);
  const select = screen.getByRole("combobox") as HTMLSelectElement;
  expect(select.value).toBe("2026-2");
  expect([...select.options].map((o) => o.value)).toEqual(["2026-2", "2026-1"]);
  const aviso = screen.getByText((_, el) => el?.getAttribute("role") === "status" && !!el.textContent?.startsWith("Este plantel"));
  expect([...aviso.querySelectorAll("strong")].map((s) => s.textContent)).toEqual(["todas las designaciones registradas", "2026-2"]);
  const encabezados = screen.getAllByRole("columnheader").map((h) => h.textContent);
  expect(encabezados).toEqual(COLS);
  expect(screen.getByText("Total docentes activos con designaciones activas en el período seleccionado: 1")).toBeTruthy();
});

test("cambiar de período pide ese id; plantel vacío muestra el mensaje certificado y ninguna tabla", async () => {
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("Docente, Uno");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "2026-1" } });
  await screen.findByText("No hay docentes con designaciones registradas en el período seleccionado.");
  expect(cuerpos).toEqual([{ periodo_id: null }, { periodo_id: 5 }]);
  expect(screen.queryByRole("table")).toBeNull();
  expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("2026-1");
});

test("sin períodos: aviso certificado y sin selector", async () => {
  plantelPorId = { null: SIN };
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText(SIN.sin_periodos!);
  expect(screen.queryByRole("combobox")).toBeNull();
});

test("falla de lectura: mensaje del backend", async () => {
  plantelPorId = { null: 503 };
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("La lectura de la base de datos falló (no es un resultado vacío).");
});

test("base maestra con período histórico: etiquetas v183 del backend y sin la nota obsoleta", async () => {
  ov = overview(true);
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("Plantel por período");
  fireEvent.click(screen.getByRole("tab", { name: /Base maestra/ }));
  await screen.findByText("Vigente al cierre del período en contexto");
  expect(screen.getByText("Fuera de la dotación al cierre del período en contexto")).toBeTruthy();
  expect(screen.queryByText(/se habilitará con el módulo Designaciones/)).toBeNull();
  await waitFor(() => expect(screen.queryByText(/No disponible: requiere el plantel histórico/)).toBeNull());
});
