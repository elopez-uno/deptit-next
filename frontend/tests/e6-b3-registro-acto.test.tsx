// 6A-B3 (último ajuste): Docentes → Registrar designación con el MISMO control de acto que el alta de Designaciones
// (ActoContextual: elegir del repositorio, cargar un nuevo acto ahora o dejar pendiente). Datos SINTÉTICOS con la forma
// de la API; las escrituras no llegan a ningún backend: se verifica el cuerpo JSON o el multipart exacto.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";
import type { ContextoDesignacion, DocentesOverview, VerificacionCuil } from "@/lib/docentes";
import type { ContextoActoNuevo, Documento } from "@/lib/designaciones";

const MODO_BASE = "Seleccionar un docente de la base maestra y registrar su designación en el período actual";
const TITULO_ACTO = "Acto administrativo que aprueba la designación";

const overview: DocentesOverview = {
  contexto: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep" } },
  abierto: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31", estado: "Abierto" },
  actual: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31", estado: "Abierto" },
  historico: false,
  docentes: [],
  catalogos: { estados: ["Activo"], estados_baja: [], tipos: ["Propio", "Prestado"], niveles_posgrado: [""],
    antiguedad_min: 0, antiguedad_max: 80 },
  permisos: { puede_escribir: true, puede_borrar: false, es_superadmin: false },
};

const contexto: ContextoDesignacion = {
  abierto: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31" },
  abierto_huella: "hp-9",
  catalogos: {
    cargos: ["Titular", "JTP"], dedicaciones: ["Simple", "Parcial", "Exclusiva"],
    horas_por_dedicacion: { Simple: 10, Parcial: 20, Exclusiva: 40 }, tipos: ["Concursado", "Interino"],
    estados: ["Activa", "Finalizada"], ad_honorem: ["No", "Sí"],
  },
  reincorporables: [{ nombre_completo: "Alfa, X", cuil: "20-11111111-1", legajo: "L-1", titulo: "Lic.", estado: "Activo", huella: "h-1" }],
  puede_escribir: true,
};

const DOCS: Documento[] = [
  { id: 41, fecha: "2026-10-01", tipo_documento: "Resolución", numero: "441/2026", dependencia_emisora: "Rectorado",
    categoria: "Designación docente", titulo: "Designaciones 2026-2", detalle: "", periodo: "", etiqueta: "Resolución 441/2026" },
  { id: 42, fecha: "2026-10-02", tipo_documento: "Disposición", numero: "12/2026", dependencia_emisora: "Decanato",
    categoria: "Designación docente", titulo: "Otra", detalle: "", periodo: "", etiqueta: "Disposición 12/2026" },
] as Documento[];

const CTX: ContextoActoNuevo = {
  titulo: "Cargar un nuevo acto al repositorio",
  caption: "El acto se guardará en **Resoluciones y respaldos**. Categoría: **{categoria}**.",
  tipos: ["Resolución", "Disposición", "Otro"],
  tipos_con_dependencia: ["Disposición", "Resolución"],
  dependencias: [{ etiqueta: "Seleccionar dependencia", id: null }, { etiqueta: "Rectorado", id: 11 }],
  sin_dependencias: "",
  help_dependencia: "El catálogo de dependencias se administra en Resoluciones y respaldos → Dependencias.",
  max_pdf_bytes: 50 * 1024 * 1024,
  pdf_grande: "El PDF supera 50 MB.",
  categoria_alta: "Designación docente",
  categorias: {},
};

let verif: VerificacionCuil | null;
let envios: { url: string; datos: Record<string, unknown>; archivo: File | null; multipart: boolean }[];

beforeEach(() => {
  verif = null;
  envios = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status });
    const method = init?.method ?? "GET";
    if (url === "/api/docentes" && method === "GET") return ok(overview);
    if (init?.body instanceof FormData) {
      const archivo = init.body.get("archivo");
      envios.push({ url, datos: JSON.parse(String(init.body.get("datos"))), archivo: archivo instanceof File ? archivo : null, multipart: true });
      return ok({ mensaje: "Designación registrada correctamente. El nuevo acto también fue guardado en Resoluciones y respaldos.", tono: "success", avisos: [] });
    }
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (url === "/api/docentes/designacion/contexto") return ok(contexto);
    if (url === "/api/docentes/designacion/duplicado") return ok({ duplicada: false });
    if (url === "/api/docentes/verificar-cuil") return ok(verif ?? { cuil_limpio: body.cuil, otros_departamentos: [], local: null });
    if (url === "/api/designaciones/actos") return ok({ documentos: DOCS });
    if (url === "/api/designaciones/acto-nuevo/contexto") return ok(CTX);
    if (url === "/api/docentes/designacion") {
      envios.push({ url, datos: body, archivo: null, multipart: false });
      return ok({ mensaje: "Docente reincorporado y designación registrada correctamente.", tono: "success", avisos: [] });
    }
    return ok({ error: { code: "NOT_FOUND", message: "no" } }, 404);
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const campo = (label: string) => {
  const l = screen.getByText(label, { selector: "label > span" });
  return l.closest("label")!.querySelector("input, select, textarea") as HTMLInputElement & HTMLSelectElement & HTMLTextAreaElement;
};

