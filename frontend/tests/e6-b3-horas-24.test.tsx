// Regla global de horarios (6A-B3, aceptación humana): HH:mm en 24 h, nunca AM/PM ni dependiente del locale; minutos
// 00/15/30/45 en selecciones nuevas; un horario histórico con otros minutos (08:10) se muestra y se envía sin cambios.
// Comisiones (único lugar con selección de hora) con el módulo completo y las fixtures reales de la API.
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, test, vi } from "vitest";
import { ComisionesModule } from "@/components/comisiones-module";
import { HoraInput } from "@/components/hora-input";
import type { Detalle, Overview } from "@/lib/comisiones";
import { HORAS_24, MINUTOS_PASO, formatoHora24, opcionesMinutos } from "@/lib/hora";

const SIN_AM_PM = /\b(AM|PM|a\.\s?m\.|p\.\s?m\.)\b/i;

describe("utilidad común de horas (24 h)", () => {
  test.each([
    ["00:00", "00:00"],
    ["08:15", "08:15"],
    ["12:30", "12:30"],
    ["17:45", "17:45"],
    ["23:45", "23:45"],
    ["23:00", "23:00"],
    ["8:15", "08:15"],
    ["08:15:00", "08:15"],
    ["12:00 AM", "00:00"],
    ["12:30 PM", "12:30"],
    ["5:45 pm", "17:45"],
    ["11:45 p. m.", "23:45"],
  ])("%s -> %s", (entrada, esperado) => {
    expect(formatoHora24(entrada)).toBe(esperado);
    expect(formatoHora24(entrada)).not.toMatch(SIN_AM_PM);
  });

  test("histórico con minutos no múltiplos de 15: se conserva (no se redondea)", () => {
    expect(formatoHora24("08:10")).toBe("08:10");
    expect(opcionesMinutos("10")).toEqual(["00", "10", "15", "30", "45"]);
    expect(opcionesMinutos("15")).toEqual(MINUTOS_PASO);
  });

  test("catálogos: horas 00-23 y minutos 00/15/30/45", () => {
    expect(HORAS_24).toHaveLength(24);
    expect(HORAS_24[0]).toBe("00");
    expect(HORAS_24[23]).toBe("23");
    expect(MINUTOS_PASO).toEqual(["00", "15", "30", "45"]);
  });
});

describe("HoraInput", () => {
  afterEach(cleanup);

  test("selector Hora + Minutos, sin input nativo de hora y sin AM/PM", () => {
    const cambios: string[] = [];
    const { container } = render(<HoraInput label="Hora" value="17:45" onChange={(v) => cambios.push(v)} />);
    expect(container.querySelector('input[type="time"]')).toBeNull();
    const h = screen.getByRole("combobox", { name: "Hora (hora)" }) as HTMLSelectElement;
    const m = screen.getByRole("combobox", { name: "Hora (minutos)" }) as HTMLSelectElement;
    expect(Array.from(h.options).map((o) => o.value)).toEqual(HORAS_24);
    expect(Array.from(m.options).map((o) => o.value)).toEqual(["00", "15", "30", "45"]);
    expect(h.value).toBe("17");
    expect(m.value).toBe("45");
    expect(container.textContent).not.toMatch(SIN_AM_PM);
    fireEvent.change(h, { target: { value: "00" } });
    fireEvent.change(m, { target: { value: "15" } });
    expect(cambios).toEqual(["00:45", "17:15"]);
  });

  test("valor histórico 08:10: se muestra 08:10 y los minutos ofrecen 10 sin redondear", () => {
    const onChange = vi.fn();
    render(<HoraInput label="Inicio" value="08:10" onChange={onChange} />);
    expect((screen.getByRole("combobox", { name: "Inicio (hora)" }) as HTMLSelectElement).value).toBe("08");
    const m = screen.getByRole("combobox", { name: "Inicio (minutos)" }) as HTMLSelectElement;
    expect(m.value).toBe("10");
    expect(Array.from(m.options).map((o) => o.value)).toEqual(["00", "10", "15", "30", "45"]);
    expect(onChange).not.toHaveBeenCalled();
  });
});

// --- Comisiones: creación, edición, franjas, inicio/fin y el cuerpo que se persiste --------------------------------
type Fx = {
  overview: Overview;
  periodos: Record<string, unknown>;
  alertas: unknown;
  sedes: unknown;
  inscriptos: Record<string, unknown>;
  materias: { respuesta: unknown };
  materia: { respuesta: unknown };
  docentes: { docentes: { cuil: string; etiqueta_alta: string }[] };
  roles: Record<string, { roles: string[]; prestado_local: boolean }>;
  lista_modificacion: unknown;
  detalle_modificacion: Detalle;
  lista_edicion: { filas: { id: number }[] };
  detalle_edicion: Detalle;
  datos_edicion: unknown;
};
const fx: Fx = JSON.parse(readFileSync(join(process.cwd(), "tests", "fixtures", "comisiones_uno.json"), "utf8"));
const LECTURAS = new Set(["periodo", "alertas", "sedes", "inscriptos", "abrir/materias", "abrir/materia", "docentes",
  "docentes/roles", "lista", "detalle", "edicion/datos", "carga-rapida/previsualizar", "asignacion/franjas"]);
let detalleEdicion: Detalle;
let posts: { path: string; body: Record<string, unknown> }[] = [];
const escrituras = () => posts.filter((p) => !LECTURAS.has(p.path));

