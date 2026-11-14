// E4-03: pestaña "👥 Equipos docentes" de Docentes. Datos SINTÉTICOS con la forma exacta de POST /docentes/equipos (el
// contenido real lo cubre el diferencial del backend).
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";
import type { DocentesOverview, Equipos, Plantel } from "@/lib/docentes";

const COLS = ["periodo", "codigo_materia", "asignatura", "materia_especifica", "carrera", "escuela", "plan_version",
  "comisiones", "turnos", "modalidades", "equipo_docente", "cantidad_comisiones", "cantidad_docentes",
  "horas_docentes_asignadas"];
const INFO = "Muestra los docentes que tiene cada materia en el período seleccionado, agrupando todas sus comisiones " +
  "y evitando repetir docentes.";
const PERIODOS = [{ id: 9, nombre: "2026-2" }, { id: 5, nombre: "2026-1" }];
const E9: Equipos = { info: INFO, periodos: PERIODOS, seleccionado: PERIODOS[0], sin_periodos: null, vacio: null,
  tabla: { columnas: COLS, filas: [
    ["2026-2", "ZZ1", "ZZ Algebra", "", "Carrera", "Escuela", "2020", "A (mañana / Presencial) | B", "mañana",
      "Presencial", "Zeta, Uno (Adjunto) | Solo Nombre", 2, 2, 10],
    ["2026-2", "ZZ9", "Optativa I", "Robótica", "Carrera", "Escuela", "2020", "noche", "noche", "", "20-90000009-9 (Responsable)", 1, 1, 3],
  ] }, total_materias: 2 };
const E5: Equipos = { info: INFO, periodos: PERIODOS, seleccionado: PERIODOS[1], sin_periodos: null,
  vacio: "No hay comisiones/equipos docentes registrados para ese período.", tabla: null, total_materias: null };
const SIN: Equipos = { info: INFO, periodos: [], seleccionado: null, sin_periodos: "Todavía no hay períodos registrados." };
const PLANTEL: Plantel = { periodos: [], seleccionado: null, sin_periodos: "sin" };
const OV = {
  contexto: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep" } },
  abierto: null, actual: null, historico: false, docentes: [],
  catalogos: { estados: [], estados_baja: [], tipos: [], niveles_posgrado: [], antiguedad_min: 0, antiguedad_max: 60 },
  permisos: { puede_escribir: false, puede_borrar: false, es_superadmin: false },
} as unknown as DocentesOverview;

let equiposPorId: Record<string, Equipos | number>;
let cuerpos: unknown[];

beforeEach(() => {
  equiposPorId = { null: E9, 9: E9, 5: E5 };
  cuerpos = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (url === "/api/docentes" && method === "GET") return new Response(JSON.stringify(OV), { status: 200 });
    if (url === "/api/docentes/plantel" && method === "POST") return new Response(JSON.stringify(PLANTEL), { status: 200 });
    if (url === "/api/docentes/equipos" && method === "POST") {
      const body = JSON.parse(String(init?.body));
      cuerpos.push(body);
      const r = equiposPorId[String(body.periodo_id)];
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

async function abrirEquipos() {
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("Plantel por período");
  const tab = screen.getByRole("tab", { name: /Equipos docentes/ });
  expect(within(tab).queryByText("Pendiente")).toBeNull();
  fireEvent.click(tab);
  await screen.findByText("Equipos docentes por materia");
}

test("sin marca Pendiente; aviso, selector (por defecto el abierto), tabla de 14 columnas y total de materias", async () => {
  await abrirEquipos();
  await screen.findByText("Zeta, Uno (Adjunto) | Solo Nombre");
  expect(cuerpos).toEqual([{ periodo_id: null }]);
  expect(screen.getByText(INFO)).toBeTruthy();
  const select = screen.getByRole("combobox") as HTMLSelectElement;
  expect(select.value).toBe("2026-2");
  expect([...select.options].map((o) => o.value)).toEqual(["2026-2", "2026-1"]);
  // 6A-B3: la clave del dato sigue siendo "escuela"; el encabezado visible es la categoría genérica
  expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(
    COLS.map((c) => (c === "escuela" ? "Unidad académica" : c)),
  );
  expect(screen.getByText("Total materias con equipo docente registrado: 2")).toBeTruthy();
  expect(screen.queryByText(/Se habilitará cuando se migren Comisiones y Materias/)).toBeNull();
  // E4-05 habilitó Resumen docente: ninguna pestaña queda "Pendiente".
  expect(within(screen.getByRole("tablist")).queryByText("Pendiente")).toBeNull();
});

test("cambiar de período pide ese id; sin equipos muestra el mensaje certificado y ninguna tabla", async () => {
  await abrirEquipos();
  await screen.findByText("Zeta, Uno (Adjunto) | Solo Nombre");
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "2026-1" } });
  await screen.findByText("No hay comisiones/equipos docentes registrados para ese período.");
  expect(cuerpos).toEqual([{ periodo_id: null }, { periodo_id: 5 }]);
  expect(screen.queryByRole("table")).toBeNull();
  expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("2026-1");
});

test("sin períodos: aviso informativo y advertencia certificada, sin selector", async () => {
  equiposPorId = { null: SIN };
  await abrirEquipos();
  await screen.findByText("Todavía no hay períodos registrados.");
  expect(screen.getByText(INFO)).toBeTruthy();
  expect(screen.queryByRole("combobox")).toBeNull();
});

test("falla de lectura: mensaje del backend", async () => {
  equiposPorId = { null: 503 };
  await abrirEquipos();
  await screen.findByText("La lectura de la base de datos falló (no es un resultado vacío).");
});
