import type { Metadata } from "next";
import "./globals.css";

// 6A-B1: sin fuentes de Google. El build productivo no descarga fuentes de Internet (reproducible, sin dependencia
// externa frágil) y el navegador no consulta servidores de terceros: se usa la pila de fuentes del sistema
// (globals.css, --font-sans / --font-mono).

export const metadata: Metadata = {
  // 6A-B4 (R-B3-10, actualizado): la instalación es de la Universidad Nacional del Oeste, por lo que el branding
  // institucional (nombre y logo) también aparece antes del login. Dentro del sistema el encabezado sigue siendo la
  // institución ACTIVA que entrega el backend.
  applicationName: "DEPTIT NEXT",
  title: "DEPTIT NEXT — Universidad Nacional del Oeste",
  description: "Sistema de Gestión Académica Departamental — Universidad Nacional del Oeste",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="es-AR" className="h-full antialiased">
      <body className="min-h-full flex flex-col">{children}</body>
    </html>
  );
}
