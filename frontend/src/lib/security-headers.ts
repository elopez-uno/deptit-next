// Cabeceras de seguridad que emite la APLICACIÓN (6A-B1). Las de transporte (HSTS) y las de borde (límite de body,
// rate limit global, TLS) son responsabilidad del reverse proxy institucional (6A-B4): Next.js no sabe si la conexión
// del navegador fue HTTPS y no las duplica.
//
// CSP: sin nonces (exigirían render dinámico en todas las páginas), por eso script-src conserva 'unsafe-inline' para
// los scripts de arranque de Next.js; no se habilita 'unsafe-eval' fuera de desarrollo (Vega usa el intérprete,
// `ast: true`). Todo lo demás es solo del mismo origen; la app no se puede embeber (frame-ancestors 'none').
export type Header = { key: string; value: string };

export function contentSecurityPolicy(dev: boolean): string {
  return [
    "default-src 'self'",
    `script-src 'self' 'unsafe-inline'${dev ? " 'unsafe-eval'" : ""}`,
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data: blob:",
    "font-src 'self' data:",
    `connect-src 'self'${dev ? " ws: wss:" : ""}`,
    "object-src 'none'",
    "base-uri 'self'",
    "form-action 'self'",
    "frame-ancestors 'none'",
  ].join("; ");
}

export function securityHeaders(dev: boolean): Header[] {
  return [
    { key: "Content-Security-Policy", value: contentSecurityPolicy(dev) },
    { key: "X-Content-Type-Options", value: "nosniff" },
    { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
    { key: "X-Frame-Options", value: "DENY" },
    {
      key: "Permissions-Policy",
      value: "camera=(), microphone=(), geolocation=(), payment=(), usb=(), interest-cohort=()",
    },
    { key: "Cross-Origin-Opener-Policy", value: "same-origin" },
  ];
}
