// Flujo REAL del módulo Movimientos (MovimientosModule completo) con las respuestas reales de la API de NEXT para UNO,
// departamento 1 (fixtures generadas por backend/tests/tools_movimientos_frontend_fixtures.py con ROLLBACK; nombres,
// CUIL y textos anonimizados). Las escrituras no llegan a ningún backend: se verifica el cuerpo exacto que enviaría la
// pantalla (ids + huella de la capa U) y la visibilidad por rol (D-AL2).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { MovimientosModule } from "@/components/movimientos-module";
import type { Documento, Listado, Overview } from "@/lib/movimientos";

type Fx = { overview: Overview; super: Overview; lector: Overview; todos: Listado; actos: { documentos: Documento[] } };
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "movimientos_uno.json"), "utf8"));

let overview: Overview;
let envios: { path: string; body: unknown }[] = [];
const escrituras = () => envios.filter((e) => !["listado", "actos"].includes(e.path));

beforeEach(() => {
  overview = fx.overview;
  envios = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
    if (url === "/api/movimientos" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/movimientos/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    envios.push({ path, body });
    if (path === "listado") return ok(body.periodo === "Todos los períodos" ? fx.todos : { periodo: overview.periodo, filas: overview.filas });
    if (path === "actos") return ok(fx.actos);
    if (path === "eliminar") return ok({ mensaje: "Movimiento eliminado.", tono: "warning" });
    return ok({ mensaje: "Acto administrativo vinculado a 1 movimiento/s.", tono: "success" });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function abrir(o: Overview = fx.overview) {
  overview = o;
  render(<MovimientosModule onAuthError={() => {}} />);
  await screen.findByText("📜 Movimientos");
}

const tablaPrincipal = () => screen.getByText("Movimientos encontrados").parentElement as HTMLElement;

test("una sola página sin pestañas: título, filtro de período, tabla de 8 columnas y primera fila seleccionada", async () => {
  await abrir();
  expect(screen.queryAllByRole("tab")).toHaveLength(0);
  expect(screen.getByText("Historial de movimientos")).toBeTruthy();
  const selector = screen.getByRole("combobox") as HTMLSelectElement;
  expect([...selector.options].map((o) => o.value)).toEqual(overview.periodos);
  expect(selector.value).toBe("2026-2");
  const tabla = tablaPrincipal();
  expect(within(tabla).getAllByRole("columnheader").map((h) => h.textContent).filter(Boolean)).toEqual([
    "Período", "Fecha", "Movimiento", "Persona / registro", "CUIL", "Detalle", "Acto administrativo", "Observaciones",
  ]);
  const radios = within(tabla).getAllByRole("radio", { name: "Seleccionar fila" }) as HTMLInputElement[];
  expect(radios).toHaveLength(overview.filas.length);
  expect(radios[0].checked).toBe(true);
  expect(radios.filter((r) => r.checked)).toHaveLength(1);
  expect(screen.getByText(`Resultados: ${overview.filas.length} de ${overview.filas.length} movimientos`)).toBeTruthy();
  expect(document.body.innerHTML).not.toMatch(/source_db|sqlite|C:\\|\.db\b/);
});

test("buscador certificado y sin resultados: sin tabla y Eliminar deshabilitado", async () => {
  await abrir(fx.super);
  const buscar = screen.getByPlaceholderText("Fecha, tipo, docente, CUIL, detalle, observaciones...");
  fireEvent.change(buscar, { target: { value: "  pendiente   DE vincular " } });
  const esperadas = overview.filas.filter((f) => f.acto_administrativo === "Pendiente de vincular").length;
  expect(screen.getByText(`Resultados: ${esperadas} de ${overview.filas.length} movimientos`)).toBeTruthy();
  fireEvent.change(buscar, { target: { value: "zz-no-existe" } });
  expect(screen.queryByText("Movimientos encontrados")).toBeNull();
  expect(screen.getByText(`Resultados: 0 de ${overview.filas.length} movimientos`)).toBeTruthy();
  expect((screen.getByRole("button", { name: "🗑️ Eliminar movimiento" }) as HTMLButtonElement).disabled).toBe(true);
});

test("cambiar a Todos los períodos relee por nombre sin paginar", async () => {
  await abrir();
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "Todos los períodos" } });
  await waitFor(() => expect(screen.getByText(`Resultados: ${fx.todos.filas.length} de ${fx.todos.filas.length} movimientos`)).toBeTruthy());
  expect(envios).toContainEqual({ path: "listado", body: { periodo: "Todos los períodos" } });
  expect(within(tablaPrincipal()).getAllByRole("radio", { name: "Seleccionar fila" })).toHaveLength(fx.todos.filas.length);
});

