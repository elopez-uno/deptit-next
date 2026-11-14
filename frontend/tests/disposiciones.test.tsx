// Flujo REAL del módulo Disposiciones (DisposicionesModule completo) con las respuestas reales de la API de NEXT para
// UNO, departamento 1 (fixtures generadas por backend/tests/tools_disposiciones_frontend_fixtures.py con ROLLBACK y una
// plantilla sintética en una raíz temporal). Las escrituras y descargas no llegan a ningún backend: se verifica el cuerpo
// exacto que enviaría la pantalla y que nunca se exponen rutas físicas.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DisposicionesModule } from "@/components/disposiciones-module";
import type { Historial, Overview, PeriodoData, Vista } from "@/lib/disposiciones";

type Fx = Record<string, unknown> & {
  overview: Overview;
  super: Overview;
  lector: Overview;
  sin_plantilla: Overview;
  periodo: PeriodoData;
  primero: Vista;
  con_designaciones: Vista;
  mixta?: Vista;
  historial: Historial;
};
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "disposiciones_uno.json"), "utf8"));

let overview: Overview;
let posts: { path: string; body: Record<string, unknown> }[] = [];
let vistaPorCuil: Record<string, Vista> = {};
const LECTURAS = new Set(["periodo", "docente", "docente/vista-previa", "historial"]);
const escrituras = () => posts.filter((p) => !LECTURAS.has(p.path));
let respuesta: { status: number; data: unknown } = { status: 200, data: { mensaje: "ok", tono: "success" } };
let binario: Response | null = null;

