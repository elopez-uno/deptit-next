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
  matcher: ["/((?!api|login|_next/static|_next/image|favicon.ico).*)"],
};
