// 6A-B3 (unidades académicas): en el Resumen docente las columnas "escuela" / "escuelas" se rotulan "Unidad académica" /
// "Unidades académicas" (en mayúsculas por el estilo de la tabla); la clave y el valor que llega del backend no cambian.
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";

import { OV, PERIODOS, PLANTEL, resumen, sec, tabla } from "./resumen-fixture";

beforeEach(() => {
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (url === "/api/docentes" && method === "GET") return new Response(JSON.stringify(OV), { status: 200 });
    if (url === "/api/docentes/plantel") return new Response(JSON.stringify(PLANTEL), { status: 200 });
    if (url === "/api/docentes/resumen" && method === "POST") {
      const r = resumen(JSON.parse(String(init?.body)).cuil, PERIODOS[0]);
      const s = r.secciones as unknown as Record<string, unknown>;
      s.comisiones = sec("Comisiones asignadas al docente — 2026-2", tabla(["asignatura", "carrera", "escuela"],
        ["Inútil I", "Ingeniería en Inutilidad", "Facultad de Pelotudismo"], ["Álgebra", "Analista", "Escuela de Ciencias Tecnológicas"]));
      s.materias_historicas = sec("Materias históricas del docente", tabla(["asignatura", "escuelas"],
        ["Inútil I", "Facultad de Pelotudismo | Escuela de Humanidades"]));
      return new Response(JSON.stringify(r), { status: 200 });
    }
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("encabezados genéricos de unidad académica y valores tal como los presenta el backend", async () => {
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("Plantel por período");
  fireEvent.click(screen.getByRole("tab", { name: /Resumen docente/ }));
  await screen.findByText("Facultad de Pelotudismo");
  const encabezados = screen.getAllByRole("columnheader").map((h) => h.textContent?.trim());
  expect(encabezados).toContain("Unidad académica");
  expect(encabezados).toContain("Unidades académicas");
  expect(encabezados).not.toContain("escuela");
  expect(encabezados).not.toContain("escuelas");
  const th = screen.getAllByRole("columnheader").find((h) => h.textContent?.trim() === "Unidad académica")!;
  expect(th.closest("thead")!.className).toContain("uppercase"); // se ve "UNIDAD ACADÉMICA"
  const tablaCom = th.closest("table")!;
  expect(within(tablaCom).getByText("Escuela de Ciencias Tecnológicas")).toBeTruthy();
  expect(screen.getByText("Facultad de Pelotudismo | Escuela de Humanidades")).toBeTruthy();
  expect(document.body.textContent).not.toMatch(/Escuela de (Facultad|Escuela|Instituto|Departamento)/);
});
