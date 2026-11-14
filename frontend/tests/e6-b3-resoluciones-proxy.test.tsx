// @vitest-environment node
// 6A-B3 (aceptación humana): el proxy REAL de Resoluciones y respaldos (route.ts, allowlist) deja pasar las dos rutas
// nuevas del vínculo acto <-> designación y sigue rechazando todo lo demás. (Los tests del módulo simulan fetch por
// encima del proxy: este archivo cubre el eslabón que faltaba y que detectó el smoke real de preproducción.)
import { NextRequest } from "next/server";
import { afterEach, beforeEach, expect, test, vi } from "vitest";
import { POST } from "@/app/api/resoluciones-respaldos/[[...path]]/route";

const ORIGEN = "http://deptit.local";
let fetchMock: ReturnType<typeof vi.fn>;

beforeEach(() => {
  fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200, headers: { "content-type": "application/json" } }));
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const llamar = (path: string[], headers: Record<string, string> = { origin: ORIGEN, "sec-fetch-site": "same-origin" }) =>
  POST(new NextRequest(`${ORIGEN}/api/resoluciones-respaldos/${path.join("/")}`, {
    method: "POST", headers: { host: "deptit.local", "content-type": "application/json", ...headers }, body: "{}" }),
  { params: Promise.resolve({ path }) } as never);

test.each([["designaciones"], ["documento/designaciones"], ["documento/docentes"], ["documento/proyectos"]])("%s se reenvía al backend", async (ruta) => {
  const r = await llamar(ruta.split("/"));
  expect(r.status).toBe(200);
  expect(String(fetchMock.mock.calls[0][0])).toMatch(new RegExp(`/resoluciones-respaldos/${ruta}$`));
});

test("rutas no migradas siguen en 404 y el CSRF same-origin se mantiene", async () => {
  expect((await llamar(["documento", "designaciones", "x"])).status).toBe(404);
  expect((await llamar(["dependencias", "eliminar"])).status).toBe(404);
  expect((await llamar(["documento", "designaciones"], { origin: "https://evil.example" })).status).toBe(403);
  expect(fetchMock).not.toHaveBeenCalled();
});
