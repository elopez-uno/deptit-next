// E4-06: "Mensaje para consultar la designación" del Resumen docente. Respuestas SINTÉTICAS con la forma exacta de la API
// (el comportamiento real lo cubre el diferencial del backend: writer, sección y mensaje byte a byte).
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { DocentesModule } from "@/components/docentes-module";
import type { Resumen } from "@/lib/docentes";
import { OV, PERIODOS, PLANTEL, resumen } from "./resumen-fixture";

// radio por el texto de su etiqueta (el nombre accesible de "⚪" no es estable entre motores de accesibilidad)
const radio = (et: string) =>
  screen.getAllByRole("radio").find((r) => r.parentElement?.textContent === et) as HTMLInputElement;

const OPCIONES = [
  { etiqueta: "⚪ Sin estado", valor: "", semaforo: { tono: "info", texto: "⚪ Estado seleccionado: **sin estado registrado**" } },
  { etiqueta: "🟢 Designación confirmada", valor: "Designación confirmada", semaforo: { tono: "success", texto: "🟢 Estado seleccionado: **Designación confirmada**" } },
  { etiqueta: "🟡 Consulta Enviada", valor: "Consulta Enviada", semaforo: { tono: "warning", texto: "🟡 Estado seleccionado: **Consulta Enviada**" } },
  { etiqueta: "🔴 Rever Designación", valor: "Rever Designación", semaforo: { tono: "error", texto: "🔴 Estado seleccionado: **Rever Designación**" } },
] as const;
const MENSAJE = {
  asunto: "Consulta y confirmación de designación - Segundo cuatrimestre 2026",
  cuerpo: "Buen día Docente, ¿cómo estás?\n\nMi nombre es …\n\nDesignación:\n- Interino; cargo Titular; dedicación Simple; …",
  advertencias: ["No está cargado el nombre de la directora o del director en los parámetros de Disposiciones."],
};

// "base" en memoria: estado guardado por `${cuil}|${periodo_id}` (por defecto 🟢 para Uno y sin estado para los demás).
// POST /resumen/estado-consulta lo modifica y cada POST /resumen lo relee, como el backend.
let guardado: Map<string, string>;
function conConsulta(cuil: string, periodoId: number | null): Resumen {
  const periodo = PERIODOS.find((p) => p.id === periodoId) ?? PERIODOS[0];
  const r = resumen(cuil, periodo);
  const valor = guardado.get(`${cuil}|${periodo.id}`) ?? (cuil.endsWith("1-1") ? "Designación confirmada" : "");
  const seleccion = OPCIONES.find((o) => o.valor === valor)!.etiqueta;
  return { ...r, consulta: { ...r.consulta!, opciones: [...OPCIONES], seleccion } };
}

let posts: { url: string; body: Record<string, unknown> }[];
let negar: boolean;
// permisos.puede_escribir del usuario (visual_can de Docentes en el certificado); por defecto, usuario con escritura
let escribe: boolean;

