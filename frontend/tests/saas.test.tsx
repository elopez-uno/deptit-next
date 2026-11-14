// Flujo del módulo Administración SaaS (SaasModule completo) con respuestas con la forma real de GET /saas y de los POST
// por acción (datos SINTÉTICOS; textos y catálogos = fixture generada desde saas/textos.py del backend). Verifica las
// 5 pestañas, las tablas sin columnas técnicas, los formularios con sus esquemas exactos (sin campos extra), el Excel,
// las confirmaciones, que eliminar institución/departamento con datos queda DESHABILITADO con explicación (D-AP1/D-AP2),
// que las escrituras esperan la respuesta y luego releen, y los errores del backend.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { SaasModule } from "@/components/saas-module";
import type { Overview } from "@/lib/saas";
import fixture from "./fixtures/saas_ui.json";

const t = (columnas: string[], filas: (string | number | null)[][]) => ({ columnas, filas });
const ficha = (cols: string[], fila: (string | number | null)[]) => t(cols, [fila]);
const dep0 = { usuarios: 0, departamentos: 0, registros: 0, tablas: 0 };

const OVERVIEW = {
  ...fixture,
  actor_id: 1,
  tablas: {
    instituciones: t(["id", "nombre", "max_usuarios", "estado"], [[10, "Instituto Alfa", 5, "Activa"], [20, "Instituto Beta", 3, "Bloqueada"], [30, "Instituto Vacío", 5, "Activa"]]),
    departamentos: t(["id", "institucion_id", "nombre", "estado", "observaciones", "institucion"], [[100, 10, "Depto Uno", "Activo", null, "Instituto Alfa"]]),
    usuarios: t(["id", "nombre", "email", "rol", "estado"], [[1, "Admin Prueba", "admin@prueba.test", "superadmin", "Activo"], [2, "Usuaria Prueba", "usuaria@prueba.test", "usuario_departamento", "Activo"]]),
    uso: t(["Institución", "Plan", "Uso cupo"], [["Instituto Alfa", "Institucional", "1/5"]]),
  },
  instituciones: [
    { id: 10, nombre: "Instituto Alfa", estado: "Activa", plan: "Institucional", max_usuarios: 5, fecha_vencimiento: null, estado_pago: "Activo", suscripcion: "Activa", observaciones: null, activos: 1, dependencias: { usuarios: 1, departamentos: 1, registros: 40, tablas: 3 }, eliminable: false, ficha: ficha(["id", "nombre"], [10, "Instituto Alfa"]) },
    { id: 20, nombre: "Instituto Beta", estado: "Bloqueada", plan: "Prueba", max_usuarios: 3, fecha_vencimiento: "2027-01-31", estado_pago: "Pendiente", suscripcion: "Prueba", observaciones: "x", activos: 0, dependencias: dep0, eliminable: true, ficha: ficha(["id", "nombre"], [20, "Instituto Beta"]) },
    { id: 30, nombre: "Instituto Vacío", estado: "Activa", plan: "Institucional", max_usuarios: 5, fecha_vencimiento: null, estado_pago: "Activo", suscripcion: "Activa", observaciones: null, activos: 0, dependencias: dep0, eliminable: true, ficha: ficha(["id", "nombre"], [30, "Instituto Vacío"]) },
  ],
  departamentos: [
    { id: 100, institucion_id: 10, institucion: "Instituto Alfa", nombre: "Depto Uno", estado: "Activo", observaciones: null, usuarios: 1, dependencias: { usuarios: 1, departamentos: 0, registros: 12, tablas: 2 }, eliminable: false, ficha: ficha(["id", "nombre"], [100, "Depto Uno"]) },
  ],
  usuarios: [
    { id: 1, institucion_id: null, departamento_id: null, nombre: "Admin Prueba", email: "admin@prueba.test", rol: "superadmin", estado: "Activo", observaciones: null, etiqueta: "admin@prueba.test - superadmin - Activo", ficha: ficha(["id", "email"], [1, "admin@prueba.test"]) },
    { id: 2, institucion_id: 10, departamento_id: 100, nombre: "Usuaria Prueba", email: "usuaria@prueba.test", rol: "usuario_departamento", estado: "Activo", observaciones: null, etiqueta: "usuaria@prueba.test - usuario_departamento - Activo", ficha: ficha(["id", "email"], [2, "usuaria@prueba.test"]) },
  ],
} as unknown as Overview;

let llamadas: { url: string; body: Record<string, unknown> | null }[] = [];
let descargas: string[] = [];
let respuesta: Record<string, { status: number; body: unknown }> = {};

