// Flujo REAL del módulo Designaciones (DesignacionesModule completo) con las respuestas reales de la API de NEXT para
// UNO, departamento 1 (fixtures generadas por backend/tests/tools_designaciones_frontend_fixtures.py con ROLLBACK).
// Las escrituras no llegan a ningún backend: se verifica el cuerpo exacto que enviaría la pantalla.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DesignacionesModule } from "@/components/designaciones-module";
import type { Carga, Overview, PeriodoData } from "@/lib/designaciones";

type Fixtures = {
  overview: Overview;
  lector: Overview;
  periodos: Record<string, PeriodoData>;
  actos: unknown;
  duplicado: { body: Record<string, unknown>; respuesta: unknown };
  carga: { texto: string; respuesta: Carga };
};
const fx: Fixtures = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "designaciones_uno.json"), "utf8"));
const abierto = fx.overview.abierto!;
const actual = fx.periodos[String(abierto.id)];
const historico = Object.values(fx.periodos).find((p) => p.historico)!;

let overview: Overview;
let posts: { path: string; body: Record<string, unknown> }[] = [];
const escrituras = () =>
  posts.filter((p) => !["periodo", "actos", "duplicado", "carga-rapida/previsualizar", "acto-nuevo/contexto"].includes(p.path));

beforeEach(() => {
  overview = fx.overview;
  posts = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/designaciones" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/designaciones/", "");
    const body = JSON.parse(String(init?.body ?? "{}"));
    posts.push({ path, body });
    if (path === "periodo") return ok(fx.periodos[String(body.periodo_id)]);
    if (path === "actos") return ok(fx.actos);
    if (path === "acto-nuevo/contexto") {
      // E4-07: forma del contexto del formulario en línea (el detalle se prueba en e4-07-acto-nuevo.test.tsx)
      return ok({ titulo: "Cargar un nuevo acto al repositorio", caption: "Categoría: **{categoria}**.", tipos: ["Resolución", "Disposición", "Otro"],
        tipos_con_dependencia: ["Disposición", "Resolución"], dependencias: [{ etiqueta: "Seleccionar dependencia", id: null }],
        sin_dependencias: "", help_dependencia: "", max_pdf_bytes: 52428800, pdf_grande: "", categoria_alta: "Designación docente", categorias: {} });
    }
    if (path === "duplicado") {
      expect(body).toEqual(fx.duplicado.body);
      return ok(fx.duplicado.respuesta);
    }
    if (path === "carga-rapida/previsualizar") {
      expect(body.texto).toBe(fx.carga.texto);
      return ok(fx.carga.respuesta);
    }
    return ok({ mensaje: "OK (respuesta simulada del test)", tono: "success" });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(tab?: string) {
  render(<DesignacionesModule onAuthError={() => {}} />);
  await screen.findByRole("heading", { name: "📑 Módulo Designaciones" }, { timeout: 5000 });
  if (tab) fireEvent.click(screen.getByRole("tab", { name: tab }));
}

// Filas de la tabla cuyo encabezado incluye `col`.
function filas(col: string) {
  const t = screen.getAllByRole("table").find((x) => within(x).queryByRole("columnheader", { name: col }));
  return t ? within(t).getAllByRole("row").slice(1) : [];
}

test("encabezado del período abierto y las 5 pestañas en el orden certificado", async () => {
  await abrir();
  expect(
    screen.getByText(`Período abierto actual: ${abierto.nombre} (${abierto.fecha_inicio} al ${abierto.fecha_fin})`)
  ).toBeTruthy();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual([
    "📋 Designaciones del período",
    "➕ Nueva designación",
    "✏️ Modificar / finalizar designación",
    "🛠️ Editar / eliminar por error",
    "📥 Carga rápida",
  ]);
});

test("pestaña 1: período abierto por defecto, tabla, conteo de activas e historial por indicador", async () => {
  await abrir();
  await waitFor(() => expect(filas("fecha_hasta_prevista").length).toBe(actual.designaciones.length), { timeout: 5000 });
  expect((screen.getByRole("combobox", { name: "Ver período" }) as HTMLSelectElement).value).toBe(abierto.nombre);
  expect(screen.getByText(`Cantidad de designaciones activas en el período seleccionado: ${actual.conteo}`)).toBeTruthy();
  // período actual: sin grilla editable ni descarga de la tabla histórica
  expect(screen.queryByRole("button", { name: /Guardar fechas corregidas/ })).toBeNull();

  const radios = within(screen.getByRole("radiogroup", { name: "Indicador" })).getAllByRole("radio");
  expect(radios.map((r) => r.textContent)).toEqual(actual.indicadores.map((i) => i.etiqueta));
  for (const i of [actual.indicadores[0], actual.indicadores.at(-1)!]) {
    fireEvent.click(screen.getByRole("radio", { name: i.etiqueta }));
    const n = actual.historial.filter((m) => m.categoria === i.categoria).length;
    await waitFor(() => expect(filas("Variación de horas").length).toBe(n));
    expect(screen.getByText((_, el) => el?.tagName === "P" && !!el.textContent?.startsWith(`${n} movimiento/s integran el indicador ${i.etiqueta};`))).toBeTruthy();
  }
});

test("pestaña 1 histórica: foto al cierre, grilla de fechas y guardado con sincronización v207", async () => {
  await abrir();
  await screen.findByRole("combobox", { name: "Ver período" }, { timeout: 5000 });
  await act(async () => fireEvent.change(screen.getByRole("combobox", { name: "Ver período" }), { target: { value: historico.periodo.nombre } }));
  await waitFor(() => expect(filas("fecha_hasta_prevista").length).toBe(historico.designaciones.length), { timeout: 5000 });
  expect(screen.getByText(`Cantidad de designaciones vigentes al cierre del período seleccionado: ${historico.conteo}`)).toBeTruthy();
  expect(screen.getAllByRole("cell", { name: "Vigente al cierre" }).length).toBe(historico.foto_ids.length);

  const guardar = screen.getByRole("button", { name: "💾 Guardar fechas corregidas" }) as HTMLButtonElement;
  expect(guardar.disabled).toBe(true);
  const d = historico.designaciones[0];
  fireEvent.change(screen.getByLabelText(`fecha_hasta de la designación ${d.id}`), { target: { value: "2026-05-15" } });
  expect(screen.getByText("Filas con cambios pendientes de guardar: 1")).toBeTruthy();
  await act(async () => fireEvent.click(guardar));
  expect(escrituras()).toEqual([
    {
      path: "fechas-historicas",
      body: { periodo_id: historico.periodo.id, cambios: [{ id: d.id, huella: d.huella, desde: d.fecha_desde, hasta: "2026-05-15" }] },
    },
  ]);
});

test("pestaña 2: formulario de alta, duplicado con los valores del formulario y acto contextual", async () => {
  await abrir("➕ Nueva designación");
  await waitFor(() => expect(posts.some((p) => p.path === "duplicado")).toBe(true), { timeout: 5000 });
  expect(filas("Legajo").length).toBe(fx.overview.docentes.length);
  const modos = within(screen.getByRole("radiogroup", { name: "Origen del acto administrativo" })).getAllByRole("radio");
  expect(modos.map((m) => m.textContent)).toEqual(["Elegir del repositorio", "Cargar un nuevo acto ahora", "Dejar pendiente"]);
  fireEvent.click(screen.getByRole("radio", { name: "Cargar un nuevo acto ahora" }));
  // E4-07: ya no es un aviso de pendiente; pide el contexto del formulario en línea (cubierto en e4-07-acto-nuevo)
  expect(screen.queryByText(/todavía no está migrado/)).toBeNull();
  await waitFor(() => expect(posts.some((p) => p.path === "acto-nuevo/contexto")).toBe(true));
  fireEvent.click(screen.getByRole("radio", { name: "Dejar pendiente" }));

  fireEvent.click(screen.getByRole("checkbox", { name: "Esta designación corresponde a funciones no docentes" }));
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Guardar designación" })));
  expect(screen.getByText("Completá las funciones no docentes antes de guardar la designación.")).toBeTruthy();
  expect(escrituras()).toEqual([]);
});

test("pestaña 3: solo designaciones no finalizadas, tipos de modificación y baja", async () => {
  await abrir("✏️ Modificar / finalizar designación");
  const modificables = actual.designaciones.filter((d) => String(d.estado ?? "").trim().toLowerCase() !== "finalizada");
  await waitFor(() => expect(filas("Funciones no docentes").length).toBe(modificables.length), { timeout: 5000 });
  const tipo = screen.getByRole("combobox", { name: "Tipo de modificación" }) as HTMLSelectElement;
  expect([...tipo.options].map((o) => o.value)).toEqual(fx.overview.catalogos.tipos_cambio);

  fireEvent.change(tipo, { target: { value: "Finalizar / baja de designación" } });
  expect(screen.getByLabelText("Fecha efectiva de finalización")).toBeTruthy();
  expect(!!screen.queryByRole("radiogroup", { name: "Origen del acto administrativo" })).toBe(
    fx.overview.catalogos.movimientos_con_acto.includes("Finalizar / baja de designación")
  );

  fireEvent.change(tipo, { target: { value: "Cambio de cargo" } });
  const f = modificables[0];
  fireEvent.click(screen.getByRole("radio", { name: "Dejar pendiente" }));
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "✏️ Guardar modificación registrada" })));
  const [w] = escrituras();
  expect(w.path).toBe("modificar");
  expect(w.body).toMatchObject({ id: f.id, huella: f.huella, tipo_cambio: "Cambio de cargo", acto: { modo: "pendiente", documento_id: null } });
});

