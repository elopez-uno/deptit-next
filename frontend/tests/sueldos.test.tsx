// Flujo REAL del módulo Sueldos (SueldosModule completo) con las respuestas reales de la API de NEXT para UNO,
// departamento 1 (fixtures generadas por backend/tests/tools_sueldos_frontend_fixtures.py con ROLLBACK). Las escrituras
// no llegan a ningún backend: se verifica el cuerpo exacto que enviaría la pantalla.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { SueldosModule } from "@/components/sueldos-module";
import type { Overview } from "@/lib/sueldos";

type Fx = Record<string, unknown> & { overview: Overview; lector: Overview; sin_departamento: Overview };
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "sueldos_uno.json"), "utf8"));

let overview: Overview;
let posts: { path: string; body: Record<string, unknown> }[] = [];
let escalasFx = "escalas";
let guardarResp: { status: number; data: unknown } = {
  status: 200,
  data: { mensaje: "Escala 10/2026 guardada correctamente.", tono: "success" },
};
const escrituras = () => posts.filter((p) => p.path === "escalas/guardar");

beforeEach(() => {
  overview = fx.overview;
  escalasFx = "escalas";
  posts = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
    if (url === "/api/sueldos" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/sueldos/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    posts.push({ path, body });
    if (path === "escalas") return ok(fx[escalasFx]);
    if (path === "tabla") return ok(body.dedicacion === "Exclusiva" ? fx.tabla_exclusiva : fx.tabla);
    if (path === "plantel") {
      const hist = overview.plantel.periodos?.find((p) => p.id === body.periodo_id)?.nombre === "2026-1";
      return ok(hist ? fx.plantel_hist : fx.plantel);
    }
    return ok(guardarResp.data, guardarResp.status);
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  guardarResp = { status: 200, data: { mensaje: "Escala 10/2026 guardada correctamente.", tono: "success" } };
});

async function abrir(tab?: string) {
  render(<SueldosModule onAuthError={() => {}} />);
  await screen.findByText("💰 Sueldos docentes");
  if (tab) fireEvent.click(screen.getByRole("tab", { name: tab }));
}

test("las 3 pestañas certificadas en orden, el aviso y la escala del mes actual con el histórico", async () => {
  await abrir();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "⚙️ Escalas básicas",
    "📈 Tabla salarial",
    "👥 Sueldos del plantel",
  ]);
  expect(document.body.textContent).toContain("Configurá el básico mensual de la dedicación Simple para cada cargo.");
  expect(screen.getByText("Simple").tagName).toBe("STRONG");
  expect(((await screen.findByLabelText("Titular — básico Simple")) as HTMLInputElement).value).toBe("487144.77");
  expect((screen.getByLabelText("Mes") as HTMLSelectElement).value).toBe("10");
  expect(screen.getByText("Histórico de escalas")).toBeTruthy();
  expect(screen.getAllByText("Inicial v256").length).toBe(6);
  expect(screen.getAllByText("$ 487.144,77").length).toBeGreaterThan(0);
  expect(screen.queryByText(/Excel|Importar|Exportar|Eliminar/i)).toBeNull();
});

test("guardar escala: cuerpo exacto (año, mes y los 6 básicos), sin usuario ni institución del cliente", async () => {
  await abrir();
  await screen.findByLabelText("JTP — básico Simple");
  fireEvent.change(screen.getByLabelText("JTP — básico Simple"), { target: { value: "330000.5" } });
  fireEvent.click(screen.getByRole("button", { name: /Guardar \/ actualizar escala mensual/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0].body).toEqual({
    anio: 2026,
    mes: 10,
    valores: {
      Titular: 487144.77,
      Asociado: 433482.17,
      Adjunto: 380014.62,
      JTP: 330000.5,
      "Ayudante 1ra": 272645.27,
      "Ayudante 2da": 218119.71,
    },
  });
  expect(await screen.findByText("Escala 10/2026 guardada correctamente.")).toBeTruthy();
});

test("error del writer: mensaje certificado 'No se pudo guardar la escala: …'", async () => {
  guardarResp = {
    status: 422,
    data: { error: { code: "REJECTED", message: "No se pudo guardar la escala: El básico de JTP debe ser mayor a cero." } },
  };
  await abrir();
  fireEvent.change(await screen.findByLabelText("JTP — básico Simple"), { target: { value: "0" } });
  fireEvent.click(screen.getByRole("button", { name: /Guardar \/ actualizar escala mensual/ }));
  expect(await screen.findByText("No se pudo guardar la escala: El básico de JTP debe ser mayor a cero.")).toBeTruthy();
});

test("solo lectura: botón deshabilitado con la ayuda certificada", async () => {
  overview = fx.lector;
  await abrir();
  const boton = await screen.findByRole("button", { name: /Guardar \/ actualizar escala mensual/ });
  expect((boton as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText("Tu rol permite visualizar, pero no cargar, editar ni generar cambios.")).toBeTruthy();
});

test("tabla salarial: escala, dedicación, posgrado y los 10 rangos de antigüedad", async () => {
  await abrir("📈 Tabla salarial");
  expect(await screen.findByText("$ 584.573,72")).toBeTruthy();
  expect(screen.getByText("24+ años")).toBeTruthy();
  fireEvent.change(screen.getByLabelText(/Dedicación/), { target: { value: "Exclusiva" } });
  await waitFor(() => expect(posts.some((p) => p.path === "tabla" && p.body.dedicacion === "Exclusiva")).toBe(true));
  expect(await screen.findByText(/Escala 06\/2026 · Exclusiva · Doctor/)).toBeTruthy();
  expect(screen.getByText(/Doctor \+18% del básico/)).toBeTruthy();
});

test("plantel: período abierto por defecto, métricas y tabla; histórico", async () => {
  await abrir("👥 Sueldos del plantel");
  expect((screen.getByLabelText("Período") as HTMLSelectElement).value).toBe("2026-2");
  expect(await screen.findByText("$ 58.835.756,12")).toBeTruthy();
  expect(screen.getByText("Total mensual estimado")).toBeTruthy();
  expect(screen.getByText(/No incorpora otros adicionales/)).toBeTruthy();
  fireEvent.change(screen.getByLabelText("Período"), { target: { value: "2026-1" } });
  expect(await screen.findByText("$ 72.511.781,78")).toBeTruthy();
});

test("institución sin departamentos: escalas institucionales y plantel con aviso de ámbito", async () => {
  overview = fx.sin_departamento;
  escalasFx = "escalas_sin_escala";
  await abrir();
  expect(await screen.findByText("Todavía no hay escalas salariales cargadas.")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "👥 Sueldos del plantel" }));
  expect(await screen.findByText(/Estás en el ámbito institucional/)).toBeTruthy();
});
