// Flujo REAL del módulo Resoluciones y respaldos (ResolucionesRespaldosModule completo) con las respuestas reales de la
// API de NEXT para UNO, departamento 1 (fixtures generadas por backend/tests/tools_resoluciones_frontend_fixtures.py con
// ROLLBACK). Las escrituras y descargas no llegan a ningún backend: se verifica el cuerpo exacto que enviaría la
// pantalla (multipart con el File, nunca base64) y que no se exponen binarios ni rutas.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ResolucionesRespaldosModule } from "@/components/resoluciones-respaldos-module";
import type { Detalle, FilaProyecto, Overview, TablaDocentes } from "@/lib/resoluciones-respaldos";

type Fx = { overview: Overview; super: Overview; lector: Overview; detalle: Detalle; docentes: TablaDocentes; proyectos: { filas: FilaProyecto[]; aviso: string } };
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "resoluciones_uno.json"), "utf8"));

let overview: Overview;
let detalle: Detalle;
type Envio = { path: string; body: unknown; form?: FormData };
let envios: Envio[] = [];
const LECTURAS = new Set(["documento", "docentes", "proyectos", "documento/pdf", "designaciones"]);
// 6A-B3: designaciones concretas (sintéticas) de los docentes elegidos; ninguna asumida única por docente.
const DESIGNACION = { cuil: "", docente: "ZZNEXT Docente", periodo: "2026 1C", cargo: "Adjunto", dedicacion: "Simple",
  tipo_designacion: "Interino", fecha_desde: "2026-03-01", fecha_hasta: "2026-07-31", estado: "Activa", funcion_no_docente: 0,
  acto_documento_id: null, acto_administrativo: "Pendiente de vincular", vinculada: false };
const DESIGNACIONES = [
  { ...DESIGNACION, id: 501 },
  { ...DESIGNACION, id: 502, periodo: "2025 2C", fecha_desde: "2025-08-01", fecha_hasta: "2025-12-31", estado: "Finalizada" },
];
const escrituras = () => envios.filter((e) => !LECTURAS.has(e.path));
let descargas = 0;

