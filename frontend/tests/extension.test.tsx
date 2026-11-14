// Flujo REAL del módulo Extensión (ExtensionModule completo) con las respuestas reales de la API de NEXT para
// UNO, departamento 2 (fixtures generadas por backend/tests/tools_extension_frontend_fixtures.py con ROLLBACK).
// Las escrituras no llegan a ningún backend: se verifica el cuerpo exacto que enviaría la pantalla.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ExtensionModule } from "@/components/extension-module";
import type { Overview } from "@/lib/extension";

type Fx = Record<string, unknown> & { overview: Overview; lector: Overview };
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "extension_uno.json"), "utf8"));
const RUTAS: Record<string, string> = {
  vigentes: "vigentes",
  "vigentes/ficha": "ficha",
  historial: "historial",
  "asignar/proyectos": "asignar_proyectos",
  "asignar/detalle": "asignar_detalle",
  asignaciones: "asignaciones",
  "editar/proyectos": "editar_proyectos",
  "editar/asignaciones": "editar_asignaciones",
  "editar/asignacion/opciones": "opciones",
  "bajas/suspender/proyectos": "suspender",
  "bajas/archivar/proyectos": "archivar",
  actos: "actos",
  alertas: "alertas",
};

let overview: Overview;
let posts: { path: string; body: Record<string, unknown> }[] = [];
const escrituras = () =>
  posts.filter((p) => !(p.path in RUTAS) && p.path !== "capacidad" && p.path !== "post-accion" && p.path !== "costos");

beforeEach(() => {
  overview = fx.overview;
  posts = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/extension" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/extension/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    posts.push({ path, body });
    if (path in RUTAS) return ok(fx[RUTAS[path]]);
    // E4-04: costos de Proyectos vigentes (el detalle con montos lo cubre e4-04-costos.test.tsx).
    if (path === "costos") return ok({ estimacion: { etiqueta: "ESTIMACIÓN", advertencia: "" }, proyectos: [], integrantes: [], sin_costo: "$ 0,00" });
    if (path === "capacidad") {
      const caps = Object.fromEntries(
        (body.cuiles as string[]).map((c) => [c, { horas_disponibles_proyectos: 2, capacidad_total_proyectos: 4, mensaje: "Horas contratadas: 10 hs" }])
      );
      return ok({ capacidades: caps });
    }
    return ok({ mensaje: "OK (respuesta simulada del test)", tono: "success" });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(tab?: string) {
  render(<ExtensionModule onAuthError={() => {}} />);
  await screen.findByText("🤝 Extensión");
  if (tab) fireEvent.click(screen.getByRole("tab", { name: tab }));
}

test("las 8 pestañas certificadas en orden y la ficha ya sin costo pendiente de Sueldos (E4-04)", async () => {
  await abrir();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "📚 Proyectos vigentes",
    "➕ Nuevo proyecto",
    "👥 Asignar docentes",
    "📋 Asignaciones",
    "🕘 Historial",
    "✏️ Editar",
    "⏸️ Bajas, suspensión, archivo y eliminación",
    "📥 Carga rápida",
  ]);
  await screen.findByText("📌 Datos del proyecto");
  // E4-04 reabrió el bloque: el costo salarial ya no está pendiente de Sueldos.
  expect(screen.queryByText("Pendiente de Sueldos")).toBeNull();
});

