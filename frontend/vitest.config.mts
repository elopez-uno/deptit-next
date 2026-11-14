import { fileURLToPath } from "node:url";
import { defineConfig } from "vitest/config";

// Tests de componentes (jsdom). No interviene en el build de Next.js.
export default defineConfig({
  esbuild: { jsx: "automatic" },
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  test: { environment: "jsdom", include: ["tests/**/*.test.tsx"], testTimeout: 30000 },
});
