// 6A-B4 (R-B3-10, actualizado): la instalación pertenece a la Universidad Nacional del Oeste, por lo que el login y la
// metadata llevan el branding institucional (nombre y logo). Dentro del sistema el encabezado es la institución ACTIVA
// que entrega el backend y se actualiza al cambiar de contexto.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import type { Session } from "@/lib/auth";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));
vi.mock("@/components/inicio-module", () => ({ InicioModule: () => <p>Módulo Inicio</p> }));
let onChangedRef: ((s: Session) => void) | null = null;
vi.mock("@/components/context-switcher", () => ({
  ContextSwitcher: ({ onChanged }: { onChanged: (s: Session) => void }) => {
    onChangedRef = onChanged;
    return <span>selector</span>;
  },
}));

import { AppShell } from "@/components/app-shell";
import { metadata } from "@/app/layout";
import LoginPage from "@/app/login/page";

const UNO = "Universidad Nacional del Oeste";
const PRUEBA = "Universidad de Prueba";

function sesion(encabezado: string, inst: { id: number; nombre: string } | null): Session {
  return {
    usuario: { id: 1, nombre: "Super", email: "s@test.local", rol: "superadmin", rol_original: null,
      modo_solo_lectura_comercial: false, es_superadmin: true },
    acceso: "normal",
    // pertenencia a UNO aunque opere en otra institución: el encabezado no la usa
    pertenencia: { institucion: { id: 1, nombre: UNO }, departamento: null },
    contexto: { institucion_encabezado: encabezado, institucion: inst, departamento: inst ? { id: 1, nombre: "Dep" } : null,
      vista: inst ? "departamento" : "sin_ambito", problema: null, seleccionable: true },
    modulos: [{ clave: "inicio", nombre: "🏠 Inicio", puede_escribir: false, puede_borrar: false }],
    sesion: { inactividad_max_segundos: 3600, expira_por_inactividad_en: 3600, expira_absoluta_en: 28800 },
  };
}

let actual: Session;
beforeEach(() => {
  onChangedRef = null;
  actual = sesion(UNO, { id: 1, nombre: UNO });
  vi.stubGlobal("fetch", async (url: string) => {
    if (url === "/api/auth/me") return new Response(JSON.stringify(actual), { status: 200 });
    if (url === "/api/contexto/periodo") return new Response(JSON.stringify({ aviso: null }), { status: 200 });
    return new Response(JSON.stringify({ error: { code: "NOT_FOUND", message: "no" } }), { status: 404 });
  });
});
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

test("login y metadata con branding institucional UNO", () => {
  expect(metadata.title).toBe("DEPTIT NEXT — Universidad Nacional del Oeste");
  expect(metadata.description).toContain(UNO);
  render(<LoginPage />);
  // El login muestra el nombre institucional (el logo se expone por alt) y el nombre del sistema.
  expect(screen.getAllByText(new RegExp(UNO)).length).toBeGreaterThan(0);
  expect(screen.getAllByText(/DEPTIT NEXT/).length).toBeGreaterThan(0);
  expect(screen.getAllByAltText(UNO).length).toBeGreaterThan(0);
});

test("encabezado = institución activa; UNO → Prueba → UNO sin arrastre; sin institución activa, ningún nombre", async () => {
  render(<AppShell />);
  await screen.findByText("Módulo Inicio");
  const encabezado = () => screen.getByRole("banner").querySelector("p")?.textContent ?? "";
  // como el backend real: tras PUT /auth/context, /auth/me devuelve la sesión del contexto nuevo
  const cambiar = (s: Session) => {
    actual = s;
    onChangedRef!(s);
  };
  expect(encabezado()).toBe(UNO);
  cambiar(sesion(PRUEBA, { id: 846, nombre: PRUEBA }));
  await waitFor(() => expect(encabezado()).toBe(PRUEBA));
  expect(screen.getByRole("banner").textContent).not.toContain(UNO);
  cambiar(sesion(UNO, { id: 1, nombre: UNO }));
  await waitFor(() => expect(encabezado()).toBe(UNO));
  cambiar(sesion("", null));
  await waitFor(() => expect(encabezado()).toBe(""));
  expect(screen.getByRole("banner").textContent).not.toMatch(/Universidad/);
});
