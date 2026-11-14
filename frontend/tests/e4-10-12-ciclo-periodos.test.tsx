// E4-10 / E4-11 / E4-12: pestañas Crear nuevo período, Revertir último cierre y Eliminar período (NEXT solo vacío, con
// el bloque separado P-12b "♻️ Reparar finalizaciones automáticas del período abierto"), y
// la señal P-01b "período cambiado" que recalcula al instante el aviso global E4-01. Datos SINTÉTICOS con la forma
// exacta de las respuestas de /periodos/*; nada llega a un backend: se verifica el cuerpo exacto de cada POST.
import { act, cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { ContextoHistorico } from "@/components/contexto-historico";
import { PeriodosModule } from "@/components/periodos-module";
import type { Session } from "@/lib/auth";
import type { CrearContexto, EliminarDiagnostico, PeriodosOverview, RepararDiagnostico, RevertirDiagnostico } from "@/lib/periodos";
import { emitirPeriodoCambiado } from "@/lib/periodo-cambiado";

const P = (id: number, nombre: string, estado: string) => ({
  id, nombre, anio: Number(nombre.slice(0, 4)), semestre: Number(nombre.slice(5)), fecha_inicio: `${nombre.slice(0, 4)}-01-01`,
  fecha_fin: `${nombre.slice(0, 4)}-07-31`, estado, observaciones: "",
});
const overview = (superadmin: boolean, escribir = true): PeriodosOverview => ({
  contexto: { institucion: { id: 1, nombre: "Inst" }, departamento: { id: 1, nombre: "Dep" } },
  periodos: [P(9, "2026-2", "Abierto"), P(5, "2026-1", "Cerrado")],
  abierto: P(9, "2026-2", "Abierto"),
  actual: P(9, "2026-2", "Abierto"),
  permisos: { puede_escribir: escribir, es_superadmin: superadmin },
});
const CTX = (existente = false): CrearContexto => ({
  aviso: "Al crear un período nuevo, cualquier período abierto anterior quedará cerrado. Las designaciones concursadas que sigan vigentes se incorporarán automáticamente con sus fechas originales. La opción inferior controla únicamente la renovación de designaciones no concursadas del período anterior.",
  anio_min: 2020, anio_max: 2100, anio_default: 2026,
  semestres: [{ valor: 1, etiqueta: "1° período: 01/01 al 31/07" }, { valor: 2, etiqueta: "2° período: 01/08 al 31/12" }],
  objetivo: { nombre: "2026-1", fecha_inicio: "2026-01-01", fecha_fin: "2026-07-31" },
  existente: existente ? P(5, "2026-1", "Cerrado") : null,
  gate: { activo: false, entorno: "desarrollo", aviso: "Desarrollo: el control de backup previo de Crear período está DESACTIVADO por configuración explícita (DEPTIT_BACKUP_GATE_CREAR_PERIODO=desactivado, DEPTIT_ENTORNO=desarrollo). En producción es obligatorio y el sistema no arranca con el control desactivado." },
  puede_escribir: true,
});
const REV_OK: RevertirDiagnostico = {
  info: "Esta opción sirve para deshacer el último cierre realizado por error.", es_superadmin: true, ok: true,
  mensaje: "Se puede revertir el último cierre.", periodo_nuevo: P(9, "2026-2", "Abierto"), periodo_anterior: P(5, "2026-1", "Cerrado"),
  designaciones_nuevo: 3, cierres_anterior: 2, activas_anterior: 0, bloqueos: [], puede_revertir: true, huella: "h-rev",
};

let ov: PeriodosOverview;
let ctx: CrearContexto;
let rev: RevertirDiagnostico;
let elim: EliminarDiagnostico;
let repar: RepararDiagnostico;
let envios: { path: string; body: Record<string, unknown> }[];
let avisos: number;

beforeEach(() => {
  ov = overview(true);
  ctx = CTX();
  rev = REV_OK;
  elim = { info: "Solo se puede eliminar un período realmente vacío.", es_superadmin: true };
  repar = { es_superadmin: true, visible: false };
  envios = [];
  avisos = 0;
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const ok = (d: unknown, status = 200) => new Response(JSON.stringify(d), { status });
    if (url === "/api/periodos" && (init?.method ?? "GET") === "GET") return ok(ov);
    if (url === "/api/contexto/periodo") {
      avisos += 1;
      return ok({ aviso: avisos > 1 ? { texto: "🕰️ Contexto histórico activo: **2025-2**" } : null });
    }
    const path = url.replace("/api/periodos/", "");
    const body = init?.body ? JSON.parse(String(init.body)) : {};
    if (path === "crear/contexto") return ok({ ...ctx, objetivo: { ...ctx.objetivo, nombre: `${body.anio}-${body.semestre}` } });
    if (path === "revertir/diagnostico") return ok(rev);
    if (path === "eliminar/diagnostico") return ok(elim);
    if (path === "reparar-finalizaciones/diagnostico") return ok(repar);
    envios.push({ path, body });
    return ok({ mensaje: `OK ${path}`, tono: "success", periodo_cambiado: true });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir(tab: string) {
  render(<PeriodosModule onAuthError={() => {}} />);
  fireEvent.click(await screen.findByRole("tab", { name: tab }));
}

test("Crear nuevo período: sin 'Pendiente', aviso certificado, gate visible, duplicado deshabilita y cuerpo exacto", async () => {
  await abrir("Crear nuevo período");
  expect(screen.queryByText("Pendiente")).toBeNull();
  expect(screen.queryByText("Pendiente de migración")).toBeNull();
  await screen.findByText(ctx.aviso);
  expect(screen.getByText(/control de backup previo de Crear período está DESACTIVADO/)).toBeTruthy();
  await screen.findByText(/Período a crear: 2026-1/);
  const semestre = screen.getByText("Semestre").closest("label")!.querySelector("select")!;
  expect([...semestre.options].map((o) => o.textContent)).toEqual(["1° período: 01/01 al 31/07", "2° período: 01/08 al 31/12"]);
  fireEvent.change(screen.getByText("Año").closest("label")!.querySelector("input")!, { target: { value: "2027" } });
  await screen.findByText(/Período a crear: 2027-1/, {}, { timeout: 2000 });
  fireEvent.click(screen.getByRole("checkbox", { name: "Copiar designaciones activas no concursadas del período anterior" }));
  fireEvent.change(screen.getByText("Observaciones del período").closest("label")!.querySelector("textarea")!, { target: { value: "obs" } });
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "🗓️ Crear período" })));
  await waitFor(() => expect(envios).toEqual([{ path: "crear", body: { anio: 2027, semestre: 1, copiar_anterior: false, observaciones: "obs" } }]));
  await screen.findByText("OK crear");
  cleanup();
  ctx = CTX(true);
  await abrir("Crear nuevo período");
  await screen.findByText("ya existe y no puede volver a crearse.", { exact: false });
  expect((screen.getByRole("button", { name: "🗓️ Crear período" }) as HTMLButtonElement).disabled).toBe(true);
});

