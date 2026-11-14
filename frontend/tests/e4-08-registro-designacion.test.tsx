// E4-08: registrar una designación desde la pestaña "Registrar docente" de Docentes (3 caminos certificados). Datos
// SINTÉTICOS con la forma exacta de POST /docentes/designacion/contexto y /verificar-cuil; las escrituras no llegan a
// ningún backend: se verifica el cuerpo exacto que recibe POST /docentes/designacion.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";
import type { ContextoDesignacion, Docente, DocentesOverview, VerificacionCuil } from "@/lib/docentes";

const MODO_BASE = "Seleccionar un docente de la base maestra y registrar su designación en el período actual";

const docente = (cuil: string, nombre: string): Docente => ({
  cuil, legajo: "L-1", apellido: nombre, nombres: "X", nombre_completo: `${nombre}, X`, titulo: "Lic.",
  titulo_posgrado: "", antiguedad_anios: null, nivel_posgrado_salarial: "", email: null, telefono: null,
  ref_legajo_fisico: null, tipo_docente: "Propio", observaciones: "", estado: "Activo", fecha_alta: "2026-03-01",
  fecha_finalizacion: "", estado_periodo_abierto: "Sin designación registrada", huella: `h-${cuil}` });

const overview = (escribir: boolean): DocentesOverview => ({
  contexto: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep" } },
  abierto: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31", estado: "Abierto" },
  actual: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31", estado: "Abierto" },
  historico: false,
  docentes: [docente("20-11111111-1", "Alfa"), docente("20-22222222-2", "Beta")],
  catalogos: { estados: ["Activo"], estados_baja: [], tipos: ["Propio", "Prestado"], niveles_posgrado: [""],
    antiguedad_min: 0, antiguedad_max: 80 },
  permisos: { puede_escribir: escribir, puede_borrar: false, es_superadmin: false },
});

const contexto = (escribir: boolean, extra: Partial<ContextoDesignacion> = {}): ContextoDesignacion => ({
  abierto: { id: 9, nombre: "2026-2", fecha_inicio: "2026-08-01", fecha_fin: "2026-12-31" },
  abierto_huella: "hp-9",
  catalogos: {
    cargos: ["Titular", "Asociado", "Adjunto", "JTP"], dedicaciones: ["Simple", "Parcial", "Exclusiva"],
    horas_por_dedicacion: { Simple: 10, Parcial: 20, Exclusiva: 40 }, tipos: ["Concursado", "Interino"],
    estados: ["Activa", "Finalizada", "Suspendida"], ad_honorem: ["No", "Sí"],
  },
  reincorporables: [
    { nombre_completo: "Alfa, X", cuil: "20-11111111-1", legajo: "L-1", titulo: "Lic.", estado: "Activo", huella: "h-1" },
    { nombre_completo: "Beta, X", cuil: "20-22222222-2", legajo: null, titulo: null, estado: "Activo", huella: "h-2" },
  ],
  puede_escribir: escribir,
  ...extra,
});

let ov: DocentesOverview;
let ctx: ContextoDesignacion;
let verif: VerificacionCuil | null;
let duplicada: boolean;
let respuesta: { status: number; body: unknown };
let envios: Record<string, unknown>[];

beforeEach(() => {
  ov = overview(true);
  ctx = contexto(true);
  verif = null;
  duplicada = false;
  respuesta = { status: 200, body: { mensaje: "Docente reincorporado y designación registrada correctamente.", tono: "success", avisos: [] } };
  envios = [];
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status });
    const method = init?.method ?? "GET";
    if (url === "/api/docentes" && method === "GET") return ok(ov);
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (url === "/api/docentes/designacion/contexto") return ok(ctx);
    if (url === "/api/docentes/designacion/duplicado") return ok({ duplicada });
    if (url === "/api/docentes/verificar-cuil") return ok(verif ?? { cuil_limpio: body.cuil, otros_departamentos: [], local: null });
    if (url === "/api/docentes/designacion") {
      envios.push(body);
      return ok(respuesta.body, respuesta.status);
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

test("camino 1: reincorporar desde la base maestra — textos, tabla, defaults del período, aviso de duplicado y cuerpo exacto", async () => {
  await abrirRegistrar();
  fireEvent.click(screen.getByRole("radio", { name: MODO_BASE }));
  await screen.findByText(/Esta opción recupera un docente propio que ya existe en la base maestra/);
  expect(screen.queryByText(/Se habilitará cuando se migre/)).toBeNull();
  expect(screen.getByText("Docentes encontrados")).toBeTruthy();
  expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["", "Docente", "CUIL", "Legajo", "Título", "Estado"]);
  expect(screen.getByText("Legajo: L-1 · Título: Lic. · Estado en base maestra: Activo")).toBeTruthy();
  expect(screen.getByText("Nueva designación para el período")).toBeTruthy();
  expect(campo("Fecha desde").value).toBe("2026-08-01");
  expect(campo("Fecha hasta").value).toBe("2026-12-31");
  expect(campo("Tipo designación").value).toBe("Concursado");
  expect(campo("Ad Honorem").value).toBe("No");
  expect(campo("Estado").value).toBe("Activa");
  expect(campo("Observaciones").placeholder).toBe("Dato opcional de la nueva designación.");
  fireEvent.change(campo("Dedicación"), { target: { value: "Parcial" } });
  expect(screen.getByText("20 hs")).toBeTruthy();
  fireEvent.click(screen.getByRole("checkbox", { name: "Esta designación corresponde a funciones no docentes" }));
  fireEvent.change(campo("Funciones que cumplirá"), { target: { value: "de tutoría." } });
  expect(screen.getByText("Vista previa: «…el cumplimiento de funciones de tutoría.»")).toBeTruthy();
  // segunda fila de la búsqueda
  fireEvent.change(campo("Buscar en la base maestra"), { target: { value: "beta" } });
  expect(screen.getByText("Legajo: - · Título: - · Estado en base maestra: Activo")).toBeTruthy();
  duplicada = true;
  fireEvent.change(campo("Cargo"), { target: { value: "JTP" } });
  await screen.findByText(/Mientras completabas el formulario se registró una designación exactamente igual/, {}, { timeout: 3000 });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Registrar designación y reincorporar al período" })));
  await waitFor(() => expect(envios).toHaveLength(1));
  expect(envios[0]).toEqual({
    camino: "reincorporar", cuil: "20-22222222-2", huella: "h-2", abierto_huella: "hp-9", cargo: "JTP",
    dedicacion: "Parcial", tipo_designacion: "Concursado", ad_honorem: "No", fecha_desde: "2026-08-01",
    fecha_hasta: "2026-12-31", estado: "Activa", funcion_no_docente: true, texto_funcion_no_docente: "de tutoría.",
    observaciones: "",
  });
  await screen.findByText("Docente reincorporado y designación registrada correctamente.");
});

