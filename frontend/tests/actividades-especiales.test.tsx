// Flujo REAL del módulo Actividades Especiales (ActividadesEspecialesModule completo) con las respuestas reales de la API
// de NEXT para UNO, departamento 1 (fixtures generadas por backend/tests/tools_actividades_frontend_fixtures.py con
// ROLLBACK). Las escrituras no llegan a ningún backend: se verifica el cuerpo exacto que enviaría la pantalla.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ActividadesEspecialesModule } from "@/components/actividades-especiales-module";
import type { Overview } from "@/lib/actividades-especiales";

type Fx = Record<string, unknown> & { overview: Overview; super: Overview; lector: Overview };
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "actividades_especiales_uno.json"), "utf8"));
const RUTAS: Record<string, string> = {
  periodo: "periodo",
  "asignar/datos": "asignar_datos",
  historial: "historial",
  "editar/actividades": "editar_actividades",
  "editar/participaciones": "participaciones",
};

let overview: Overview;
let posts: { path: string; body: Record<string, unknown> }[] = [];
const escrituras = () => posts.filter((p) => !(p.path in RUTAS));

beforeEach(() => {
  overview = fx.overview;
  posts = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/actividades-especiales" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/actividades-especiales/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    posts.push({ path, body });
    if (path in RUTAS) return ok(fx[RUTAS[path]]);
    return ok({ mensaje: "Participaciones registradas: 1.", tono: "success", avisos: ["20-1-0: El docente ya está asignado a esta actividad."] });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(tab?: string) {
  render(<ActividadesEspecialesModule onAuthError={() => {}} />);
  await screen.findByText("⭐ Actividades Especiales");
  if (tab) fireEvent.click(screen.getByRole("tab", { name: tab }));
}

test("las 5 pestañas certificadas en orden, el aviso de horas y las actividades del período", async () => {
  await abrir();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "📚 Actividades del período",
    "➕ Nueva actividad",
    "👥 Asignar docentes",
    "🕘 Historial",
    "✏️ Editar / eliminar",
  ]);
  expect(screen.getByText(/no consumen horas de dedicación/)).toBeTruthy();
  await screen.findByText("Participaciones docentes");
  expect(screen.queryByText(/Excel|Costo|horas semanales/i)).toBeNull();
});

test("nueva actividad: cuerpo exacto con el período y la huella", async () => {
  await abrir("➕ Nueva actividad");
  fireEvent.change(screen.getByLabelText("Título de la actividad"), { target: { value: "ZZNEXT front" } });
  fireEvent.click(screen.getByRole("button", { name: /Crear Actividad Especial/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({
    path: "crear",
    body: { periodo_id: overview.abierto!.id, titulo: "ZZNEXT front", descripcion: "", observaciones: "", huella_periodos: overview.huella_periodos },
  });
});

test("asignar docentes: actividad, docentes con rol y avisos por cada error", async () => {
  await abrir("👥 Asignar docentes");
  fireEvent.click((await screen.findAllByLabelText("Seleccionar fila"))[0]);
  const datos = fx.asignar_datos as { actividades: { id: number; huella: string }[]; docentes: { etiqueta: string; cuil: string }[] };
  fireEvent.click(await screen.findByLabelText(datos.docentes[0].etiqueta));
  fireEvent.change(screen.getByLabelText("Rol en la actividad"), { target: { value: "Coordinadora" } });
  fireEvent.click(screen.getByRole("button", { name: /Guardar participaciones/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0].body).toEqual({
    periodo_id: overview.abierto!.id,
    actividad_id: datos.actividades[0].id,
    huella: datos.actividades[0].huella,
    docentes: [{ cuil: datos.docentes[0].cuil, rol: "Coordinadora", observaciones: "" }],
  });
  expect(await screen.findByText(/El docente ya está asignado a esta actividad/)).toBeTruthy();
});

test("editar: estados certificados; usuario de departamento sin eliminaciones", async () => {
  await abrir("✏️ Editar / eliminar");
  fireEvent.click((await screen.findAllByLabelText("Seleccionar fila"))[0]);
  const estado = (await screen.findByLabelText("Estado")) as HTMLSelectElement;
  expect([...estado.options].map((o) => o.value)).toEqual(["Activa", "Finalizada", "Suspendida"]);
  fireEvent.change(screen.getByLabelText("Título"), { target: { value: "" } });
  fireEvent.click(screen.getByRole("button", { name: /Guardar cambios de la actividad/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0].path).toBe("editar");
  expect(escrituras()[0].body.titulo).toBe("");
  await screen.findByText("Participaciones encontradas", {}, { timeout: 3000 });
  expect(screen.getAllByText("La eliminación por error está reservada al rol superadmin.").length).toBe(2);
  expect(screen.queryByRole("button", { name: /Eliminar actividad/ })).toBeNull();
});

test("superadmin: quitar participación sin confirmación y eliminar actividad con casilla", async () => {
  overview = fx.super;
  await abrir("✏️ Editar / eliminar");
  fireEvent.click((await screen.findAllByLabelText("Seleccionar fila"))[0]);
  await screen.findByText("Participaciones encontradas", {}, { timeout: 3000 });
  const boton = screen.getByRole("button", { name: /Eliminar participación por error/ });
  expect((boton as HTMLButtonElement).disabled).toBe(true);
  const radios = screen.getAllByLabelText("Seleccionar fila");
  fireEvent.click(radios[radios.length - 1]);
  await waitFor(() => expect((boton as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(boton);
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0].path).toBe("editar/quitar-participacion");
  expect(screen.getByLabelText("Confirmo que esta actividad fue cargada por error")).toBeTruthy();
});

test("solo lectura: sin botones de escritura", async () => {
  overview = fx.lector;
  await abrir("➕ Nueva actividad");
  expect(screen.getAllByText("Tu rol permite consultar esta pestaña, pero no registrar cambios.").length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: /Crear Actividad Especial/ })).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "🕘 Historial" }));
  expect(within(screen.getByRole("tabpanel")).getByText("Historial de Actividades Especiales")).toBeTruthy();
});