beforeEach(() => {
  posts = [];
  negar = false;
  escribe = true;
  guardado = new Map();
  vi.stubGlobal("fetch", async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    const ok = (d: unknown) => new Response(JSON.stringify(d), { status: 200 });
    if (url === "/api/docentes" && method === "GET") return ok({ ...OV, permisos: { ...OV.permisos, puede_escribir: escribe } });
    if (url === "/api/docentes/plantel") return ok(PLANTEL);
    const body = JSON.parse(String(init?.body ?? "{}"));
    posts.push({ url, body });
    // respuesta asíncrona (como la red): deja ver el render intermedio con el resumen anterior
    if (url === "/api/docentes/resumen") return new Promise((res) => setTimeout(() => res(ok(conConsulta(body.cuil, body.periodo_id))), 5));
    if (url === "/api/docentes/resumen/estado-consulta") {
      if (negar)
        return new Response(JSON.stringify({ error: { code: "DENIED", message: "⛔ Tu rol no permite esta acción (permiso requerido: designaciones.write)." } }), { status: 403 });
      guardado.set(`${body.cuil}|${body.periodo_id}`, body.estado);
      return ok({ mensaje: "Estado de la consulta guardado.", tono: "success", estado: body.estado, semaforo: OPCIONES.find((o) => o.valor === body.estado)!.semaforo });
    }
    if (url === "/api/docentes/resumen/mensaje") return ok(MENSAJE);
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

async function abrir() {
  render(<DocentesModule onAuthError={() => {}} />);
  await screen.findByText("Plantel por período");
  fireEvent.click(screen.getByRole("tab", { name: /Resumen docente/ }));
  await screen.findByRole("heading", { name: "Mensaje para consultar la designación — 2026-2" });
}

test("estado actual, radio certificado y semáforo de la opción elegida (viene del backend)", async () => {
  await abrir();
  expect(screen.getByText("Estado de la consulta al docente")).toBeTruthy();
  expect(radio("🟢 Designación confirmada").checked).toBe(true);
  expect(screen.getByText("Designación confirmada", { selector: "strong" })).toBeTruthy();
  fireEvent.click(radio("🔴 Rever Designación"));
  expect(screen.getByText("Rever Designación", { selector: "strong" })).toBeTruthy();
  fireEvent.click(radio("⚪ Sin estado"));
  expect(screen.getByText("sin estado registrado", { selector: "strong" })).toBeTruthy();
});

test("guardar envía cuil, período y el valor de la opción; muestra el resultado o el rechazo del backend", async () => {
  await abrir();
  fireEvent.click(radio("🟡 Consulta Enviada"));
  fireEvent.click(screen.getByRole("button", { name: "💾 Guardar estado de la consulta" }));
  await screen.findByText("Estado de la consulta guardado.");
  const w = posts.find((p) => p.url === "/api/docentes/resumen/estado-consulta")!;
  expect(w.body).toEqual({ cuil: "20-00000001-1", periodo_id: 9, estado: "Consulta Enviada" });
  negar = true;
  fireEvent.click(radio("⚪ Sin estado"));
  fireEvent.click(screen.getByRole("button", { name: "💾 Guardar estado de la consulta" }));
  await screen.findByText(/permiso requerido: designaciones.write/);
  expect(posts.filter((p) => p.url.endsWith("estado-consulta")).at(-1)!.body.estado).toBe("");
});

test("generar mensaje: advertencias, asunto y cuerpo listos para copiar, tal como los devuelve el backend", async () => {
  await abrir();
  fireEvent.click(screen.getByRole("button", { name: "✉️ Generar mensaje para el docente" }));
  await screen.findByText(MENSAJE.advertencias[0]);
  expect(posts.find((p) => p.url === "/api/docentes/resumen/mensaje")!.body).toEqual({ cuil: "20-00000001-1", periodo_id: 9 });
  const asunto = within(screen.getByText("Asunto sugerido").closest("label") ?? document.body).getByRole("textbox") as HTMLInputElement;
  expect(asunto.value).toBe(MENSAJE.asunto);
  const cuerpo = screen.getAllByRole("textbox").find((x) => x.tagName === "TEXTAREA") as HTMLTextAreaElement;
  expect(cuerpo.value).toBe(MENSAJE.cuerpo);
});

test("cambiar de período vuelve a leer el estado de ese período y no arrastra el mensaje", async () => {
  await abrir();
  fireEvent.click(screen.getByRole("button", { name: "✉️ Generar mensaje para el docente" }));
  await screen.findByText(MENSAJE.advertencias[0]);
  fireEvent.change(screen.getByRole("combobox"), { target: { value: "2026-1" } });
  await screen.findByRole("heading", { name: "Mensaje para consultar la designación — 2026-1" });
  await waitFor(() => expect(screen.queryByText(MENSAJE.advertencias[0])).toBeNull());
});

test("sin escritura en Docentes: Guardar y Generar mensaje deshabilitados con la ayuda certificada; el radio y el semáforo siguen", async () => {
  escribe = false;
  await abrir();
  for (const nombre of ["💾 Guardar estado de la consulta", "✉️ Generar mensaje para el docente"]) {
    const b = screen.getByRole("button", { name: nombre }) as HTMLButtonElement;
    expect(b.disabled).toBe(true);
    expect(b.parentElement!.getAttribute("title")).toBe("Tu rol permite visualizar, pero no cargar, editar ni generar cambios.");
    fireEvent.click(b);
  }
  fireEvent.click(radio("🔴 Rever Designación"));
  expect(screen.getByText("Rever Designación", { selector: "strong" })).toBeTruthy();
  expect(posts.some((p) => p.url.endsWith("estado-consulta") || p.url.endsWith("/mensaje"))).toBe(false);
});

// Regresión del bug de la validación visual: guardar, cambiar a otro docente y volver mostraba el estado del docente
// anterior (la sección se montaba con el resumen viejo y la clave del docente nuevo, y no se volvía a montar).
test("guardar → otro docente → volver: el radio muestra lo que relee el backend para cada docente", async () => {
  await abrir();
  const fila = (nombre: string) => screen.getAllByText(nombre).find((x) => x.closest("tr"))!.closest("tr")!;
  for (const [estado, etiqueta] of [["Consulta Enviada", "🟡 Consulta Enviada"], ["Rever Designación", "🔴 Rever Designación"],
    ["Designación confirmada", "🟢 Designación confirmada"], ["", "⚪ Sin estado"]] as const) {
    fireEvent.click(radio(etiqueta));
    fireEvent.click(screen.getByRole("button", { name: "💾 Guardar estado de la consulta" }));
    await screen.findByText("Estado de la consulta guardado.");
    expect(guardado.get("20-00000001-1|9")).toBe(estado);
    fireEvent.click(fila("Dos, Docente"));
    await waitFor(() => expect(posts.at(-1)!.body.cuil).toBe("20-00000002-2"));
    await waitFor(() => expect(radio("⚪ Sin estado").checked).toBe(true));
    await waitFor(() => expect(screen.queryByText("Estado de la consulta guardado.")).toBeNull());
    fireEvent.click(fila("Uno, Docente"));
    await waitFor(() => expect(posts.at(-1)!.body.cuil).toBe("20-00000001-1"));
    await waitFor(() => expect(radio(etiqueta).checked).toBe(true));
    await new Promise((r) => setTimeout(r, 30));
    expect(radio(etiqueta).checked).toBe(true);
  }
});
