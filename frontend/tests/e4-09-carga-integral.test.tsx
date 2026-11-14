// E4-09: "Carga rápida integral de docentes y designaciones" (pestaña Carga rápida de Docentes). Datos SINTÉTICOS con la
// forma exacta de POST /docentes/carga-integral/previsualizar y /docentes/carga-integral; nada llega a un backend: se
// verifica el multipart exacto (parte "datos" JSON + parte "archivo") y el JSON del modelo.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";
import type { DocentesOverview, ResultadoIntegral, RevisionIntegral } from "@/lib/docentes";

const overview = (escribir: boolean): DocentesOverview => ({
  contexto: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep" } },
  abierto: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31", estado: "Abierto" },
  actual: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31", estado: "Abierto" },
  historico: false,
  docentes: [],
  catalogos: { estados: ["Activo"], estados_baja: [], tipos: ["Propio", "Prestado"], niveles_posgrado: [""],
    antiguedad_min: 0, antiguedad_max: 80 },
  permisos: { puede_escribir: escribir, puede_borrar: false, es_superadmin: false },
});

const REV: RevisionIntegral = {
  avisos: [], filas_docentes: 2, filas_designaciones: 3, docentes_nuevos: 1, docentes_existentes: 1,
  designaciones_nuevas: 2, designaciones_omitidas: 1, designaciones_detectadas: 3, errores_docentes: 0,
  errores_designaciones: 0, errores: 0, sin_errores: true,
  docentes: [
    { fila: 2, cuil: "20-1", apellido: "Nuevo", nombres: "Uno", legajo: "", antiguedad_anios: "", nivel_posgrado_salarial: "",
      estado: "Activo", accion: "Crear docente", motivo: "Datos válidos" },
    { fila: 3, cuil: "20-2", apellido: "", nombres: "", legajo: "L-9", antiguedad_anios: "", nivel_posgrado_salarial: "",
      estado: "Activo", accion: "Actualizar campos informados u omitir",
      motivo: "Ya existe; si elegís actualizar, solo se modificarán las celdas con valor" },
  ],
  designaciones: [
    { fila: 2, periodo: "2026-2", docente: "Nuevo, Uno", cuil: "20-1", cargo: "JTP", dedicacion: "Simple", horas: 10,
      tipo_designacion: "Interino", numero_resolucion: "", ad_honorem: "No", fecha_desde: "2026-08-01",
      fecha_hasta: "2026-12-31", estado: "Activa", accion: "Crear designación", motivo: "Falta N° de resolución de la designación" },
  ],
  huella: "h-rev-1",
};
const RES: ResultadoIntegral = {
  mensaje: "Carga integral verificada. Docentes nuevos: 1. Docentes actualizados: 1. Docentes existentes omitidos: 0. " +
    "Designaciones nuevas realmente guardadas: 1. Duplicadas omitidas desde la revisión: 1. Errores: 1.",
  tono: "warning", errores: 1,
  detalle: [{ Fila: 2, Docente: "Nuevo, Uno", CUIL: "20-1", Período: "2026-2", Resultado: "Creada", Detalle: "Verificada en la base de datos." }],
  errores_detalle: ["Designación fila 4: La base de datos devolvió un error durante la operación: la transacción se revirtió completa."],
};

let ov: DocentesOverview;
let rev: RevisionIntegral | { status: number; error: string };
let envios: { path: string; datos: unknown; archivo: string | null; json?: unknown }[];

beforeEach(() => {
  ov = overview(true);
  rev = REV;
  envios = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status });
    if (url === "/api/docentes" && (init?.method ?? "GET") === "GET") return ok(ov);
    const path = url.replace("/api/docentes/", "");
    if (init?.body instanceof FormData) {
      const a = init.body.get("archivo");
      envios.push({ path, datos: JSON.parse(String(init.body.get("datos"))), archivo: a instanceof File ? a.name : null });
      if (path === "carga-integral/previsualizar") {
        return "status" in rev ? ok({ error: { code: "LECTURA", message: rev.error } }, rev.status) : ok(rev);
      }
      if (path === "carga-integral") return ok(RES);
    }
    if (path === "carga-integral/modelo") {
      envios.push({ path, datos: null, archivo: null, json: JSON.parse(String(init?.body)) });
      return new Response(new Blob(["PK"]), { status: 200 });
    }
    return ok({ error: { code: "NOT_FOUND", message: "no" } }, 404);
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir() {
  render(<DocentesModule onAuthError={() => {}} />);
  fireEvent.click(await screen.findByRole("tab", { name: /Carga rápida/ }));
  await screen.findByText("Carga rápida integral de docentes y designaciones");
}

const subir = (nombre = "integral.xlsx") =>
  fireEvent.change(screen.getByLabelText("Subir Excel integral completado"), {
    target: { files: [new File(["PK"], nombre)] },
  });

