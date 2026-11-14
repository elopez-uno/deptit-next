// E4-07: "Cargar un nuevo acto ahora" en Designaciones (alta y modificación / baja). Flujo REAL del módulo con las
// fixtures reales de UNO (designaciones_uno.json) y el contexto del formulario con la forma exacta de la API. Las
// escrituras no llegan a ningún backend: se verifica el multipart exacto (parte "datos" JSON + parte "archivo").
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DesignacionesModule } from "@/components/designaciones-module";
import type { ContextoActoNuevo, Overview, PeriodoData } from "@/lib/designaciones";

type Fixtures = { overview: Overview; periodos: Record<string, PeriodoData>; actos: unknown; duplicado: { respuesta: unknown } };
const fx: Fixtures = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "designaciones_uno.json"), "utf8"));
const abierto = fx.overview.abierto!;
const actual = fx.periodos[String(abierto.id)];

const CTX: ContextoActoNuevo = {
  titulo: "Cargar un nuevo acto al repositorio",
  caption:
    "El acto se guardará en **Resoluciones y respaldos** y, al confirmar la operación, quedará vinculado al registro correspondiente. El PDF es opcional y puede adjuntarse después. Categoría: **{categoria}**.",
  tipos: ["Resolución", "Disposición", "Otro"],
  tipos_con_dependencia: ["Disposición", "Resolución"],
  dependencias: [
    { etiqueta: "Seleccionar dependencia", id: null },
    { etiqueta: "Rectorado", id: 11 },
    { etiqueta: "Consejo Superior", id: 12 },
  ],
  sin_dependencias: "",
  help_dependencia: "El catálogo de dependencias se administra en Resoluciones y respaldos → Dependencias.",
  max_pdf_bytes: 50 * 1024 * 1024,
  pdf_grande: "El PDF supera 50 MB.",
  categoria_alta: "Designación docente",
  categorias: {
    "Cambio de cargo": "Cambio de cargo",
    "Aumento de dedicación": "Cambio de dedicación",
    "Finalizar / baja de designación": "Designación docente",
    "Cambio de condición Ad Honorem": "Cambio de condición Ad Honorem / Rentada",
  },
};

let ctx: ContextoActoNuevo;
let respuesta: { status: number; body: unknown };
let envios: { path: string; datos: Record<string, unknown>; archivo: File | null; multipart: boolean }[];

