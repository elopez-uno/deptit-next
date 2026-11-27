// @vitest-environment node
// 6A-B1: el redirect optimista del proxy cubre las rutas de la aplicación, pero no los recursos estáticos.
// Los logos DEPTIT de /public/branding se sirven en el login (sin cookie), igual que el favicon y los assets de Next.
import { describe, expect, it } from "vitest";
import { config } from "@/proxy";

const matcher = new RegExp(`^${config.matcher[0]}$`);

describe("matcher del proxy", () => {
  it("protege las rutas de la aplicación", () => {
    for (const ruta of ["/", "/periodos", "/docentes/123", "/login-interno"]) {
      expect(matcher.test(ruta), ruta).toBe(true);
    }
  });

  it("deja pasar login, API, assets de Next y archivos estáticos", () => {
    for (const ruta of [
      "/login",
      "/api/auth/me",
      "/_next/static/chunks/main.js",
      "/_next/image",
      "/favicon.ico",
      "/branding/deptit-logo-completo.png",
      "/branding/deptit-icono.png",
    ]) {
      expect(matcher.test(ruta), ruta).toBe(false);
    }
  });
});