test("usuario de departamento: vincula con huellas, sin Quitar vínculo ni Eliminar (D-AL2)", async () => {
  await abrir();
  expect(screen.queryByText("Eliminar movimiento del historial")).toBeNull();
  expect(screen.queryByRole("button", { name: "🗑️ Eliminar movimiento" })).toBeNull();
  fireEvent.click(screen.getByText("🔗 Vincular / cambiar acto administrativo de uno o varios movimientos"));
  const elegibles = overview.filas.filter((f) => overview.tipos_con_acto.includes(f.tipo_movimiento ?? ""));
  expect(screen.getByText(`Movimientos mostrados: ${elegibles.length}`)).toBeTruthy();
  const checks = screen.getAllByRole("checkbox", { name: "Seleccionar" });
  fireEvent.click(checks[0]);
  await screen.findByText("Acto administrativo común para los movimientos seleccionados");
  expect(screen.queryByRole("button", { name: "Quitar vínculo de los seleccionados y dejar pendiente" })).toBeNull();
  const vincular = screen.getByRole("button", { name: "🔗 Vincular / cambiar acto de los seleccionados" }) as HTMLButtonElement;
  expect(vincular.disabled).toBe(true); // sin acto elegido (el selector no preselecciona)
  const doc = fx.actos.documentos[0];
  const selector = screen.getByText("Actos encontrados").parentElement as HTMLElement;
  fireEvent.click(within(selector).getAllByRole("radio", { name: "Seleccionar fila" })[0]);
  fireEvent.click(vincular);
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({
    path: "actos/vincular",
    body: { documento_id: doc.id, seleccion: [{ id: elegibles[0].id, huella: elegibles[0].huella }] },
  });
});

test("superadmin: Eliminar con confirmación previa, sobre la fila seleccionada, y Quitar vínculo visible", async () => {
  await abrir(fx.super);
  const boton = screen.getByRole("button", { name: "🗑️ Eliminar movimiento" });
  fireEvent.click(boton);
  expect(await screen.findByText("Primero confirmá la eliminación.")).toBeTruthy();
  expect(escrituras()).toHaveLength(0);
  const radios = within(tablaPrincipal()).getAllByRole("radio", { name: "Seleccionar fila" });
  fireEvent.click(radios[2]);
  fireEvent.click(screen.getByLabelText("Confirmo que quiero eliminar este movimiento"));
  fireEvent.click(boton);
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const fila = overview.filas[2];
  expect(escrituras()[0]).toEqual({ path: "eliminar", body: { id: fila.id, huella: fila.huella, confirmar: true } });
  await screen.findByText("Movimiento eliminado.");
  fireEvent.click(screen.getByText("🔗 Vincular / cambiar acto administrativo de uno o varios movimientos"));
  fireEvent.click(screen.getAllByRole("checkbox", { name: "Seleccionar" })[0]);
  expect(await screen.findByRole("button", { name: "Quitar vínculo de los seleccionados y dejar pendiente" })).toBeTruthy();
});

test("solo lectura: sin gestión de actos ni Eliminar; sin exportación ni pestañas", async () => {
  await abrir(fx.lector);
  expect(screen.getByText("Movimientos encontrados")).toBeTruthy();
  expect(screen.queryByText("🔗 Vincular / cambiar acto administrativo de uno o varios movimientos")).toBeNull();
  expect(screen.queryByText("Eliminar movimiento del historial")).toBeNull();
  expect(screen.queryByText(/Excel|CSV|Exportar|Descargar|Imprimir/)).toBeNull();
  expect(screen.queryAllByRole("tab")).toHaveLength(0);
});

test("sin movimientos: aviso certificado y nada más", async () => {
  await abrir({ ...fx.overview, filas: [] });
  expect(screen.getByText("Todavía no hay movimientos registrados.")).toBeTruthy();
  expect(screen.queryByPlaceholderText("Fecha, tipo, docente, CUIL, detalle, observaciones...")).toBeNull();
});
