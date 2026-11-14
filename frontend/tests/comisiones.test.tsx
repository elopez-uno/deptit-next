// Flujo REAL del módulo Comisiones (ComisionesModule completo) con las respuestas reales de la API de NEXT para UNO,
// departamento 1 (fixtures generadas por backend/tests/tools_comisiones_frontend_fixtures.py con ROLLBACK).
// Las escrituras no llegan a ningún backend: se verifica el cuerpo exacto que enviaría la pantalla.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ComisionesModule } from "@/components/comisiones-module";
import type { Detalle, Lista, Overview } from "@/lib/comisiones";

type Fixtures = {
  overview: Overview;
  lector: Overview;
  periodos: Record<string, unknown>;
  alertas: unknown;
  sedes: unknown;
  inscriptos: Record<string, unknown>;
  materias: { body: unknown; respuesta: { materias: { materia_id: number }[] } };
  materia: { body: { materia_id: number }; respuesta: unknown };
  docentes: { docentes: { cuil: string; etiqueta_alta: string; nombre_completo: string }[] };
  roles: Record<string, { roles: string[]; prestado_local: boolean }>;
  lista_modificacion: Lista;
  detalle_modificacion: Detalle;
  lista_edicion: Lista;
  detalle_edicion: Detalle;
  datos_edicion: unknown;
  carga: { texto: string; respuesta: { totales: Record<string, number>; huella: string } };
};
const fx: Fixtures = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "comisiones_uno.json"), "utf8"));
const LECTURAS = new Set([
  "periodo",
  "alertas",
  "sedes",
  "inscriptos",
  "abrir/materias",
  "abrir/materia",
  "docentes",
  "docentes/roles",
  "lista",
  "detalle",
  "edicion/datos",
  "carga-rapida/previsualizar",
  "asignacion/franjas",
]);

let overview: Overview;
let posts: { path: string; body: Record<string, unknown> }[] = [];
const escrituras = () => posts.filter((p) => !LECTURAS.has(p.path));

beforeEach(() => {
  overview = fx.overview;
  posts = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/comisiones" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/comisiones/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    posts.push({ path, body });
    if (path === "periodo") return ok(fx.periodos[String(body.periodo_id)] ?? { vacio: true });
    if (path === "alertas") return ok(fx.alertas);
    if (path === "sedes") return ok(fx.sedes);
    if (path === "inscriptos") return ok(fx.inscriptos[String(body.periodo_id)] ?? { legacy: [], vacio: true });
    if (path === "abrir/materias") return ok(fx.materias.respuesta);
    if (path === "abrir/materia") return ok(fx.materia.respuesta);
    if (path === "docentes") return ok(fx.docentes);
    if (path === "docentes/roles") return ok(fx.roles[String(body.cuil)] ?? { roles: [], prestado_local: false });
    if (path === "lista") return ok(body.contexto === "modificacion" ? fx.lista_modificacion : fx.lista_edicion);
    if (path === "detalle") return ok(body.contexto === "modificacion" ? fx.detalle_modificacion : fx.detalle_edicion);
    if (path === "edicion/datos") return ok(fx.datos_edicion);
    if (path === "carga-rapida/previsualizar") return ok(fx.carga.respuesta);
    return ok({ mensaje: "OK (respuesta simulada del test)", tono: "success" });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(tab?: string) {
  render(<ComisionesModule onAuthError={() => {}} />);
  await screen.findByRole("heading", { name: "📋 Módulo Comisiones" }, { timeout: 5000 });
  if (tab) fireEvent.click(screen.getByRole("tab", { name: tab }));
}

test("encabezado del período actual y las 8 pestañas en el orden certificado", async () => {
  await abrir();
  const a = fx.overview.actual!;
  expect(screen.getByText(`Período actual para comisiones: ${a.nombre} (${a.fecha_inicio} al ${a.fecha_fin}).`)).toBeTruthy();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "📋 Comisiones del período",
    "➕ Abrir comisión",
    "👥 Inscriptos",
    "🔁 Modificación de asignaciones",
    "📥 Carga rápida",
    "🚨 Alertas",
    "✏️ Editar / eliminar",
    "🏫 Sedes institucionales",
  ]);
  // Pestaña 1: período abierto por defecto, tabla integrada y pie con totales.
  await screen.findByText(/^Total comisiones: /, {}, { timeout: 5000 });
  expect(posts[0]).toEqual({ path: "periodo", body: { periodo_id: fx.overview.abierto!.id } });
  expect(screen.getByRole("columnheader", { name: "Alumnos del conjunto" })).toBeTruthy();
});

test("abrir comisión: envía comisión, horario por defecto y docente con su horario efectivo", async () => {
  await abrir("➕ Abrir comisión");
  await screen.findByText(/^Materias encontradas: /, {}, { timeout: 5000 });
  fireEvent.change(screen.getByPlaceholderText("Ej.: 1, 2, A, B"), { target: { value: "ZZ1" } });
  const doc = fx.docentes.docentes[0];
  fireEvent.click(await screen.findByRole("checkbox", { name: doc.etiqueta_alta }, { timeout: 5000 }));
  await screen.findByText("Horario efectivo que cubrirá este docente", {}, { timeout: 5000 });
  fireEvent.click(screen.getByRole("button", { name: "➕ Abrir comisión con horarios y docentes" }));
  await waitFor(() => expect(escrituras().length).toBe(1));
  const roles = fx.roles[doc.cuil]?.roles ?? [];
  expect(escrituras()[0]).toEqual({
    path: "abrir",
    body: expect.objectContaining({
      materia_id: fx.materias.respuesta.materias[0].materia_id,
      adicionales: [],
      nombre: "ZZ1",
      turno: "mañana",
      modalidad: "Presencial",
      horarios: [{ dia: "Lunes", hora_inicio: "08:00", hora_fin: "12:00" }],
      docentes: [{ cuil: doc.cuil, rol: roles[0] ?? fx.overview.catalogos.roles[0], franjas: [{ usar: true, desde: "08:00", hasta: "12:00" }] }],
      huella_periodos: fx.overview.huella_periodos,
    }),
  });
});