describe("Comisiones en 24 h", () => {
  beforeEach(() => {
    posts = [];
    detalleEdicion = fx.detalle_edicion;
    vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
      const ok = (data: unknown) => new Response(JSON.stringify(data), { status: 200 });
      if (url === "/api/comisiones" && (init?.method ?? "GET") === "GET") return ok(fx.overview);
      const path = url.replace("/api/comisiones/", "");
      const body = JSON.parse(String(init?.body ?? "{}"));
      posts.push({ path, body });
      if (path === "periodo") return ok(fx.periodos[String(body.periodo_id)] ?? { vacio: true });
      if (path === "alertas") return ok(fx.alertas);
      if (path === "sedes") return ok(fx.sedes);
      if (path === "inscriptos") return ok(fx.inscriptos[String(body.periodo_id)] ?? { legacy: [], vacio: true });
      if (path === "abrir/materias") return ok(fx.materias.respuesta);
      if (path === "abrir/materia") return ok(fx.materia.respuesta);
      if (path === "docentes") return ok(fx.docentes);
      if (path === "docentes/roles") return ok(fx.roles[String(body.cuil)] ?? { roles: [], prestado_local: false });
      if (path === "lista") return ok(body.contexto === "modificacion" ? fx.lista_modificacion : fx.lista_edicion);
      if (path === "detalle") return ok(body.contexto === "modificacion" ? fx.detalle_modificacion : detalleEdicion);
      if (path === "edicion/datos") return ok(fx.datos_edicion);
      return ok({ mensaje: "OK (respuesta simulada del test)", tono: "success" });
    });
  });
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  const elegir = (nombre: string, valor: string) =>
    fireEvent.change(screen.getByRole("combobox", { name: nombre }), { target: { value: valor } });

  async function abrir(tab: string) {
    const r = render(<ComisionesModule onAuthError={() => {}} />);
    await screen.findByRole("heading", { name: "📋 Módulo Comisiones" }, { timeout: 5000 });
    fireEvent.click(screen.getByRole("tab", { name: tab }));
    return r;
  }

  test("abrir comisión: horario 17:45–23:45 y franja docente 17:45–23:45 en el cuerpo enviado", async () => {
    const { container } = await abrir("➕ Abrir comisión");
    await screen.findByText(/^Materias encontradas: /, {}, { timeout: 5000 });
    fireEvent.change(screen.getByPlaceholderText("Ej.: 1, 2, A, B"), { target: { value: "ZZ24" } });
    elegir("Hora de inicio 1 (hora)", "17");
    elegir("Hora de inicio 1 (minutos)", "45");
    elegir("Hora de finalización 1 (hora)", "23");
    elegir("Hora de finalización 1 (minutos)", "45");
    const doc = fx.docentes.docentes[0];
    fireEvent.click(await screen.findByRole("checkbox", { name: doc.etiqueta_alta }, { timeout: 5000 }));
    await screen.findByText("Horario efectivo que cubrirá este docente", {}, { timeout: 5000 });
    expect(container.querySelector('input[type="time"]')).toBeNull();
    expect(container.textContent).not.toMatch(SIN_AM_PM);
    fireEvent.click(screen.getByRole("button", { name: "➕ Abrir comisión con horarios y docentes" }));
    await waitFor(() => expect(escrituras().length).toBe(1));
    const body = escrituras()[0].body as { horarios: unknown; docentes: { franjas: unknown }[] };
    expect(body.horarios).toEqual([{ dia: "Lunes", hora_inicio: "17:45", hora_fin: "23:45" }]);
    expect(body.docentes[0].franjas).toEqual([{ usar: true, desde: "17:45", hasta: "23:45" }]);
  });

  test("editar / agregar horario: histórico 08:10 se reabre como 08:10 y se envía sin redondear; nuevo 00:00–12:30", async () => {
    const h0 = detalleEdicion.horarios[0];
    detalleEdicion = { ...fx.detalle_edicion, horarios: [{ ...h0, hora_inicio: "08:10", hora_fin: "12:30" }, ...fx.detalle_edicion.horarios.slice(1)] };
    const { container } = await abrir("✏️ Editar / eliminar");
    await screen.findByText(/^Comisión seleccionada · /, {}, { timeout: 5000 });
    const sub = screen.getByRole("tablist", { name: "Secciones de corrección" });
    fireEvent.click(within(sub).getByRole("tab", { name: "🕒 Horarios" }));
    expect((screen.getByRole("combobox", { name: "Hora de inicio (hora)" }) as HTMLSelectElement).value).toBe("08");
    expect((screen.getByRole("combobox", { name: "Hora de inicio (minutos)" }) as HTMLSelectElement).value).toBe("10");
    expect(container.textContent).not.toMatch(SIN_AM_PM);
    fireEvent.click(screen.getByRole("button", { name: "✏️ Guardar cambios del horario" }));
    await waitFor(() => expect(escrituras().length).toBe(1));
    expect(escrituras()[0].body).toEqual(expect.objectContaining({ horario_id: h0.id, hora_inicio: "08:10", hora_fin: "12:30" }));

    const hs = screen.getByRole("tablist", { name: "Acciones sobre horarios" });
    fireEvent.click(within(hs).getByRole("tab", { name: "➕ Agregar horario" }));
    elegir("Hora de inicio (hora)", "00");
    elegir("Hora de inicio (minutos)", "00");
    elegir("Hora de finalización (minutos)", "30");
    fireEvent.click(screen.getByRole("button", { name: "➕ Agregar horario" }));
    await waitFor(() => expect(escrituras().length).toBe(2));
    expect(escrituras()[1].body).toEqual(expect.objectContaining({ hora_inicio: "00:00", hora_fin: "12:30" }));
    expect(container.textContent).not.toMatch(SIN_AM_PM);
  });
});
