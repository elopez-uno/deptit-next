// E4-04: costos salariales de "📚 Proyectos vigentes" en Investigación y Extensión. Vigentes y ficha son las respuestas
// reales de la API (fixtures de cada bloque); POST /costos es SINTÉTICO con la forma exacta de la composición (los montos
// reales los cubre el diferencial del backend). La pantalla solo cruza por id: no calcula nada.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { ExtensionModule } from "@/components/extension-module";
import { InvestigacionModule } from "@/components/investigacion-module";
import type { Costos } from "@/lib/investigacion";

type Fx = Record<string, unknown> & {
  overview: unknown;
  vigentes: { filas: { id: number }[]; lista: Record<string, unknown>[] };
  ficha: { proyecto_id: number; integrantes: Record<string, unknown>[] };
};
const ADVERTENCIA = "Los costos son una estimación: usan la lógica salarial certificada y pueden no contemplar todos los conceptos.";
const LEYENDA =
  "Las horas totales se calculan como horas semanales × semanas comprendidas entre la fecha de inicio y la fecha de " +
  "finalización del proyecto. El costo total salarial usa como base la escala 06/2026, prorratea el sueldo según horas " +
  "asignadas / horas contractuales rentadas y proyecta ese importe por los 24 meses de ejecución del proyecto. Las " +
  "designaciones Ad Honorem imputan $0.";

const MODULOS = [
  { mod: "investigacion", Comp: InvestigacionModule, titulo: "🔬 Investigación" },
  { mod: "extension", Comp: ExtensionModule, titulo: "🤝 Extensión" },
] as const;

function datos(mod: string) {
  const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", `${mod}_uno.json`), "utf8"));
  // la ficha real con dos integrantes: el primero con costo imputado, el segundo sin fila en el detalle
  const base = fx.ficha.integrantes[0] ?? { docente: "Docente, Uno", cuil: "20-00000000-1", departamento: "Dep", rol: "Integrante", horas: "10", observaciones: "" };
  const ficha = { ...fx.ficha, periodo_activo: "2026-2", integrantes: [{ ...base, id: 501 }, { ...base, docente: "Docente, Sin costo", id: 502 }] };
  const ids = fx.vigentes.filas.map((f) => f.id);
  const costos: Costos = {
    estimacion: { etiqueta: "ESTIMACIÓN", advertencia: ADVERTENCIA },
    proyectos: ids.map((id, i) => ({
      proyecto_id: id,
      costo_tabla: i === 0 ? "$ 10.941.720,84" : `$ ${i},00`,
      costo_ficha: i === 0 ? "$ 10.941.720,84" : `$ ${i},00`,
      leyenda: LEYENDA,
    })),
    integrantes: [{ asignacion_id: 501, proyecto_id: ids[0], detalle_salarial: "Titular · Simple · Rentada", costo: "$ 6.242.143,20" }],
    sin_costo: "$ 0,00",
  };
  return { fx, ficha, costos };
}

let respuestaCostos: (c: Costos) => Response;

function stub(mod: string) {
  const { fx, ficha, costos } = datos(mod);
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (d: unknown) => new Response(JSON.stringify(d), { status: 200 });
    if (url === `/api/${mod}` && (init?.method ?? "GET") === "GET") return ok(fx.overview);
    const path = url.replace(`/api/${mod}/`, "");
    if (path === "vigentes") return ok(fx.vigentes);
    if (path === "vigentes/ficha") return ok(ficha);
    if (path === "costos") return respuestaCostos(costos);
    if (path === "actos") return ok(fx.actos);
    if (path === "alertas") return ok(fx.alertas);
    return ok({});
  });
  return costos;
}

beforeEach(() => {
  respuestaCostos = (c) => new Response(JSON.stringify(c), { status: 200 });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe.each(MODULOS)("$mod", ({ mod, Comp, titulo }) => {
  test("tabla, listado, métrica, leyenda e integrantes con los costos; etiqueta ESTIMACIÓN y advertencia", async () => {
    const costos = stub(mod);
    render(<Comp onAuthError={() => {}} />);
    await screen.findByText(titulo);
    await screen.findByText("📌 Datos del proyecto");
    await screen.findByText("Titular · Simple · Rentada");
    expect(screen.queryByText("Pendiente de Sueldos")).toBeNull();
    // tabla de proyectos: columna "Costo total sueldos" con el valor de cada proyecto (por id)
    const tablas = screen.getAllByRole("table");
    const cabeceras = (tb: HTMLElement) => within(tb).getAllByRole("columnheader").map((h) => h.textContent);
    const conCosto = tablas.filter((tb) => cabeceras(tb).includes("Costo total sueldos"));
    expect(conCosto).toHaveLength(2); // tabla de proyectos y listado completo
    const encabezados = cabeceras(conCosto[0]);
    const celdas = within(conCosto[0]).getAllByRole("row").slice(1);
    const col = encabezados.indexOf("Costo total sueldos");
    expect(col).toBeGreaterThan(0);
    expect(encabezados[col - 1]).toBe("Meses de ejecución");
    expect(celdas.map((f) => within(f).getAllByRole("cell")[col].textContent)).toEqual(costos.proyectos.map((p) => p.costo_tabla));
    // métrica de la ficha, leyenda certificada y advertencia (tabla + ficha)
    expect(screen.getAllByText("$ 10.941.720,84").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText(LEYENDA)).toBeTruthy();
    expect(screen.getAllByText("ESTIMACIÓN").length).toBe(2);
    expect(screen.getAllByText(ADVERTENCIA).length).toBe(2);
    // integrantes: costo imputado y, sin fila en el detalle, $ 0,00 sin caption salarial
    expect(screen.getByText("$ 6.242.143,20")).toBeTruthy();
    expect(screen.getByText("$ 0,00")).toBeTruthy();
    // listado completo: la columna va después de "Meses de ejecución", alineada por posición e id
    const lista = conCosto[1];
    const cab = within(lista).getAllByRole("columnheader").map((h) => h.textContent);
    expect(cab[cab.indexOf("Meses de ejecución") + 1]).toBe("Costo total sueldos");
    const filas = within(lista).getAllByRole("row").slice(1);
    expect(within(filas[1]).getAllByRole("cell")[cab.indexOf("Costo total sueldos")].textContent).toBe(costos.proyectos[1].costo_tabla);
  });

  test("falla de la lectura de costos: mensaje del backend y el resto de la pestaña sigue", async () => {
    stub(mod);
    respuestaCostos = () =>
      new Response(JSON.stringify({ error: { code: "DB_READ", message: "La lectura de la base de datos falló (no es un resultado vacío)." } }), { status: 503 });
    render(<Comp onAuthError={() => {}} />);
    await screen.findByText("La lectura de la base de datos falló (no es un resultado vacío).");
    await screen.findByText("📌 Datos del proyecto");
    await waitFor(() => expect(screen.queryByText("ESTIMACIÓN")).toBeNull());
    expect(screen.queryByText("Pendiente de Sueldos")).toBeNull();
  });
});