async function abrirRegistrar() {
  render(<DocentesModule onAuthError={() => {}} />);
  fireEvent.click(await screen.findByRole("tab", { name: /Registrar docente/ }));
}

function origen(nombre: string) {
  const grupo = screen.getByRole("radiogroup", { name: "Origen del acto administrativo" });
  fireEvent.click(within(grupo).getByRole("radio", { name: nombre }));
}

test("camino 1: el control de acto es el del alta de Designaciones y por defecto queda pendiente (cuerpo certificado)", async () => {
  await abrirRegistrar();
  fireEvent.click(screen.getByRole("radio", { name: MODO_BASE }));
  await screen.findByText(TITULO_ACTO);
  const grupo = screen.getByRole("radiogroup", { name: "Origen del acto administrativo" });
  expect(within(grupo).getAllByRole("radio").map((r) => r.textContent)).toEqual([
    "Elegir del repositorio", "Cargar un nuevo acto ahora", "Dejar pendiente"]);
  expect(within(grupo).getByRole("radio", { name: "Dejar pendiente" }).getAttribute("aria-checked")).toBe("true");
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Registrar designación y reincorporar al período" })));
  await waitFor(() => expect(envios).toHaveLength(1));
  expect(envios[0].url).toBe("/api/docentes/designacion");
  expect("acto" in envios[0].datos).toBe(false);
});

test("camino 1: elegir un acto del repositorio envía su documento_id real por JSON", async () => {
  await abrirRegistrar();
  fireEvent.click(screen.getByRole("radio", { name: MODO_BASE }));
  await screen.findByText(TITULO_ACTO);
  origen("Elegir del repositorio");
  fireEvent.click(await screen.findByText("441/2026"));
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Registrar designación y reincorporar al período" })));
  await waitFor(() => expect(envios).toHaveLength(1));
  expect(envios[0]).toMatchObject({ url: "/api/docentes/designacion", multipart: false });
  expect(envios[0].datos).toMatchObject({ camino: "reincorporar", cuil: "20-11111111-1", acto: { modo: "existente", documento_id: 41 } });
  await screen.findByText("Docente reincorporado y designación registrada correctamente.");
});

test("camino 3: cargar un nuevo acto ahora viaja por multipart a /designacion/acto-nuevo con el PDF", async () => {
  verif = { cuil_limpio: "20-44444444-4", otros_departamentos: [], local: { cuil: "20-44444444-4", tipo_docente: "Propio", nombre: "Delta, Z" } };
  await abrirRegistrar();
  fireEvent.change(campo("CUIL"), { target: { value: "20-44444444-4" } });
  await screen.findByText("Designación en el período actual", {}, { timeout: 3000 });
  origen("Cargar un nuevo acto ahora");
  await screen.findByText("Cargar un nuevo acto al repositorio");
  expect(screen.getByText("Designación docente")).toBeTruthy(); // categoría del alta
  expect(campo("Título / asunto").value).toBe("Designación — Delta, Z");
  fireEvent.change(campo("Dependencia emisora"), { target: { value: "Rectorado" } });
  fireEvent.change(campo("Número / código del acto"), { target: { value: "500/2026" } });
  const pdf = new File(["%PDF-1.4 zz"], "acto.pdf", { type: "application/pdf" });
  fireEvent.change(screen.getByLabelText("PDF del acto administrativo (opcional; puede cargarse después)"), { target: { files: [pdf] } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Registrar una nueva designación para este docente" })));
  await waitFor(() => expect(envios).toHaveLength(1));
  const e = envios[0];
  expect(e).toMatchObject({ url: "/api/docentes/designacion/acto-nuevo", multipart: true });
  expect(e.archivo?.name).toBe("acto.pdf");
  expect(e.datos).toMatchObject({ camino: "cuil_local", cuil_alta: "20-44444444-4", abierto_huella: "hp-9" });
  expect(e.datos.acto).toMatchObject({ modo: "nuevo", payload: { tipo_documento: "Resolución", dependencia_id: 11, numero: "500/2026", titulo: "Designación — Delta, Z" } });
  await screen.findByText(/El nuevo acto también fue guardado en Resoluciones y respaldos/);
});