test("modificación: subpestañas y baja real con confirmación y huella", async () => {
  await abrir("🔁 Modificación de asignaciones");
  await screen.findByText(/^Comisión seleccionada · /, {}, { timeout: 5000 });
  const sub = screen.getByRole("tablist", { name: "Acciones sobre la comisión" });
  expect(within(sub).getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "📌 Estado actual",
    "➕ Alta docente",
    "➖ Baja docente",
    "🕘 Historial",
  ]);
  fireEvent.click(within(sub).getByRole("tab", { name: "➖ Baja docente" }));
  const activa = fx.detalle_modificacion.asignaciones.find((a) => String(a.estado ?? "Activa") === "Activa");
  if (!activa) return;
  fireEvent.click(screen.getByRole("checkbox", { name: "Confirmo que es una baja real en la comisión y debe quedar en historial" }));
  fireEvent.click(screen.getByRole("button", { name: "Registrar baja por modificación de asignación" }));
  await waitFor(() => expect(escrituras().length).toBe(1));
  expect(escrituras()[0]).toEqual({
    path: "modificacion/baja",
    body: expect.objectContaining({
      comision_id: fx.lista_modificacion.filas[0].id,
      asignacion_id: activa.id,
      confirmar: true,
      huella: fx.detalle_modificacion.huella,
    }),
  });
});

test("editar / eliminar: 5 subpestañas, horarios con 3 acciones y docentes con 3 correcciones", async () => {
  await abrir("✏️ Editar / eliminar");
  await screen.findByText(/^Comisión seleccionada · /, {}, { timeout: 5000 });
  const sub = screen.getByRole("tablist", { name: "Secciones de corrección" });
  expect(within(sub).getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "📌 Estado actual",
    "📝 Datos generales",
    "🕒 Horarios",
    "👥 Docentes",
    "🗑️ Eliminar",
  ]);
  fireEvent.click(within(sub).getByRole("tab", { name: "🕒 Horarios" }));
  const hs = screen.getByRole("tablist", { name: "Acciones sobre horarios" });
  expect(within(hs).getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "✏️ Editar horario",
    "➕ Agregar horario",
    "🗑️ Eliminar horario",
  ]);
  fireEvent.click(within(hs).getByRole("tab", { name: "➕ Agregar horario" }));
  fireEvent.click(screen.getByRole("button", { name: "➕ Agregar horario" }));
  await waitFor(() => expect(escrituras().length).toBe(1));
  expect(escrituras()[0]).toEqual({
    path: "edicion/horario/agregar",
    body: { comision_id: fx.lista_edicion.filas[0].id, dia: "Lunes", hora_inicio: "08:00", hora_fin: "12:00", observaciones: "", huella: fx.detalle_edicion.huella },
  });
  fireEvent.click(within(sub).getByRole("tab", { name: "👥 Docentes" }));
  expect(screen.getAllByRole("radio").map((r) => (r.parentElement?.textContent ?? "").trim())).toEqual(
    expect.arrayContaining(["➕ Asignar docente", "🕒 Horario efectivo", "🗑️ Quitar asignación"])
  );
  // usuario de departamento: la eliminación de la comisión es solo de superadmin
  fireEvent.click(within(sub).getByRole("tab", { name: "🗑️ Eliminar" }));
  expect(screen.queryByRole("button", { name: "🗑️ Eliminar comisión completa" })).toBeNull();
});

test("carga rápida: vista previa real y carga con confirmación y huella de la vista previa", async () => {
  await abrir("📥 Carga rápida");
  fireEvent.change(screen.getByRole("textbox", { name: "Pegá acá las comisiones con horarios" }), { target: { value: fx.carga.texto } });
  await screen.findByText("Vista previa", {}, { timeout: 5000 });
  expect(screen.getByText("Listas").parentElement?.textContent).toContain(String(fx.carga.respuesta.totales.ok));
  fireEvent.click(screen.getByRole("checkbox", { name: /Confirmo que quiero cargar solamente/ }));
  fireEvent.click(screen.getByRole("button", { name: "📥 Cargar comisiones válidas" }));
  await waitFor(() => expect(escrituras().length).toBe(1));
  expect(escrituras()[0]).toEqual({
    path: "carga-rapida",
    body: { texto: fx.carga.texto, excel: null, confirmar: true, huella: fx.carga.respuesta.huella },
  });
});

test("solo lectura: no se muestran botones de escritura", async () => {
  overview = fx.lector;
  await abrir("🏫 Sedes institucionales");
  await screen.findByText("Sedes activas", {}, { timeout: 5000 });
  expect(screen.queryByRole("button", { name: "➕ Agregar sede institucional" })).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "➕ Abrir comisión" }));
  await screen.findByText(/^Materias encontradas: /, {}, { timeout: 5000 });
  expect(screen.queryByRole("button", { name: "➕ Abrir comisión con horarios y docentes" })).toBeNull();
  expect(escrituras()).toEqual([]);
});