test("camino 1: sin período abierto, lista vacía y rol de solo lectura (botón deshabilitado con la ayuda certificada)", async () => {
  ctx = contexto(true, { abierto: null, reincorporables: [] });
  await abrirRegistrar();
  fireEvent.click(screen.getByRole("radio", { name: MODO_BASE }));
  await screen.findByText("No hay un período abierto. Abrí o creá el período actual antes de reincorporar docentes.");
  cleanup();
  ctx = contexto(true, { reincorporables: [] });
  await abrirRegistrar();
  fireEvent.click(screen.getByRole("radio", { name: MODO_BASE }));
  await screen.findByText(/No hay docentes propios pendientes de reincorporación/);
  cleanup();
  ov = overview(false);
  ctx = contexto(false);
  await abrirRegistrar();
  fireEvent.click(screen.getByRole("radio", { name: MODO_BASE }));
  const boton = (await screen.findByRole("button", { name: "💾 Registrar designación y reincorporar al período" })) as HTMLButtonElement;
  expect(boton.disabled).toBe(true);
  expect(boton.parentElement!.getAttribute("title")).toBe("Tu rol permite visualizar, pero no cargar, editar ni generar cambios.");
});

test("camino 2: CUIL de otro departamento → 'Registrar como propio…' arma el formulario certificado y envía la coincidencia", async () => {
  verif = {
    cuil_limpio: "27-33333333-3",
    otros_departamentos: [{ nombre_completo: "Gama, Y", cuil: "27-33333333-3", legajo: "9", departamento_origen: "Dto. Otro" } as never],
    local: null,
  };
  respuesta = { status: 200, body: { mensaje: "Docente propio/compartido y designación registrados correctamente.", tono: "success" } };
  await abrirRegistrar();
  fireEvent.change(campo("CUIL"), { target: { value: "27-33333333-3" } });
  await screen.findByText(/El CUIL ya pertenece a un docente registrado en otro departamento/, {}, { timeout: 3000 });
  await screen.findByText("Designación en el período actual");
  expect(campo("Tipo de designación").value).toBe("Concursado");
  expect(campo("Observaciones de la designación").placeholder).toBe("");
  fireEvent.change(campo("Cargo"), { target: { value: "Adjunto" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Registrar como propio y guardar designación" })));
  await waitFor(() => expect(envios).toHaveLength(1));
  expect(envios[0]).toMatchObject({ camino: "cuil_existente", cuil: "27-33333333-3", departamento_origen: "Dto. Otro",
    cuil_alta: "27-33333333-3", cargo: "Adjunto", abierto_huella: "hp-9" });
  await screen.findByText("Docente propio/compartido y designación registrados correctamente.");
});

test("camino 3: CUIL ya local → aviso + formulario; error del backend visible sin otra escritura", async () => {
  verif = { cuil_limpio: "20-44444444-4", otros_departamentos: [], local: { cuil: "20-44444444-4", tipo_docente: "Propio", nombre: "Delta, Z" } };
  respuesta = { status: 422, body: { error: { code: "FECHAS", message: "La fecha hasta no puede ser anterior a la fecha desde." } } };
  await abrirRegistrar();
  fireEvent.change(campo("CUIL"), { target: { value: "20-44444444-4" } });
  await screen.findByText("Este CUIL ya está registrado en el departamento actual como Delta, Z.", {}, { timeout: 3000 });
  await screen.findByText("Designación en el período actual");
  fireEvent.change(campo("Fecha hasta"), { target: { value: "2026-01-01" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "💾 Registrar una nueva designación para este docente" })));
  await screen.findByText("La fecha hasta no puede ser anterior a la fecha desde.");
  expect(envios).toHaveLength(1);
  expect(envios[0]).toMatchObject({ camino: "cuil_local", cuil_alta: "20-44444444-4", fecha_hasta: "2026-01-01" });
});