test("alta de proyecto: cuerpo exacto y sin crear actos nuevos", async () => {
  await abrir("➕ Nuevo proyecto");
  await screen.findByText("Registrar nuevo proyecto institucional");
  // E4-04 quitó el texto obsoleto (Resoluciones y respaldos ya está cerrado; el certificado no lo tiene).
  expect((await screen.findAllByText(/Buscá un documento ya cargado/)).length).toBeGreaterThan(0);
  expect(screen.queryByText(/pendiente de migración/)).toBeNull();
  const nombre = screen.getByLabelText("Nombre del proyecto");
  fireEvent.change(nombre, { target: { value: "ZZNEXT front" } });
  fireEvent.click(screen.getByRole("button", { name: "💾 Guardar proyecto" }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const w = escrituras()[0];
  expect(w.path).toBe("proyecto/guardar");
  expect(w.body).toMatchObject({ nombre: "ZZNEXT front", estado: "Activo", documento_id: null });
});

test("asignar docentes: una sola acción con huellas y la configuración por docente", async () => {
  await abrir("👥 Asignar docentes");
  await screen.findByText("Docentes asignados hasta el momento");
  const check = (await screen.findAllByLabelText("Seleccionar"))[0];
  fireEvent.click(check);
  const rol = await screen.findByLabelText("Rol del docente en el proyecto");
  fireEvent.change(rol, { target: { value: "Directora" } });
  fireEvent.change(screen.getByLabelText(/^Horas semanales asignadas al docente/), { target: { value: "2.5" } });
  expect(await screen.findByText(/quedan 2 hs disponibles/)).toBeTruthy();
  fireEvent.click(screen.getByRole("button", { name: /Asignar 1 docente\/s al proyecto/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const w = escrituras()[0];
  const det = fx.asignar_detalle as { huella_integrantes: string; docentes: { cuil: string }[] };
  expect(w.path).toBe("asignar");
  expect(w.body).toMatchObject({ huella_integrantes: det.huella_integrantes, huella_periodo: overview.huella_periodo });
  expect(w.body.docentes).toEqual([{ cuil: det.docentes[0].cuil, rol: "Directora", horas: 2.5, observaciones: "" }]);
});

test("editar asignación: envía la etiqueta del selector de docente", async () => {
  await abrir("✏️ Editar");
  fireEvent.click(await screen.findByLabelText("Asignación de un docente"));
  const radios = await screen.findAllByLabelText("Seleccionar fila");
  fireEvent.click(radios[0]);
  const boton = await screen.findByRole("button", { name: "💾 Guardar cambios de la asignación" });
  fireEvent.click(boton);
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const w = escrituras()[0];
  const opc = fx.opciones as { docentes: { etiqueta: string; actual: boolean }[] };
  expect(w.path).toBe("editar/asignacion");
  expect(w.body.docente_etiqueta).toBe(opc.docentes.find((d) => d.actual)!.etiqueta);
});

test("solo lectura: no ofrece escrituras ni eliminación definitiva", async () => {
  overview = fx.lector;
  await abrir("⏸️ Bajas, suspensión, archivo y eliminación");
  fireEvent.click(screen.getByLabelText("Eliminar definitivamente un proyecto"));
  expect(screen.getAllByText("Tu rol permite consultar esta pestaña, pero no registrar cambios.").length).toBeGreaterThan(0);
  expect(screen.queryByRole("button", { name: "🗑️ Eliminar definitivamente" })).toBeNull();
});

test("carga rápida: descarga del modelo integral", async () => {
  await abrir("📥 Carga rápida");
  expect(await screen.findByRole("button", { name: /Descargar Excel integral de proyectos y docentes de extensión/ })).toBeTruthy();
  expect(within(screen.getByRole("tabpanel")).getByText(/Subir Excel completo/)).toBeTruthy();
});

test("propio de Extensión: 1 hora por defecto, sin la ayuda de 0 hs y rótulos Área/Secretaría", async () => {
  await abrir("👥 Asignar docentes");
  await screen.findByText("Docentes asignados hasta el momento");
  fireEvent.click((await screen.findAllByLabelText("Seleccionar"))[0]);
  const horas = (await screen.findByLabelText(/^Horas semanales asignadas al docente/)) as HTMLInputElement;
  expect(horas.value).toBe("1");
  expect(screen.getByText(/Investigación permite 0 hs; en Extensión las horas deben ser mayores a 0\./)).toBeTruthy();
  expect(screen.queryByText(/Se permiten 0 hs/)).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Asignar 1 docente\/s al proyecto/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect((escrituras()[0].body.docentes as { horas: number }[])[0].horas).toBe(1);
  cleanup();
  await abrir("➕ Nuevo proyecto");
  expect(await screen.findByLabelText(/^Área\/Secretaría\/Instituto\/Departamento de radicación/)).toBeTruthy();
});
