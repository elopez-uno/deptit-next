import type { Metadata } from "next";
import "./globals.css";

// 6A-B1: sin fuentes de Google. El build productivo no descarga fuentes de Internet (reproducible, sin dependencia
// externa frágil) y el navegador no consulta servidores de terceros: se usa la pila de fuentes del sistema
// (globals.css, --font-sans / --font-mono).

export const metadata: Metadata = {
  // 6A-B4 (R-B3-10): branding neutro de la instalación; ninguna universidad antes del login.
  title: "DEPTIT — Gestión académica",
  description: "Sistema de gestión académica departamental",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
