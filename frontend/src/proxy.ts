import { NextResponse } from "next/server";
import type { NextRequest } from "next/server";

// Redirección optimista: sin cookie de sesión no tiene sentido mostrar el shell.
// La autorización real la decide FastAPI en cada request (/auth/me).
export function proxy(request: NextRequest) {
  if (!request.cookies.has("deptit_session")) {
    return NextResponse.redirect(new URL("/login", request.url));
  }
  return NextResponse.next();
}

export const config = {
  // Los recursos estáticos (public/, favicon, assets de Next) no pasan por el redirect optimista: no son rutas de la
  // aplicación y el navegador los pide sin cookie de sesión (p. ej. el logo institucional en el login).
  matcher: [
    "/((?!api(?:/|$)|login(?:/|$)|_next/static|_next/image|favicon\\.ico$|.*\\.(?:svg|png|jpg|jpeg|gif|webp|avif|ico|txt|xml|woff2?)$).*)",
  ],
};
