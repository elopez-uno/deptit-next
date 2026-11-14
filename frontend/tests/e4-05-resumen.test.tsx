// E4-05: pestaña "📊 Resumen docente". Datos SINTÉTICOS con la forma exacta de POST /docentes/resumen (el contenido real
// lo cubre el diferencial del backend, sección por sección). La pantalla solo dibuja lo que transcribe el backend.
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";

import { OV, PERIODOS, PLANTEL, resumen } from "./resumen-fixture";

let cuerpos: { cuil: string; periodo_id: number | null }[];
let fallar: boolean;

beforeEach(() => {
  cuerpos = [];
  fallar = false;
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (url === "/api/docentes" && method === "GET") return new Response(JSON.stringify(OV), { status: 200 });
    if (url === "/api/docentes/plantel") return new Response(JSON.stringify(PLANTEL), { status: 200 });
    if (url === "/api/docentes/resumen" && method === "POST") {
      const b = JSON.parse(String(init?.body));
      cuerpos.push(b);
      if (fallar) return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "El docente seleccionado no figura en el departamento." } }), { status: 404 });
      const p = PERIODOS.find((x) => x.id === b.periodo_id) ?? PERIODOS[0];
      return new Response(JSON.stringify(resumen(b.cuil, p)), { status: 200 });
    }
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir() {
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("Plantel por período");
  const tab = screen.getByRole("tab", { name: /Resumen docente/ });
  expect(within(screen.getByRole("tablist")).queryByText("Pendiente")).toBeNull();
  fireEvent.click(tab);
  await screen.findByText("Resumen individual del docente");
}

test("abre con el primer docente y el período por defecto; dibuja las 13 secciones de lectura y la sección de consulta (E4-06)", async () => {
  await abrir();
  await screen.findByText("👤 Uno, Docente");
  expect(cuerpos[0]).toEqual({ cuil: "20-00000001-1", periodo_id: null });
  expect((screen.getByRole("combobox") as HTMLSelectElement).value).toBe("2026-2");
  for (const t of ["Datos generales", "Resumen actual del período — 2026-2", "Designaciones institucionales del docente — 2026-2",
    "📄 Resoluciones, disposiciones y actos administrativos", "💰 Sueldo estimado — 2026-2", "Investigación del docente — 2026-2",
    "Extensión del docente — 2026-2", "Actividades Especiales del docente — 2026-2", "Comisiones asignadas al docente — 2026-2",
    "Cronograma semanal — 2026-2", "Alertas de superposición — 2026-2", "Productividad del período — 2026-2", "Materias históricas del docente"])
    expect(screen.getByRole("heading", { name: t })).toBeTruthy();
  // tarjeta: rótulos y valores del bloque certificado
  expect(screen.getByText("Cargo/s por departamento")).toBeTruthy();
  expect(screen.getAllByText("+10 hs").length).toBe(2);
  expect(screen.getByText("🧩 DOCENTE COMPARTIDO: tiene designaciones en más de un departamento para este período.")).toBeTruthy();
  // sueldo como ESTIMACIÓN (D-E4-02) con su total
  expect(screen.getByText("ESTIMACIÓN")).toBeTruthy();
  expect(screen.getAllByText("$ 584.573,72").length).toBeGreaterThanOrEqual(2);
  // cronograma: celda ocupada con el título exacto (tooltip) y vacíos
  expect(screen.getByTitle("Álgebra · 08:00–10:00 · Dep A")).toBeTruthy();
  // superposiciones con aviso, métricas, detalle de no lectivas y mensaje sin torta
  expect(screen.getByText("Este docente tiene superposiciones horarias entre sus comisiones.")).toBeTruthy();
  expect(screen.getByText("75%")).toBeTruthy();
  expect(screen.getByText("Ver cálculo de horas no lectivas por comisión / departamento")).toBeTruthy();
  expect(screen.getByText("No hay horas contratadas ni horas asignadas para graficar productividad.")).toBeTruthy();
  // vacíos certificados
  expect(screen.getByText("No hay resoluciones, disposiciones u otros actos administrativos vinculados a este docente.")).toBeTruthy();
  // E4-06 habilitó la sección: su detalle lo cubre e4-06-consulta.test.tsx
  expect(screen.getByRole("heading", { name: "Mensaje para consultar la designación — 2026-2" })).toBeTruthy();
  expect(screen.queryByText(/se habilitarán en la integración E4-06/)).toBeNull();
  expect(screen.getByRole("button", { name: "💾 Guardar estado de la consulta" })).toBeTruthy();
});

test("buscar, elegir otro docente y otro período pide ese cuil y ese id; sin coincidencias muestra el aviso", async () => {
  await abrir();
  await screen.findByText("👤 Uno, Docente");
  fireEvent.click(screen.getByText("Dos, Docente"));
  await screen.findByText("👤 Dos, Docente");
  expect(cuerpos.at(-1)).toEqual({ cuil: "20-00000002-2", periodo_id: null });
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "2026-1" } });
  await screen.findByRole("heading", { name: "Cronograma semanal — 2026-1" });
  expect(cuerpos.at(-1)).toEqual({ cuil: "20-00000002-2", periodo_id: 5 });
  fireEvent.change(screen.getByPlaceholderText("Nombre, CUIL, legajo o título"), { target: { value: "zzzz" } });
  expect(await screen.findByText("No hay docentes que coincidan con la búsqueda.")).toBeTruthy();
});

test("falla de la lectura: mensaje del backend", async () => {
  fallar = true;
  await abrir();
  await waitFor(() => expect(screen.getByText("El docente seleccionado no figura en el departamento.")).toBeTruthy());
});