beforeEach(() => {
  llamadas = [];
  descargas = [];
  respuesta = {};
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) {
    descargas.push(this.download);
  });
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const body = init?.body ? JSON.parse(String(init.body)) : null;
    llamadas.push({ url, body });
    expect(url.startsWith("/api/saas")).toBe(true);
    if (body) expect(JSON.stringify(body)).not.toMatch(/salt|password_hash|sqlite_id|source_db/);
    if (respuesta[url]) return new Response(JSON.stringify(respuesta[url].body), { status: respuesta[url].status });
    if (url === "/api/saas") return new Response(JSON.stringify(OVERVIEW), { status: 200 });
    if (url === "/api/saas/planes") return new Response(JSON.stringify({ metricas: [{ label: "Carreras", valor: "3" }, { label: "Materias", valor: "40" }, { label: "Estado", valor: "OK" }], aviso: null }), { status: 200 });
    if (url === "/api/saas/descargas/excel") return new Response(new Blob(["PK"]), { status: 200, headers: { "content-disposition": "attachment; filename=\"Administracion_SaaS_20261030_101500.xlsx\"; filename*=UTF-8''Administraci%C3%B3n_SaaS_20261030_101500.xlsx" } });
    return new Response(JSON.stringify({ mensaje: "Hecho.", tono: "success" }), { status: 200 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function abrir() {
  render(<SaasModule onAuthError={() => {}} />);
  await screen.findByText("⚙️ Administración SaaS");
}

function expander(titulo: string) {
  const d = screen.getByText(titulo, { selector: "summary" }).closest("details") as HTMLDetailsElement;
  d.open = true;
  return within(d);
}

test("5 pestañas certificadas; tablas sin columnas técnicas; Excel de la tabla con el nombre del backend", async () => {
  await abrir();
  expect(screen.getAllByRole("tab").map((b) => b.textContent)).toEqual(["Instituciones", "Departamentos", "Usuarios", "Suscripción / Comercial", "Credenciales iniciales"]);
  const tabla = screen.getByRole("table", { name: "Instituciones" });
  expect(tabla.textContent).not.toMatch(/sqlite_id|source_db|slug/);
  fireEvent.click(screen.getAllByText("📥 Descargar tabla en Excel")[0]);
  await waitFor(() => expect(descargas).toEqual(["Administración_SaaS_20261030_101500.xlsx"]));
  expect(llamadas.at(-1)).toEqual({ url: "/api/saas/descargas/excel", body: { tabla: "instituciones", id: null } });
});

test("crear institución envía el esquema exacto, espera la respuesta y relee", async () => {
  await abrir();
  const crear = expander("Crear institución");
  fireEvent.change(crear.getAllByRole("textbox")[0], { target: { value: "Instituto Nuevo" } });
  fireEvent.click(crear.getByRole("button", { name: "Crear institución" }));
  await screen.findByText("Hecho.");
  const post = llamadas.find((l) => l.url === "/api/saas/instituciones");
  expect(post?.body).toEqual({ nombre: "Instituto Nuevo", max_usuarios: 5, plan: "Institucional", fecha_vencimiento: null, estado_pago: "Activo", suscripcion: "Activa", estado: "Activa", observaciones: "" });
  expect(llamadas.filter((l) => l.url === "/api/saas")).toHaveLength(2); // relectura tras el éxito
});

test("eliminar institución: con datos queda deshabilitado con explicación; vacía exige casilla + ELIMINAR", async () => {
  await abrir();
  const del = expander("Eliminar institución");
  expect(del.getByText(/elimina definitivamente una institución VACÍA/)).toBeTruthy();
  expect(del.getByText(/contiene datos y no puede eliminarse \(1 usuario\(s\), 1 departamento\(s\), 40 registro\(s\) en 3 tabla\(s\)\)/)).toBeTruthy();
  expect((del.getByRole("button", { name: "🗑️ Eliminar institución" }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(del.getAllByRole("combobox")[0], { target: { value: "30" } });
  const boton = del.getByRole("button", { name: "🗑️ Eliminar institución" }) as HTMLButtonElement;
  expect(boton.disabled).toBe(true);
  fireEvent.click(del.getByRole("checkbox"));
  fireEvent.change(del.getByRole("textbox"), { target: { value: "eliminar" } });
  expect(boton.disabled).toBe(false);
  fireEvent.click(boton);
  await screen.findByText("Hecho.");
  expect(llamadas.find((l) => l.url === "/api/saas/instituciones/eliminar")?.body).toEqual({ institucion_id: 30, confirmado: true, texto: "eliminar" });
});

test("departamentos: métricas del diagnóstico sin rutas; eliminar con usuarios deshabilitado", async () => {
  await abrir();
  fireEvent.click(screen.getByRole("tab", { name: "Departamentos" }));
  await waitFor(() => expect(screen.getAllByTestId("metrica")).toHaveLength(3));
  expect(document.body.textContent).not.toMatch(/Archivo usado|Base local|\.db/);
  const del = expander("Eliminar departamento");
  expect(del.getByText("Usuarios asignados: 1.")).toBeTruthy();
  expect(del.getByText(/No se puede eliminar porque tiene usuarios asignados/)).toBeTruthy();
  fireEvent.click(del.getByRole("checkbox"));
  expect((del.getByRole("button", { name: "🗑️ Eliminar departamento" }) as HTMLButtonElement).disabled).toBe(true);
});

test("usuarios: alta con departamento de la institución, error del backend visible y sin eco de la contraseña", async () => {
  respuesta["/api/saas/usuarios"] = { status: 422, body: { error: { code: "REJECTED", message: "No se pudo crear el usuario: La institución ya alcanzó el cupo de 5 usuarios activos." } } };
  await abrir();
  fireEvent.click(screen.getByRole("tab", { name: "Usuarios" }));
  const crear = expander("Crear usuario");
  const combos = crear.getAllByRole("combobox");
  expect(Array.from((combos[0] as HTMLSelectElement).options).map((o) => o.textContent)).toEqual(["Instituto Alfa", "Instituto Vacío"]); // solo Activas
  fireEvent.change(combos[2], { target: { value: "100" } });
  const textos = crear.getAllByRole("textbox");
  fireEvent.change(textos[1], { target: { value: "nueva@prueba.test" } });
  const claves = (screen.getByText("Crear usuario", { selector: "summary" }).closest("details") as HTMLElement).querySelectorAll('input[type="password"]');
  fireEvent.change(claves[0], { target: { value: "clave-sintetica-larga" } });
  fireEvent.change(claves[1], { target: { value: "clave-sintetica-larga" } });
  fireEvent.click(crear.getByRole("button", { name: "Crear usuario" }));
  await screen.findByText(/alcanzó el cupo de 5 usuarios activos/);
  const post = llamadas.find((l) => l.url === "/api/saas/usuarios");
  expect(Object.keys(post?.body ?? {}).sort()).toEqual(["departamento_id", "email", "estado", "institucion_id", "nombre", "observaciones", "password", "password_confirmacion", "rol"]);
  expect(post?.body?.departamento_id).toBe(100);
  expect(document.body.textContent).not.toContain("clave-sintetica-larga");
});

test("eliminar usuario exige confirmación explícita", async () => {
  await abrir();
  fireEvent.click(screen.getByRole("tab", { name: "Usuarios" }));
  const del = expander("Eliminar usuario");
  const boton = del.getByRole("button", { name: "🗑️ Eliminar usuario" }) as HTMLButtonElement;
  expect(boton.disabled).toBe(true);
  fireEvent.change(del.getByRole("combobox"), { target: { value: "2" } });
  fireEvent.click(del.getByRole("checkbox"));
  fireEvent.click(boton);
  await screen.findByText("Hecho.");
  expect(llamadas.find((l) => l.url === "/api/saas/usuarios/eliminar")?.body).toEqual({ usuario_id: 2, confirmado: true });
});

test("comercial: tablero de uso, bloquear y criterio de acceso; credenciales sin tooling", async () => {
  await abrir();
  fireEvent.click(screen.getByRole("tab", { name: "Suscripción / Comercial" }));
  expect(screen.getByRole("table", { name: "Suscripción / Comercial" }).textContent).toContain("1/5");
  const ed = expander("Editar plan, vencimiento, pago y acceso");
  fireEvent.click(ed.getByRole("button", { name: "Bloquear institución" }));
  await screen.findByText("Hecho.");
  expect(llamadas.find((l) => l.url === "/api/saas/instituciones/bloquear")?.body).toEqual({ institucion_id: 10 });
  fireEvent.click(screen.getByRole("tab", { name: "Credenciales iniciales" }));
  expect(document.body.textContent).toContain("Ya no existen credenciales iniciales.");
  expect(document.body.textContent).not.toContain("tools/");
});

test("rol sin acceso: muestra el mensaje del backend", async () => {
  vi.stubGlobal("fetch", async () => new Response(JSON.stringify({ error: { code: "DENIED", message: "Solo el superadmin puede administrar instituciones, cupos y usuarios." } }), { status: 403 }));
  render(<SaasModule onAuthError={() => {}} />);
  await screen.findByText("Solo el superadmin puede administrar instituciones, cupos y usuarios.");
});
