import type { Metadata } from "next";
import "./globals.css";

// 6A-B1: sin fuentes de Google. El build productivo no descarga fuentes de Internet (reproducible, sin dependencia
// externa frágil) y el navegador no consulta servidores de terceros: se usa la pila de fuentes del sistema
// (globals.css, --font-sans / --font-mono).

export const metadata: Metadata = {
  // 6A-B4 (R-B3-10): branding neutro de la instalación; ninguna universidad antes del login. La institución activa
  // se muestra dentro del sistema a partir del contexto que entrega el backend.
  applicationName: "DEPTIT",
  title: "DEPTIT — Gestión académica",
  description: "Sistema de gestión académica departamental",
  // Favicon / app icon: isotipo DEPTIT de /public/branding, servido tal cual.
  icons: {
    icon: [{ url: "/branding/deptit-icono.png", type: "image/png" }],
    apple: [{ url: "/branding/deptit-icono.png", type: "image/png" }],
  },
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es-AR" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