test("Revertir: solo superadmin; bloqueado por dependencias sin botón; reversible con tres confirmaciones", async () => {
  ov = overview(false);
  rev = { info: "x", es_superadmin: false, mensaje_permiso: "Solo el superadmin puede revertir un cierre de período." };
  await abrir("Revertir último cierre");
  await screen.findByText("Solo el superadmin puede revertir un cierre de período.");
  expect(screen.queryByRole("button", { name: "↩️ Revertir último cierre" })).toBeNull();
  cleanup();
  ov = overview(true);
  rev = { ...REV_OK, puede_revertir: false, bloqueos: [{ tabla: "investigacion_docente", etiqueta: "Investigación", filas: 4 }],
    mensaje_bloqueo: "No se puede revertir el último cierre: el período 2026-2 ya contiene información que la reversión no elimina (Investigación: 4). No se realizó ningún cambio." };
  await abrir("Revertir último cierre");
  await screen.findByText(rev.mensaje_bloqueo!);
  expect(screen.getByText("Investigación")).toBeTruthy();
  expect(screen.queryByRole("button", { name: "↩️ Revertir último cierre" })).toBeNull();
  cleanup();
  rev = REV_OK;
  await abrir("Revertir último cierre");
  await screen.findByText("Período a eliminar");
  const boton = screen.getByRole("button", { name: "↩️ Revertir último cierre" });
  await act(async () => fireEvent.click(boton));
  expect(screen.getByText("Tenés que marcar las tres confirmaciones antes de revertir el cierre.")).toBeTruthy();
  for (const nombre of [/se eliminará el último período creado/, /se reabrirá el período anterior/, /Confirmo que quiero revertir/])
    fireEvent.click(screen.getByRole("checkbox", { name: nombre }));
  await act(async () => fireEvent.click(boton));
  await waitFor(() => expect(envios).toEqual([{ path: "revertir", body: { observaciones: "", confirmar_1: true, confirmar_2: true, confirmar_3: true, huella: "h-rev" } }]));
});