test("sección certificada sin 'Pendiente': textos, modelo con filas elegidas y revisión con métricas, controles y tablas", async () => {
  URL.createObjectURL = vi.fn(() => "blob:x");
  URL.revokeObjectURL = vi.fn();
  await abrir();
  expect(screen.queryByText(/Se habilitará cuando se migre/)).toBeNull();
  expect(screen.getByText(/No existe un cupo de docentes ni de designaciones por departamento/)).toBeTruthy();
  expect(screen.getByText("⚙️ Tamaño inicial del modelo Excel")).toBeTruthy();
  const docField = screen.getByText("Filas preformateadas — Docentes").closest("label")!.querySelector("input")!;
  expect((docField as HTMLInputElement).value).toBe("1000");
  fireEvent.change(docField, { target: { value: "200" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "📥 Descargar Excel integral de docentes y designaciones" })));
  await waitFor(() => expect(envios.find((e) => e.path === "carga-integral/modelo")?.json).toEqual({ filas_docentes: 200, filas_designaciones: 5000 }));
  subir();
  await screen.findByText("Docentes nuevos");
  expect(envios.filter((e) => e.path === "carga-integral/previsualizar")).toEqual([
    { path: "carga-integral/previsualizar", datos: {}, archivo: "integral.xlsx" }]);
  expect(screen.getByText("Designaciones duplicadas que se omitirán automáticamente: 1.")).toBeTruthy();
  expect(screen.getByText("Control de Designaciones: detectadas 3 | nuevas 2 | duplicadas 1 | errores 0.")).toBeTruthy();
  expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(
    ["fila", "cuil", "apellido", "nombres", "legajo", "antiguedad_anios", "nivel_posgrado_salarial", "estado", "accion", "motivo"]);
  fireEvent.click(screen.getByRole("tab", { name: "📋 Revisión de designaciones" }));
  expect(screen.getByText("Falta N° de resolución de la designación")).toBeTruthy();
  expect(screen.getByRole("checkbox", { name: "Actualizar los datos personales de los docentes que ya existen" })).toBeTruthy();
});

test("carga: sin confirmar avisa sin enviar; confirmada envía el multipart exacto, muestra el resultado y vuelve a revisar", async () => {
  await abrir();
  subir();
  await screen.findByText("Docentes nuevos");
  const boton = screen.getByRole("button", { name: "📥 Cargar docentes y designaciones del Excel" });
  await act(async () => fireEvent.click(boton));
  expect(screen.getByText("Primero confirmá que revisaste el archivo.")).toBeTruthy();
  expect(envios.filter((e) => e.path === "carga-integral")).toHaveLength(0);
  fireEvent.click(screen.getByRole("checkbox", { name: "Actualizar los datos personales de los docentes que ya existen" }));
  expect(screen.getByText(/Actualización parcial activa/)).toBeTruthy();
  fireEvent.click(screen.getByRole("checkbox", { name: "Confirmo que revisé el archivo y quiero registrar los datos válidos" }));
  await act(async () => fireEvent.click(boton));
  await screen.findByText(RES.mensaje);
  expect(envios.find((e) => e.path === "carga-integral")).toEqual({
    path: "carga-integral", archivo: "integral.xlsx", datos: { confirmar: true, actualizar_existentes: true, huella: "h-rev-1" } });
  expect(screen.getByText("Verificación contra la base de datos")).toBeTruthy();
  const errores = screen.getByText("Ver errores de ejecución").closest("details")!;
  expect(within(errores).getByText(RES.errores_detalle[0])).toBeTruthy();
  await waitFor(() => expect(envios.filter((e) => e.path === "carga-integral/previsualizar")).toHaveLength(2));
});

test("revisión con errores: confirmación y botón deshabilitados con el mensaje certificado; error de lectura visible", async () => {
  rev = { ...REV, errores: 2, errores_designaciones: 2, sin_errores: false };
  await abrir();
  subir();
  await screen.findByText("Corregí los errores indicados en el Excel y volvé a subirlo. No se guardó ningún dato.");
  expect((screen.getByRole("checkbox", { name: /Confirmo que revisé el archivo/ }) as HTMLInputElement).disabled).toBe(true);
  expect((screen.getByRole("button", { name: "📥 Cargar docentes y designaciones del Excel" }) as HTMLButtonElement).disabled).toBe(true);
  cleanup();
  rev = { status: 422, error: "No se pudo leer o validar el Excel integral: El archivo debe contener una hoja llamada Designaciones." };
  await abrir();
  subir();
  await screen.findByText(rev.error);
});

test("rol sin escritura: puede revisar, pero el botón de carga queda deshabilitado con la ayuda certificada", async () => {
  ov = overview(false);
  await abrir();
  subir();
  await screen.findByText("Docentes nuevos");
  const boton = screen.getByRole("button", { name: "📥 Cargar docentes y designaciones del Excel" }) as HTMLButtonElement;
  expect(boton.disabled).toBe(true);
  expect(boton.parentElement!.getAttribute("title")).toBe("Tu rol permite visualizar, pero no cargar, editar ni generar cambios.");
});