beforeEach(() => {
  ctx = CTX;
  respuesta = { status: 200, body: { mensaje: "Designación registrada correctamente. El nuevo acto también fue guardado en Resoluciones y respaldos.", tono: "success" } };
  envios = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/designaciones" && (init?.method ?? "GET") === "GET") return ok(fx.overview);
    const path = url.replace("/api/designaciones/", "");
    if (init?.body instanceof FormData) {
      const archivo = init.body.get("archivo");
      envios.push({ path, datos: JSON.parse(String(init.body.get("datos"))), archivo: archivo instanceof File ? archivo : null, multipart: true });
      return new Response(JSON.stringify(respuesta.body), { status: respuesta.status });
    }
    const body = JSON.parse(String(init?.body ?? "{}"));
    if (path === "periodo") return ok(fx.periodos[String(body.periodo_id)]);
    if (path === "actos") return ok(fx.actos);
    if (path === "duplicado") return ok(fx.duplicado.respuesta);
    if (path === "acto-nuevo/contexto") return ok(ctx);
    envios.push({ path, datos: body, archivo: null, multipart: false });
    return ok({ mensaje: "OK (respuesta simulada del test)", tono: "success" });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(tab: string) {
  render(<DesignacionesModule onAuthError={() => {}} />);
  await screen.findByRole("heading", { name: "📑 Módulo Designaciones" }, { timeout: 5000 });
  fireEvent.click(screen.getByRole("tab", { name: tab }));
}

const campo = (label: string) => {
  const l = screen.getByText(label, { selector: "label > span, label span, span" });
  return l.closest("label")!.querySelector("input, select, textarea") as HTMLInputElement & HTMLSelectElement & HTMLTextAreaElement;
};

function hoy() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

test("alta: formulario en línea certificado (rótulos, orden, defaults, sugerencias) y multipart con el PDF", async () => {
  await abrir("➕ Nueva designación");
  fireEvent.click(await screen.findByRole("radio", { name: "Cargar un nuevo acto ahora" }));
  await screen.findByText("Cargar un nuevo acto al repositorio");
  const docente = fx.overview.docentes[0];
  // caption con la categoría de la operación
  expect(screen.getByText("Designación docente", { selector: "b" })).toBeTruthy();
  const c = fx.overview.catalogos;
  expect(campo("Tipo de documento").value).toBe("Resolución");
  expect([...campo("Tipo de documento").options].map((o) => o.value)).toEqual(CTX.tipos);
  expect([...campo("Dependencia emisora").options].map((o) => o.value)).toEqual(CTX.dependencias.map((d) => d.etiqueta));
  expect(campo("Dependencia emisora").value).toBe("Seleccionar dependencia");
  expect(screen.getByText(CTX.help_dependencia)).toBeTruthy();
  expect(campo("Número / código del acto").placeholder).toBe("Ej.: 441/2026");
  expect(campo("Fecha del acto").value).toBe(hoy());
  expect(campo("Título / asunto").value).toBe(`Designación — ${docente.nombre_completo}`);
  const detalle = campo("Detalle / referencia adicional").value;
  expect(detalle.startsWith(`${abierto.nombre} - ${docente.nombre_completo} - ${c.cargos[0]} - ${c.dedicaciones[0]} - `)).toBe(true);
  expect(detalle.endsWith(`hs - ${c.tipos[0]} - Función: Docencia`)).toBe(true);
  expect(campo("Observaciones internas").value).toBe("");

  fireEvent.change(campo("Dependencia emisora"), { target: { value: "Rectorado" } });
  fireEvent.change(campo("Número / código del acto"), { target: { value: "441/2026" } });
  const pdf = new File(["%PDF-1.4 sintetico"], "acto.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("PDF del acto administrativo (opcional; puede cargarse después)"), { target: { files: [pdf] } });
  expect(screen.getByText(/^Archivo: acto\.pdf — \d+\.\d KB$/)).toBeTruthy();
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Guardar designación" })));

  await waitFor(() => expect(envios).toHaveLength(1));
  const [e] = envios;
  expect(e.path).toBe("acto-nuevo/alta");
  expect(e.multipart).toBe(true);
  expect(e.archivo?.name).toBe("acto.pdf");
  expect(e.datos.cuil).toBe(docente.cuil);
  expect(e.datos.acto).toEqual({
    modo: "nuevo",
    payload: {
      tipo_documento: "Resolución",
      dependencia_id: 11,
      numero: "441/2026",
      fecha: hoy(),
      titulo: `Designación — ${docente.nombre_completo}`,
      detalle,
      observaciones: "",
    },
  });
  await screen.findByText(/El nuevo acto también fue guardado en Resoluciones y respaldos\./);
});

test("cambiar el tipo vuelve a 'Seleccionar dependencia'; 'Otro' la deja opcional; sin dependencias activas avisa", async () => {
  ctx = { ...CTX, dependencias: [CTX.dependencias[0]], sin_dependencias: "No hay dependencias emisoras activas. Primero cargá una en Resoluciones y respaldos → Dependencias." };
  await abrir("➕ Nueva designación");
  fireEvent.click(await screen.findByRole("radio", { name: "Cargar un nuevo acto ahora" }));
  await screen.findByText("Cargar un nuevo acto al repositorio");
  expect(screen.getByText(ctx.sin_dependencias)).toBeTruthy();
  fireEvent.change(campo("Tipo de documento"), { target: { value: "Otro" } });
  expect(screen.getByText("Dependencia emisora (opcional)")).toBeTruthy();
  expect(screen.queryByText(ctx.sin_dependencias)).toBeNull();
});

test("rechazo del backend (errores del formulario): se muestra y no hay otra escritura", async () => {
  respuesta = { status: 422, body: { error: { code: "ACTO_INVALIDO", message: "No se puede crear el acto administrativo: Seleccioná la dependencia emisora. Completá el número del acto administrativo." } } };
  await abrir("➕ Nueva designación");
  fireEvent.click(await screen.findByRole("radio", { name: "Cargar un nuevo acto ahora" }));
  await screen.findByText("Cargar un nuevo acto al repositorio");
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Guardar designación" })));
  await screen.findByText(/No se puede crear el acto administrativo: Seleccioná la dependencia emisora\./);
  expect(envios.map((x) => x.path)).toEqual(["acto-nuevo/alta"]);
  expect(envios[0].archivo).toBeNull();
});

test("modificación con acto nuevo: categoría y título por tipo de cambio; 'Dejar pendiente' sigue por JSON", async () => {
  respuesta = { status: 200, body: { mensaje: "Designación actualizada correctamente.", tono: "success" } };
  await abrir("✏️ Modificar / finalizar designación");
  const modificables = actual.designaciones.filter((d) => String(d.estado ?? "").trim().toLowerCase() !== "finalizada");
  const f = modificables[0];
  const tipo = (await screen.findByRole("combobox", { name: "Tipo de modificación" }, { timeout: 5000 })) as HTMLSelectElement;
  fireEvent.change(tipo, { target: { value: "Cambio de cargo" } });
  fireEvent.click(screen.getByRole("radio", { name: "Cargar un nuevo acto ahora" }));
  await screen.findByText("Cargar un nuevo acto al repositorio");
  expect(screen.getByText("Cambio de cargo", { selector: "b" })).toBeTruthy();
  expect(campo("Título / asunto").value).toBe(`Cambio de cargo — ${f.nombre_completo}`);
  expect(campo("Detalle / referencia adicional").value).toBe("");
  fireEvent.change(campo("Tipo de documento"), { target: { value: "Otro" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "✏️ Guardar modificación registrada" })));
  await waitFor(() => expect(envios).toHaveLength(1));
  expect(envios[0]).toMatchObject({ path: "acto-nuevo/modificar", multipart: true, archivo: null });
  expect(envios[0].datos).toMatchObject({ id: f.id, huella: f.huella, tipo_cambio: "Cambio de cargo" });
  expect((envios[0].datos.acto as { payload: Record<string, unknown> }).payload).toMatchObject({ tipo_documento: "Otro", dependencia_id: null });

  // cambiar de tipo reinicia el acto (clave del formulario por tipo de cambio, como el certificado)
  fireEvent.change(tipo, { target: { value: "Aumento de dedicación" } });
  const grupo = screen.getByRole("radiogroup", { name: "Origen del acto administrativo" });
  expect(within(grupo).getByRole("radio", { name: "Elegir del repositorio" }).getAttribute("aria-checked")).toBe("true");
  fireEvent.click(screen.getByRole("radio", { name: "Dejar pendiente" }));
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "✏️ Guardar modificación registrada" })));
  await waitFor(() => expect(envios).toHaveLength(2));
  expect(envios[1]).toMatchObject({ path: "modificar", multipart: false });
  expect(envios[1].datos.acto).toMatchObject({ modo: "pendiente" });
});