test("Eliminar (solo vacío): con datos rechazo y sin botón; vacío exige confirmación y texto exacto", async () => {
  elim = { info: "x", es_superadmin: true, periodo: P(9, "2026-2", "Abierto"), conteos: [{ tabla: "designaciones", etiqueta: "Designaciones", filas: 7 }],
    movimientos: 3, apertura_automatica: null, bloqueos: [{ tabla: "designaciones", etiqueta: "Designaciones", filas: 7 }], vacio: false,
    proximo_activo: P(5, "2026-1", "Cerrado"), texto_confirmacion: "ELIMINAR 2026-2", mensaje: "El período contiene información y no puede eliminarse.", huella: "h1" };
  await abrir("Eliminar período");
  await screen.findByText("El período contiene información y no puede eliminarse.");
  expect(screen.queryByRole("button", { name: /Eliminar período vacío/ })).toBeNull();
  expect(screen.queryByText(/TODOS los datos/)).toBeNull();
  cleanup();
  elim = { ...elim, conteos: [], movimientos: 1, apertura_automatica: 77, bloqueos: [], vacio: true, mensaje: null };
  await abrir("Eliminar período");
  await screen.findByText(/su único movimiento es la apertura automática del sistema/);
  expect(screen.getByText("Después de eliminarlo, quedará activo el período", { exact: false })).toBeTruthy();
  const boton = screen.getByRole("button", { name: "🗑️ Eliminar período vacío" });
  await act(async () => fireEvent.click(boton));
  expect(screen.getByText("Tenés que marcar la confirmación antes de eliminar el período.")).toBeTruthy();
  fireEvent.click(screen.getByRole("checkbox", { name: /se eliminará el período vacío seleccionado/ }));
  const texto = screen.getByText("Para confirmar, escribí exactamente: ELIMINAR 2026-2").closest("label")!.querySelector("input")!;
  fireEvent.change(texto, { target: { value: "ELIMINAR 2026" } });
  await act(async () => fireEvent.click(boton));
  expect(screen.getByText("La confirmación escrita no coincide. Escribí: ELIMINAR 2026-2")).toBeTruthy();
  fireEvent.change(texto, { target: { value: "ELIMINAR 2026-2" } });
  await act(async () => fireEvent.click(boton));
  await waitFor(() => expect(envios).toEqual([{ path: "eliminar", body: { periodo_id: 9, observaciones: "", confirmar: true, texto_confirmacion: "ELIMINAR 2026-2", huella: "h1" } }]));
});

test("P-12b Reparar finalizaciones: oculto sin datos o sin superadmin; aviso certificado + botón; bloqueado sin botón", async () => {
  const BOTON = "♻️ Reparar finalizaciones automáticas del período abierto";
  await abrir("Eliminar período");
  await screen.findByText("Solo se puede eliminar un período realmente vacío.");
  expect(screen.queryByTestId("reparar-finalizaciones")).toBeNull();
  cleanup();
  repar = { es_superadmin: false, visible: false };
  await abrir("Eliminar período");
  await screen.findByText("Solo se puede eliminar un período realmente vacío.");
  expect(screen.queryByRole("button", { name: BOTON })).toBeNull();
  cleanup();
  repar = { es_superadmin: true, visible: true, boton: BOTON, puede_reparar: false, movimientos_cierre: 77, designaciones_reactivables: 77,
    bloqueos: [{ tabla: "periodos", etiqueta: "el período abierto no es el último del departamento (existe 2026-2)", filas: 77 }],
    mensaje: "El período abierto 2026-1 tiene 77 finalización/es automática/s por cierre que no se pueden reparar con seguridad (x). No se realizará ningún cambio.", huella: "h0" };
  await abrir("Eliminar período");
  await screen.findByText(repar.mensaje!);
  expect(screen.getByText("el período abierto no es el último del departamento (existe 2026-2)")).toBeTruthy();
  expect(screen.queryByRole("button", { name: BOTON })).toBeNull();
  cleanup();
  repar = { ...repar, puede_reparar: true, bloqueos: [], movimientos_cierre: 3, designaciones_reactivables: 3, huella: "h-rep",
    mensaje: "El período abierto 2027-1 todavía tiene finalizaciones automáticas por cierre. Se pueden reactivar 3 designación/es y limpiar 3 movimiento/s automático/s." };
  await abrir("Eliminar período");
  await screen.findByText(repar.mensaje!);
  await act(async () => fireEvent.click(screen.getByRole("button", { name: BOTON })));
  await waitFor(() => expect(envios).toEqual([{ path: "reparar-finalizaciones", body: { huella: "h-rep" } }]));
  await screen.findByText("OK reparar-finalizaciones");
});

test("P-01b: la señal 'período cambiado' recalcula al instante el aviso global del shell, y Períodos la emite al escribir", async () => {
  const session = { contexto: {} } as unknown as Session;
  render(<ContextoHistorico session={session} />);
  await waitFor(() => expect(avisos).toBe(1));
  expect(screen.queryByTestId("aviso-contexto-historico")).toBeNull();
  act(() => emitirPeriodoCambiado());
  await screen.findByTestId("aviso-contexto-historico");
  expect(avisos).toBe(2);
  // y una escritura de Períodos (crear) la emite sin navegar ni refrescar
  await abrir("Crear nuevo período");
  await screen.findByText(/Período a crear: 2026-1/);
  await act(async () => fireEvent.click(screen.getByRole("button", { name: "🗓️ Crear período" })));
  await waitFor(() => expect(avisos).toBe(3));
});