test("pestaña 4 (usuario de departamento): corrección por fila, sin eliminación (solo superadmin)", async () => {
  await abrir("🛠️ Editar / eliminar por error");
  await waitFor(() => expect(filas("Editar / eliminar").length).toBe(actual.designaciones.length), { timeout: 5000 });
  expect(screen.queryByRole("columnheader", { name: "Eliminar" })).toBeNull();
  expect(screen.queryByText("Seleccionar todas las designaciones mostradas para eliminar")).toBeNull();
  const [a, b] = actual.designaciones;
  fireEvent.click(screen.getByLabelText(`Editar / eliminar designación ${a.id}`));
  expect(screen.getByText(/^Designación seleccionada: /)).toBeTruthy();
  fireEvent.click(screen.getByLabelText(`Editar / eliminar designación ${b.id}`));
  expect(screen.getByText(/Marcá una sola designación en 'Editar \/ eliminar'/)).toBeTruthy();
  fireEvent.click(screen.getByLabelText(`Editar / eliminar designación ${b.id}`));
  fireEvent.click(screen.getByRole("radio", { name: "Eliminar designación cargada por error" }));
  expect(screen.queryByRole("button", { name: /Eliminar designación sin registrar movimiento/ })).toBeNull();
});

test("pestaña 5: vista previa real, CUIL inexistente bloquea la carga", async () => {
  await abrir("📥 Carga rápida");
  fireEvent.change(screen.getByRole("textbox", { name: "Pegá acá las designaciones" }), { target: { value: fx.carga.texto } });
  await screen.findByText(`Filas detectadas: ${fx.carga.respuesta.filas.length}`, undefined, { timeout: 5000 });
  // Etapa 5 (docs/ETAPA5_FINAL_REMEDIATION.md): las fechas ISO pegadas no se invierten (bug heredado del certificado:
  // 2026-08-01 -> 2026-01-08).  Una preview generada con el bug viejo hace fallar este test.
  const iso = [abierto.fecha_inicio, abierto.fecha_fin].map(String);
  const invertida = (f: string) => `${f.slice(0, 4)}-${f.slice(8, 10)}-${f.slice(5, 7)}`;
  expect(iso).toEqual(["2026-08-01", "2026-12-31"]);
  expect(fx.carga.texto).toContain(`\t${iso[0]}\t${iso[1]}\n`);
  for (const f of fx.carga.respuesta.filas as unknown as Record<string, unknown>[]) {
    expect([f.fecha_desde, f.fecha_hasta]).toEqual(iso);
  }
  const vista = within(screen.getByRole("heading", { name: "Vista previa" }).parentElement!);
  expect(vista.getAllByText(iso[0])).toHaveLength(fx.carga.respuesta.filas.length);
  expect(vista.queryAllByText(invertida(iso[0]))).toEqual([]);
  expect(screen.getByText("Hay designaciones con CUIL que no existen en la base maestra. Esas filas no se pueden cargar.")).toBeTruthy();
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "📥 Cargar designaciones pegadas" })));
  expect(screen.getByText("No se cargó nada. Primero registrá los docentes que faltan.")).toBeTruthy();
  expect(escrituras()).toEqual([]);
});

test("solo lectura: no se muestran botones de escritura", async () => {
  overview = fx.lector;
  await abrir();
  await waitFor(() => expect(filas("fecha_hasta_prevista").length).toBe(actual.designaciones.length), { timeout: 5000 });
  fireEvent.click(screen.getByText("🔗 Vincular / cambiar acto administrativo de una o varias designaciones"));
  fireEvent.click(screen.getByRole("tab", { name: "➕ Nueva designación" }));
  await screen.findByText("Docentes encontrados");
  expect(screen.queryByRole("button", { name: "💾 Guardar designación" })).toBeNull();
  fireEvent.click(screen.getByRole("tab", { name: "✏️ Modificar / finalizar designación" }));
  await waitFor(() => expect(screen.getByRole("combobox", { name: "Tipo de modificación" })).toBeTruthy(), { timeout: 5000 });
  expect(screen.queryByRole("button", { name: "✏️ Guardar modificación registrada" })).toBeNull();
  expect(screen.queryAllByRole("button").filter((b) => /Vincular|Quitar vínculo/.test(b.textContent ?? ""))).toEqual([]);
});
