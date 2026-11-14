// Flujo REAL del submódulo "Plan de estudio" (MateriasModule completo) con las respuestas reales de la API de NEXT
// para la institución UNO (fixtures generadas por backend/tests/tools_materias_frontend_fixtures.py).
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { MateriasModule } from "@/components/materias-module";

type Fixtures = { overview: { escuelas: string[] }; plan: Record<string, unknown> };
const fx: Fixtures = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "materias_uno.json"), "utf8"));
const planKey = (b: { escuela: unknown; carrera_id: unknown }) =>
  JSON.stringify({ escuela: b.escuela, carrera_id: b.carrera_id ?? null });
const plan = new Map(Object.entries(fx.plan).map(([k, v]) => [planKey(JSON.parse(k)), v]));

let llamadas: { escuela: unknown; carrera_id: unknown }[] = [];
let demora: (body: { carrera_id: unknown }) => number = () => 0;

beforeEach(() => {
  llamadas = [];
  demora = () => 0;
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/materias") return ok(fx.overview);
    if (url === "/api/materias/plan") {
      const body = JSON.parse(String(init?.body));
      llamadas.push(body);
      await new Promise((r) => setTimeout(r, demora(body)));
      const resp = plan.get(planKey(body));
      if (!resp) throw new Error(`sin fixture para ${planKey(body)}`);
      return ok(resp);
    }
    throw new Error(`fetch inesperado: ${url}`);
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrirPlan() {
  render(<MateriasModule onAuthError={() => {}} />);
  fireEvent.click(await screen.findByRole("tab", { name: "Plan de estudio / Materias" }));
  return screen.findByRole("combobox", { name: "Carrera / plan" }, { timeout: 5000 });
}

function filasDeGrillas() {
  // cada cuadro por año es una tabla con encabezado "Orden"
  return screen
    .getAllByRole("table")
    .filter((t) => within(t).queryByRole("columnheader", { name: "Orden" }))
    .reduce((n, t) => n + within(t).getAllByRole("row").length - 1, 0);
}

async function esperarAbogacia() {
  await screen.findByRole("heading", { name: "Abogacía" }, { timeout: 5000 });
  await waitFor(() => expect(filasDeGrillas()).toBe(47), { timeout: 5000 });
}

test("UNO → seleccionar Abogacía (46) muestra las 47 materias en los cuadros por año", async () => {
  const select = await abrirPlan();
  await waitFor(() => expect(llamadas.length).toBeGreaterThan(0));
  await act(async () => fireEvent.change(select, { target: { value: "46" } }));
  await esperarAbogacia();
  expect(llamadas.at(-1)).toEqual({ escuela: "Todas", carrera_id: 46 });
  expect(screen.getByText("Materias del plan").nextSibling?.textContent).toBe("47");
  expect(screen.queryByText("Esta carrera todavía no tiene materias cargadas.")).toBeNull();
});

test("filtro de Unidad académica de Abogacía y luego selección", async () => {
  await abrirPlan();
  const escuela = fx.overview.escuelas.find((e) => e.includes("Jurídicas"))!;
  fireEvent.change(screen.getByRole("combobox", { name: "Unidad académica" }), { target: { value: escuela } });
  await waitFor(() => expect(llamadas.at(-1)?.escuela).toBe(escuela), { timeout: 5000 });
  const select = await screen.findByRole("combobox", { name: "Carrera / plan" });
  await waitFor(() => expect((select as HTMLSelectElement).options.length).toBe(2), { timeout: 5000 });
  await act(async () => fireEvent.change(select, { target: { value: "46" } }));
  await esperarAbogacia();
});

test("respuestas fuera de orden: la anterior llega tarde y no pisa a Abogacía", async () => {
  const select = await abrirPlan();
  await waitFor(() => expect(llamadas.length).toBeGreaterThan(0));
  demora = (b) => (b.carrera_id === 46 ? 0 : 800);
  await act(async () => fireEvent.change(select, { target: { value: "47" } }));
  await new Promise((r) => setTimeout(r, 300));
  await act(async () => fireEvent.change(select, { target: { value: "46" } }));
  await esperarAbogacia();
  await new Promise((r) => setTimeout(r, 1000));
  expect(filasDeGrillas()).toBe(47);
});