beforeEach(() => {
  overview = fx.overview;
  posts = [];
  vistaPorCuil = { [fx.primero.cuil]: fx.primero, [fx.con_designaciones.cuil]: fx.con_designaciones };
  if (fx.mixta) vistaPorCuil[fx.mixta.cuil] = fx.mixta;
  respuesta = { status: 200, data: { mensaje: "ok", tono: "success" } };
  binario = null;
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
    if (url === "/api/disposiciones" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/disposiciones/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    posts.push({ path, body });
    if (path === "periodo") return ok(fx.periodo);
    if (path === "docente") return ok(vistaPorCuil[String(body.cuil)] ?? fx.primero);
    if (path === "docente/vista-previa") return ok({ considerandos: ["Que, por Resolución CS se designó al docente ZZ;"], aviso_incompletas: "" });
    if (path === "historial") return ok(fx.historial);
    if (binario && ["descargar", "historial/zip", "zip-lote"].includes(path)) return binario;
    return ok(respuesta.data, respuesta.status);
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(tab?: string) {
  render(<DisposicionesModule onAuthError={() => {}} />);
  await screen.findByText("📄 Disposiciones");
  if (tab) fireEvent.click(screen.getByRole("tab", { name: tab }));
}

test("las 3 pestañas certificadas en orden, aviso y configuración de 10 campos con la plantilla", async () => {
  await abrir();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["⚙️ Configuración", "📝 Nueva disposición", "📚 Historial"]);
  expect(screen.getByText(/genera disposiciones en Word a partir de la plantilla/)).toBeTruthy();
  expect(screen.getByText(/La institución tiene su plantilla configurada \(actualizada .+, huella [0-9a-f]{12}\)\./)).toBeTruthy();
  expect(screen.getByLabelText("Rector/a")).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Rector/a"), { target: { value: "ZZNEXT Rectora" } });
  fireEvent.click(screen.getByRole("button", { name: /Guardar configuración de disposiciones/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const enviado = escrituras()[0];
  expect(enviado.path).toBe("configuracion/guardar");
  expect(Object.keys(enviado.body.valores as object)).toHaveLength(10);
  expect((enviado.body.valores as Record<string, string>).rector).toBe("ZZNEXT Rectora");
  expect(enviado.body.huella).toBe(overview.huella_configuracion);
  expect(document.body.innerHTML).not.toMatch(/C:\\|inst_1|storage|\.docx#/);
  expect(screen.queryByText(/PDF|Excel/)).toBeNull();
});

test("sin plantilla: estado visible y reemplazo .docx con validación de extensión", async () => {
  overview = fx.sin_plantilla;
  await abrir();
  expect(screen.getByText(/La institución no tiene una plantilla Word de disposición configurada/)).toBeTruthy();
  const input = screen.getByLabelText("Cargar/reemplazar plantilla Word de la institución") as HTMLInputElement;
  fireEvent.change(input, { target: { files: [new File(["x"], "modelo.pdf")] } });
  expect(screen.getByText("El archivo debe tener extensión .docx.")).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Reemplazar plantilla/ })).toBeNull();
  fireEvent.change(input, { target: { files: [new File(["PK"], "Modelo.docx")] } });
  fireEvent.click(await screen.findByRole("button", { name: /Reemplazar plantilla de la institución/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({ path: "plantilla/reemplazar", body: { nombre_archivo: "Modelo.docx", contenido_base64: btoa("PK") } });
});

test("nueva disposición: padrón numerado, docente por defecto, considerandos y cuerpo exacto de la generación", async () => {
  await abrir("📝 Nueva disposición");
  await screen.findByText("Docentes activos del período");
  expect(screen.getByDisplayValue(String(fx.periodo.numero_inicial))).toBeTruthy();
  expect(screen.getByRole("button", { name: `📄 Generar las ${fx.periodo.habilitados.length} disposiciones y preparar ZIP` })).toBeTruthy();
  await screen.findByText(/Estado de la consulta antes de generar la disposición/);
  expect((screen.getByLabelText("Incluir artículo de actividades especiales") as HTMLInputElement).disabled).toBe(true);
  await screen.findByText("Que, por Resolución CS se designó al docente ZZ;");
  // elegir el docente con designaciones y generar
  fireEvent.click(screen.getAllByLabelText("Seleccionar fila")[fx.periodo.habilitados.findIndex((h) => h.cuil === fx.con_designaciones.cuil)]);
  await waitFor(() => expect(posts.some((p) => p.path === "docente" && p.body.cuil === fx.con_designaciones.cuil)).toBe(true));
  await screen.findByDisplayValue(fx.con_designaciones.numero);
  respuesta = { status: 200, data: { mensaje: "Disposición generada y guardada en historial.", tono: "success", id: 99, file_name: "20261028-100000_Disposicion_x.docx" } };
  fireEvent.click(screen.getByRole("button", { name: /Generar Word de disposición/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const v = fx.con_designaciones;
  expect(escrituras()[0].path).toBe("generar");
  expect(escrituras()[0].body).toMatchObject({
    periodo_id: overview.periodo_defecto,
    cuil: v.cuil,
    huella: v.huella,
    tipo: "Asignación de funciones docentes",
    estado: "Borrador",
    incluir_concursado: v.tiene_concursado,
    incluir_interino: v.tiene_interino,
    incluir_investigacion: v.tiene_investigacion_o_extension,
    designaciones: v.designaciones.map((d) => ({ designacion_id: d.designacion_id, fecha_desde: d.fecha_desde, fecha_hasta: d.fecha_hasta, observaciones: d.observaciones })),
  });
  binario = new Response(new Blob(["PK"]), { status: 200, headers: { "content-disposition": "attachment; filename=\"20261028-100000_Disposicion_x.docx\"" } });
  fireEvent.click(await screen.findByRole("button", { name: /Descargar Word generado/ }));
  await waitFor(() => expect(posts.some((p) => p.path === "descargar" && p.body.id === 99)).toBe(true));
});

test("generación masiva: UNA acción; preflight con errores muestra la tabla y no ofrece ZIP", async () => {
  await abrir("📝 Nueva disposición");
  await screen.findByText("Docentes activos del período");
  fireEvent.click(screen.getByText("📦 Generar todas las disposiciones del período"));
  respuesta = {
    status: 200,
    data: { tono: "error", mensaje: "No se generó ninguna disposición porque hay docentes con una designación concursada/interina activa DEL DEPARTAMENTO ACTUAL sin acto administrativo vinculado al repositorio. Vinculá esos actos en Designaciones.", tabla: [{ "N° disposición": "72", Docente: "ZZ", CUIL: "20-1-0" }], generadas: 0, ids: [], errores: [] },
  };
  fireEvent.click(screen.getByRole("button", { name: /Generar las \d+ disposiciones y preparar ZIP/ }));
  await screen.findByText(/No se generó ninguna disposición/);
  expect(escrituras()).toHaveLength(1);
  expect(escrituras()[0]).toMatchObject({ path: "generar-masiva", body: { periodo_id: overview.periodo_defecto, estado: "Borrador", huella_padron: fx.periodo.huella_padron } });
  expect(screen.queryByRole("button", { name: /Descargar ZIP/ })).toBeNull();
  respuesta = { status: 200, data: { tono: "success", mensaje: "Se generaron y guardaron 2 disposiciones del período. Ya podés descargar el ZIP debajo.", tabla: [], generadas: 2, ids: [5, 6], errores: [{ "N° disposición": "74", Docente: "ZZ", Error: "No se pudo..." }], aviso: "Hubo 1 disposición/es que no pudieron generarse. Las restantes sí quedaron guardadas.", zip_nombre: "Disposiciones_2026-2.zip" } };
  fireEvent.click(screen.getByRole("button", { name: /Generar las \d+ disposiciones y preparar ZIP/ }));
  await screen.findByText(/Hubo 1 disposición\/es que no pudieron generarse/);
  binario = new Response(new Blob(["PK"]), { status: 200, headers: { "content-disposition": "attachment; filename=\"Disposiciones_2026-2.zip\"" } });
  fireEvent.click(screen.getByRole("button", { name: "⬇️ Descargar ZIP con todas las disposiciones (2)" }));
  await waitFor(() => expect(posts.some((p) => p.path === "zip-lote")).toBe(true));
  expect(posts.find((p) => p.path === "zip-lote")!.body).toEqual({ periodo_id: overview.periodo_defecto, ids: [5, 6] });
});

test("historial: legado bloqueado, sin ZIP, eliminar solo superadmin con confirmación", async () => {
  await abrir("📚 Historial");
  await screen.findByText("Disposiciones encontradas");
  expect(screen.getByText("No hay archivos Word disponibles para descargar en conjunto con este filtro.")).toBeTruthy();
  expect(screen.getByText(/Documento histórico anterior a B12E/)).toBeTruthy();
  expect(screen.queryByRole("button", { name: /Descargar Word del historial/ })).toBeNull();
  expect(screen.queryByRole("button", { name: /Eliminar registro/ })).toBeNull();
  expect(screen.getByText(`Resultados: ${fx.historial.filas.length} de ${fx.historial.filas.length} disposiciones`)).toBeTruthy();
  cleanup();
  overview = fx.super;
  await abrir("📚 Historial");
  await screen.findByText("Disposiciones encontradas");
  fireEvent.click(screen.getByRole("button", { name: /Eliminar registro de disposición/ }));
  expect(screen.getByText("Primero confirmá la eliminación.")).toBeTruthy();
  expect(escrituras()).toHaveLength(0);
  fireEvent.click(screen.getByLabelText("Confirmo que quiero eliminar el registro de esta disposición"));
  fireEvent.click(screen.getByRole("button", { name: /Eliminar registro de disposición/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const f = fx.historial.filas[0];
  expect(escrituras()[0]).toEqual({ path: "historial/eliminar", body: { id: f.id, huella: f.huella, confirmar: true } });
});

test("solo lectura: sin botones de escritura, plantilla ni eliminación", async () => {
  overview = fx.lector;
  await abrir();
  expect(screen.queryByRole("button", { name: /Guardar configuración/ })).toBeNull();
  expect(screen.queryByLabelText("Cargar/reemplazar plantilla Word de la institución")).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "📝 Nueva disposición" }));
  await screen.findByText("Docentes activos del período");
  expect(screen.queryByRole("button", { name: /Guardar número inicial/ })).toBeNull();
  expect(screen.queryByRole("button", { name: /Generar Word/ })).toBeNull();
});