beforeEach(() => {
  overview = fx.overview;
  detalle = fx.detalle;
  envios = [];
  descargas = 0;
  vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: () => "blob:x", revokeObjectURL: () => {} }));
  vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(() => {});
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown, status = 200) => new Response(JSON.stringify(data), { status });
    if (url === "/api/resoluciones-respaldos" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/resoluciones-respaldos/", "");
    if (init?.body instanceof FormData) {
      envios.push({ path, body: JSON.parse(String(init.body.get("datos"))), form: init.body });
      return ok({ mensaje: "Acto guardado correctamente (ID 99) y vinculado a 2 docentes. PDF adjunto.", tono: "success" });
    }
    const body = JSON.parse(String(init?.body ?? "{}"));
    envios.push({ path, body });
    if (path === "documento") return ok(detalle);
    if (path === "docentes") return ok(fx.docentes);
    if (path === "proyectos") return ok(fx.proyectos);
    if (path === "designaciones") return ok({ filas: DESIGNACIONES, caption: "Marcá la designación", aviso: "" });
    if (path === "documento/pdf") {
      descargas += 1;
      return new Response(new Blob(["%PDF-1.4 x"]), {
        status: 200,
        headers: { "content-type": "application/pdf", "content-disposition": "attachment; filename=\"Acta.pdf\"; filename*=UTF-8''Acta%20%C3%B1.pdf" },
      });
    }
    return ok({ mensaje: "ok", tono: "success" });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

async function abrir(tab?: string) {
  render(<ResolucionesRespaldosModule onAuthError={() => {}} />);
  await screen.findByText("📂 Resoluciones y respaldos");
  if (tab) fireEvent.click(screen.getByRole("tab", { name: tab }));
}

async function seleccionarPrimero() {
  const radios = await screen.findAllByRole("radio", { name: "Seleccionar fila" });
  fireEvent.click(radios[0]);
  await screen.findByText("Documento seleccionado");
}

test("las 3 pestañas certificadas en orden, aviso y repositorio sin binarios", async () => {
  await abrir();
  expect(screen.getAllByRole("tab").map((t) => t.textContent)).toEqual(["📚 Repositorio", "➕ Cargar acto", "🏛️ Dependencias"]);
  expect(screen.getByText(/Repositorio documental del departamento/)).toBeTruthy();
  expect(screen.getByText("Documentación respaldatoria")).toBeTruthy();
  for (const h of ["Fecha", "Tipo", "Dependencia emisora", "Respalda", "N°", "Estado PDF", "Tamaño (KB)"]) {
    expect(screen.getAllByText(h).length).toBeGreaterThan(0);
  }
  expect(screen.getAllByRole("radio", { name: "Seleccionar fila" })).toHaveLength(overview.repositorio.filas.length);
  expect(document.body.innerHTML).not.toMatch(/%PDF|C:\\|storage|archivo_pdf/);
});

test("filtros y búsqueda certificados", async () => {
  await abrir();
  fireEvent.change(screen.getByPlaceholderText("Número, dependencia, docente, CUIL, proyecto, título..."), { target: { value: "zz-no-existe" } });
  expect(await screen.findByText("No hay documentos que coincidan con los filtros.")).toBeTruthy();
});

test("usuario de departamento: detalle, descarga bajo demanda, corrección de dependencia y sin botón Eliminar (D-AK6)", async () => {
  await abrir();
  await seleccionarPrimero();
  expect(envios.find((e) => e.path === "documento")?.body).toEqual({ id: overview.repositorio.filas[0].id });
  expect(screen.queryByRole("button", { name: /Eliminar documento/ })).toBeNull();
  fireEvent.click(screen.getByRole("button", { name: /Descargar PDF/ }));
  await waitFor(() => expect(descargas).toBe(1));
  expect(envios.find((e) => e.path === "documento/pdf")?.body).toEqual({ id: overview.repositorio.filas[0].id });
  fireEvent.click(screen.getByText("🏛️ Asignar o corregir dependencia emisora"));
  fireEvent.click(screen.getByRole("button", { name: /Guardar dependencia del documento/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toMatchObject({ path: "documento/dependencia", body: { id: overview.repositorio.filas[0].id } });
});

test("reemplazar PDF viaja como multipart con el File y respeta el tope de 50 MB", async () => {
  await abrir();
  await seleccionarPrimero();
  const input = screen.getByLabelText("Seleccionar PDF") as HTMLInputElement;
  const grande = new File(["x"], "grande.pdf", { type: "application/pdf" });
  Object.defineProperty(grande, "size", { value: 50 * 1024 * 1024 + 1 });
  fireEvent.change(input, { target: { files: [grande] } });
  fireEvent.click(screen.getByRole("button", { name: /Reemplazar PDF/ }));
  expect(await screen.findByText("El PDF supera 50 MB.")).toBeTruthy();
  expect(escrituras()).toHaveLength(0);
  const pdf = new File(["%PDF-1.4\n%%EOF"], "Acta ñ.pdf", { type: "application/pdf" });
  fireEvent.change(input, { target: { files: [pdf] } });
  fireEvent.click(screen.getByRole("button", { name: /Reemplazar PDF/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const e = escrituras()[0];
  expect(e.path).toBe("documento/adjuntar-pdf");
  expect(e.body).toEqual({ id: overview.repositorio.filas[0].id });
  const parte = e.form?.get("archivo") as File;
  expect(parte).toBeInstanceOf(File);
  expect(parte.name).toBe("Acta ñ.pdf");
  expect(String(e.form?.get("datos"))).not.toMatch(/JVBER|base64/);
});

test("resolución de designación ya cargada: se vincula después a designaciones concretas (y se confirma un reemplazo)", async () => {
  const otro = { ...DESIGNACION, id: 503, acto_documento_id: 77, acto_administrativo: "Resolución 9/2025 (Rectorado)" };
  detalle = { ...fx.detalle, designacion_docente: true, caption_designaciones: "Marcá la designación",
    designaciones: [{ ...DESIGNACIONES[0], vinculada: false }, DESIGNACIONES[1], otro] } as Detalle;
  await abrir();
  await seleccionarPrimero();
  expect(screen.getByText(/Designaciones respaldadas por este acto \(0\)/)).toBeTruthy();
  expect(screen.getByText("Acto vinculado actual: Resolución 9/2025 (Rectorado)")).toBeTruthy();
  fireEvent.click(screen.getByRole("checkbox", { name: /^ID 501 ·/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /^ID 503 ·/ }));
  fireEvent.click(screen.getByRole("checkbox", { name: /Confirmo reemplazar el acto vinculado de 1 designación/ }));
  fireEvent.click(screen.getByRole("button", { name: /Guardar designaciones vinculadas/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({ path: "documento/designaciones",
    body: { id: overview.repositorio.filas[0].id, designaciones: [501, 503], reemplazar_vinculos: true } });
});

test("acto ya cargado: aviso de designación pendiente y agregar docentes con el selector del alta", async () => {
  detalle = { ...fx.detalle, designacion_docente: true, designaciones: [], caption_designaciones: "",
    designacion_pendiente: "Esta resolución todavía no está vinculada a ninguna designación: la relación queda pendiente.",
    relaciones: { docentes: true, designaciones: true, proyectos: null }, proyectos_vinculados: [] } as Detalle;
  await abrir();
  await seleccionarPrimero();
  expect(screen.getByText(/todavía no está vinculada a ninguna designación/)).toBeTruthy();
  const panel = screen.getByText("👥 Agregar docentes a este acto").closest("details") as HTMLElement;
  const boton = within(panel).getByRole("button", { name: /Agregar docentes seleccionados/ }) as HTMLButtonElement;
  expect(boton.disabled).toBe(true);
  const checks = await within(panel).findAllByRole("checkbox", { name: "Seleccionar" });
  fireEvent.click(checks[1]);
  fireEvent.click(boton);
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({ path: "documento/docentes", body: { id: overview.repositorio.filas[0].id,
    modo: "Designaciones activas del período actual", docentes: [fx.docentes.filas[1].CUIL] } });
});

test("acto de investigación ya cargado: se agregan y quitan proyectos (conjunto final)", async () => {
  const [p0, p1, p2] = fx.proyectos.filas;
  detalle = { ...fx.detalle, designacion_docente: false, designaciones: [], caption_designaciones: "", designacion_pendiente: "",
    relaciones: { docentes: false, designaciones: false, proyectos: "investigacion" }, proyectos_vinculados: [p0.ID, p1.ID] } as Detalle;
  await abrir();
  await seleccionarPrimero();
  expect(screen.queryByText("👥 Agregar docentes a este acto")).toBeNull();
  expect(screen.getByText("🔬 Proyectos vinculados a este acto (2)")).toBeTruthy();
  await waitFor(() => expect(envios.some((e) => e.path === "proyectos")).toBe(true));
  const etiqueta = (p: typeof p0) => new RegExp(`^${p.Código ? `\\[${p.Código.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}\\] ` : ""}`);
  const casilla = (p: typeof p0) => screen.getAllByRole("checkbox").find((c) => (c.parentElement?.textContent ?? "").includes(p.Proyecto) && etiqueta(p).test(c.parentElement?.textContent ?? "")) as HTMLInputElement;
  expect(casilla(p0).checked && casilla(p1).checked && !casilla(p2).checked).toBe(true);
  fireEvent.click(casilla(p0)); // quitar
  fireEvent.click(casilla(p2)); // agregar
  fireEvent.click(screen.getByRole("button", { name: /Guardar proyectos vinculados/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({ path: "documento/proyectos",
    body: { id: overview.repositorio.filas[0].id, proyectos: [p1.ID, p2.ID].sort((a, b) => a - b) } });
});

test("alta de designación sin designación: el aviso de relación pendiente se muestra con el mensaje", async () => {
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
    if (url === "/api/resoluciones-respaldos" && (init?.method ?? "GET") === "GET") return ok(overview);
    const path = url.replace("/api/resoluciones-respaldos/", "");
    if (init?.body instanceof FormData) {
      envios.push({ path, body: JSON.parse(String(init.body.get("datos"))), form: init.body });
      return ok({ mensaje: "Acto guardado correctamente (ID 99) y vinculado al docente seleccionado. PDF pendiente de carga.",
        tono: "success", aviso: "Esta resolución todavía no está vinculada a ninguna designación: la relación queda pendiente." });
    }
    envios.push({ path, body: JSON.parse(String(init?.body ?? "{}")) });
    if (path === "docentes") return ok(fx.docentes);
    if (path === "designaciones") return ok({ filas: DESIGNACIONES, caption: "", aviso: "" });
    return ok({});
  });
  await abrir("➕ Cargar acto");
  fireEvent.click((await screen.findAllByRole("checkbox", { name: "Seleccionar" }))[0]);
  fireEvent.change(screen.getByLabelText(/^Dependencia emisora/), { target: { value: "Rectorado" } });
  await screen.findByText(/Sin designación seleccionada/);
  fireEvent.click(screen.getByRole("button", { name: /Guardar acto respaldatorio/ }));
  expect(await screen.findByText(/Acto guardado correctamente .*⚠️ Esta resolución todavía no está vinculada/)).toBeTruthy();
  expect(escrituras()[0].body).not.toHaveProperty("designaciones");
});

test("superadmin: Eliminar visible solo con confirmación", async () => {
  overview = fx.super;
  await abrir();
  await seleccionarPrimero();
  const boton = screen.getByRole("button", { name: /Eliminar documento/ }) as HTMLButtonElement;
  expect(boton.disabled).toBe(true);
  fireEvent.click(screen.getByLabelText("Confirmo que quiero eliminar este acto/documento del repositorio"));
  fireEvent.click(boton);
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({ path: "documento/eliminar", body: { id: overview.repositorio.filas[0].id, confirmar: true } });
});

test("cargar acto de designación: docentes del período actual, dependencia obligatoria y multipart", async () => {
  await abrir("➕ Cargar acto");
  expect(screen.getByText("Docentes alcanzados por la resolución")).toBeTruthy();
  await waitFor(() => expect(envios.find((e) => e.path === "docentes")?.body).toEqual({ modo: "Designaciones activas del período actual" }));
  const boton = () => screen.getByRole("button", { name: /Guardar acto respaldatorio/ }) as HTMLButtonElement;
  expect(screen.getByText("Seleccioná al menos un docente para este tipo de resolución.")).toBeTruthy();
  expect(screen.getByText("Seleccioná la dependencia que emitió esta resolución o disposición.")).toBeTruthy();
  expect(boton().disabled).toBe(true);
  const checks = await screen.findAllByRole("checkbox", { name: "Seleccionar" });
  fireEvent.click(checks[0]);
  fireEvent.click(checks[1]);
  expect(screen.getByText(/Referencia automática:/)).toBeTruthy();
  // 6A-B3: se piden y muestran las designaciones de los docentes elegidos; se elige una concreta por id
  await waitFor(() => expect(envios.filter((e) => e.path === "designaciones").at(-1)?.body).toEqual({ cuiles: [fx.docentes.filas[0].CUIL, fx.docentes.filas[1].CUIL] }));
  fireEvent.click(await screen.findByRole("checkbox", { name: /^ID 501 · ZZNEXT Docente · 2026 1C · Adjunto · Simple · Interino · 2026-03-01 → 2026-07-31 · Activa/ }));
  expect(screen.getByRole("checkbox", { name: /^ID 502 · .* · 2025 2C · .* · Finalizada/ })).toBeTruthy();
  const dependencia = screen.getByLabelText(/^Dependencia emisora/) as HTMLSelectElement;
  fireEvent.change(dependencia, { target: { value: "Rectorado" } });
  expect(boton().disabled).toBe(false);
  fireEvent.change(screen.getByPlaceholderText("Ej.: 123/2026"), { target: { value: "ZZNEXT-1/2026" } });
  fireEvent.change(screen.getByLabelText("PDF respaldatorio (opcional; puede cargarse después)"), {
    target: { files: [new File(["%PDF-1.4\n%%EOF"], "acto.pdf", { type: "application/pdf" })] },
  });
  fireEvent.click(boton());
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  const e = escrituras()[0];
  expect(e.path).toBe("actos/guardar");
  const datos = e.body as Record<string, unknown>;
  expect(datos).toMatchObject({ categoria: "Designación docente", tipo_documento: "Resolución", numero: "ZZNEXT-1/2026",
    modo_docentes: "Designaciones activas del período actual" });
  expect(datos.docentes).toEqual([fx.docentes.filas[0].CUIL, fx.docentes.filas[1].CUIL]);
  expect(datos.designaciones).toEqual([501]);
  expect(datos.reemplazar_vinculos).toBe(false);
  expect(datos.dependencia_id).toBe(overview.alta.dependencias.find((o) => o.etiqueta === "Rectorado")?.id);
  expect((e.form?.get("archivo") as File).name).toBe("acto.pdf");
  expect(await screen.findByText(/Acto guardado correctamente/)).toBeTruthy();
});

test("cargar acto de proyecto de investigación sugiere Disposición y envía los proyectos elegidos", async () => {
  await abrir("➕ Cargar acto");
  fireEvent.change(screen.getByLabelText("¿Qué respalda este documento?"), { target: { value: "Proyecto de Investigación" } });
  expect((screen.getByLabelText("Tipo de documento") as HTMLSelectElement).value).toBe("Disposición");
  await waitFor(() => expect(envios.find((e) => e.path === "proyectos")?.body).toEqual({ tipo: "investigacion" }));
  const checks = await screen.findAllByRole("checkbox", { name: "Seleccionar" });
  fireEvent.click(checks[2]);
  fireEvent.change(screen.getByLabelText(/^Dependencia emisora/), { target: { value: "Secretaría de Ciencia y Tecnología" } });
  fireEvent.click(screen.getByRole("button", { name: /Guardar acto respaldatorio/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect((escrituras()[0].body as Record<string, unknown>).proyectos).toEqual([fx.proyectos.filas[2].ID]);
  expect(escrituras()[0].form?.get("archivo")).toBeNull();
});

test("solo lectura: sin acciones, Cargar acto con aviso y Dependencias vacía (D-AK5)", async () => {
  overview = fx.lector;
  await abrir();
  await seleccionarPrimero();
  expect(screen.queryByText("🏛️ Asignar o corregir dependencia emisora")).toBeNull();
  expect(screen.queryByText(/Reemplazar PDF|Adjuntar PDF pendiente/)).toBeNull();
  expect(screen.queryByRole("button", { name: /Eliminar documento/ })).toBeNull();
  expect(screen.getByRole("button", { name: /Descargar PDF/ })).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "➕ Cargar acto" }));
  expect(screen.getByText("Tu usuario tiene permisos de solo lectura.")).toBeTruthy();
  fireEvent.click(screen.getByRole("tab", { name: "🏛️ Dependencias" }));
  expect(within(screen.getByRole("tabpanel")).queryByText(/Dependencias emisoras|Agregar dependencia/)).toBeNull();
});

test("dependencias: métricas, alta y edición institucional", async () => {
  await abrir("🏛️ Dependencias");
  expect(screen.getByText("Dependencias activas")).toBeTruthy();
  fireEvent.change(screen.getByPlaceholderText("Ej.: Secretaría de Ciencia y Tecnología"), { target: { value: "ZZNEXT Secretaría" } });
  fireEvent.click(screen.getByRole("button", { name: /Agregar dependencia/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(1));
  expect(escrituras()[0]).toEqual({ path: "dependencias/agregar", body: { nombre: "ZZNEXT Secretaría", observaciones: "" } });
  fireEvent.click(await screen.findByRole("button", { name: /Guardar cambios de la dependencia/ }));
  await waitFor(() => expect(escrituras()).toHaveLength(2));
  expect(escrituras()[1].path).toBe("dependencias/editar");
  expect(escrituras()[1].body).toMatchObject({ id: overview.dependencias.opciones_edicion[0].id, estado: "Activa" });
});
