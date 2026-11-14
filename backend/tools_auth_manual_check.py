"""Prueba MANUAL con credenciales reales (las ingresa una persona; nada se imprime ni se guarda).

Recorre el flujo completo via Next.js (http://localhost:3001), como el navegador:
login -> /auth/me -> opciones/cambio de contexto (si el rol lo permite, y se restaura) -> logout -> /auth/me con la
cookie vieja (debe ser 401).  Muestra solo resultados: status, rol, institucion, departamento, vista y modulos.

Antes de pedir la contraseña verifica la cadena Next.js -> FastAPI con un login VACIO (no consume intentos del
limite: el backend lo rechaza sin consultar ni registrar el throttle).  Si cualquier respuesta no es JSON (p. ej. la
pagina de error HTML de ``next dev``), se informa status y un resumen seguro, sin volcar el cuerpo.
"""

import getpass
import json
import sys
import urllib.error
import urllib.request

NEXT = "http://localhost:3001"
HEADERS = {"Content-Type": "application/json", "Origin": NEXT, "Sec-Fetch-Site": "same-origin"}
FORBIDDEN = ("salt", "password_hash", "postgresql://", "DATABASE_URL")


class UnexpectedResponse(Exception):
    """Respuesta que no es el JSON esperado; ``str()`` es seguro de mostrar (sin cuerpo ni secretos)."""


def http(method, path, body=None, cookie=None):
    req = urllib.request.Request(NEXT + path, method=method,
                                 data=None if body is None else json.dumps(body).encode())
    for k, v in HEADERS.items():
        req.add_header(k, v)
    if cookie:
        req.add_header("Cookie", cookie)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode("utf-8", "replace"), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode("utf-8", "replace"), e.headers


def safe_summary(status, body, headers):
    """Descripcion de una respuesta no JSON sin incluir su contenido."""
    ctype = (headers.get("Content-Type") if headers is not None else None) or "desconocido"
    kind = "página de error HTML de Next.js" if "__NEXT_DATA__" in body else "contenido no JSON"
    hint = " Revisá la consola de `next dev` (puerto 3001) y reinicialo si hace falta." if status >= 500 else ""
    return f"status={status}: {kind} (content-type={ctype}, {len(body)} bytes; cuerpo omitido).{hint}"


def as_json(status, body, headers):
    try:
        data = json.loads(body)
    except ValueError:
        raise UnexpectedResponse(safe_summary(status, body, headers)) from None
    if not isinstance(data, dict):
        raise UnexpectedResponse(f"status={status}: JSON inesperado (no es un objeto).")
    return data


def error_message(status, body, headers):
    data = as_json(status, body, headers)
    message = (data.get("error") or {}).get("message") if isinstance(data.get("error"), dict) else None
    return message or f"status={status} sin mensaje de error"


def describe(data):
    u, c = data["usuario"], data["contexto"]
    return (f"rol={u['rol']} rol_original={u['rol_original']} superadmin={u['es_superadmin']} "
            f"acceso={data['acceso']} | institucion={c['institucion'] and c['institucion']['nombre']} | "
            f"departamento={c['departamento'] and c['departamento']['nombre']} | vista={c['vista']} | "
            f"problema={c['problema']} | modulos={len(data['modulos'])}")


def preflight():
    """Login vacio: debe volver 401 JSON del backend atravesando el proxy.  ``UnexpectedResponse`` si no."""
    try:
        status, body, headers = http("POST", "/api/auth/login", {"email": "", "password": ""})
    except (urllib.error.URLError, OSError) as exc:
        raise UnexpectedResponse(f"No se pudo conectar con {NEXT} ({type(exc).__name__}).") from None
    data = as_json(status, body, headers)
    if status != 401 or (data.get("error") or {}).get("code") != "LOGIN_REJECTED":
        raise UnexpectedResponse(f"status={status}: el proxy/backend no responde como se espera "
                                 f"(code={(data.get('error') or {}).get('code')}).")


def run() -> int:
    ok = True

    def check(name, cond, detail=""):
        nonlocal ok
        ok = ok and bool(cond)
        print(f"{'PASS' if cond else 'FAIL'}  {name}  {detail}")

    preflight()
    print("PASS  cadena Next.js -> FastAPI disponible (login vacío -> 401 JSON)")

    email = input("Mail del usuario de prueba: ").strip()
    password = getpass.getpass("Contraseña (no se muestra): ")
    status, body, headers = http("POST", "/api/auth/login", {"email": email, "password": password})
    del password
    set_cookie = headers.get("Set-Cookie") or ""
    check("login con credenciales válidas", status == 200, f"status={status}")
    if status != 200:
        print("Mensaje:", error_message(status, body, headers))
        return 1
    check("cookie HttpOnly + SameSite=Strict", "HttpOnly" in set_cookie and "SameSite=strict" in set_cookie)
    cookie = set_cookie.split(";")[0]
    check("respuesta sin secretos", not any(w in body for w in FORBIDDEN) and cookie.split("=", 1)[1] not in body)
    data = as_json(status, body, headers)
    print("      ", describe(data))

    status, body, _ = http("GET", "/api/auth/me", cookie=cookie)
    check("/auth/me con sesión", status == 200 and not any(w in body for w in FORBIDDEN), f"status={status}")

    if data["contexto"]["seleccionable"]:
        status, body, headers = http("GET", "/api/auth/context/options", cookie=cookie)
        opts = as_json(status, body, headers)
        check("opciones de contexto", status == 200,
              f"instituciones={len(opts['instituciones'])} departamentos={len(opts['departamentos'])} "
              f"consolidado={opts['permite_consolidado']}")
        original = data["contexto"]
        if opts["permite_consolidado"] and opts["departamentos"]:
            status, body, headers = http("PUT", "/api/auth/context",
                                         {"departamento_id": opts["departamentos"][0]["id"]}, cookie)
            check("coordinación: elegir un departamento", status == 200, describe(as_json(status, body, headers)))
            status, body, headers = http("PUT", "/api/auth/context", {"consolidado": True}, cookie)
            check("coordinación: volver al consolidado", status == 200, describe(as_json(status, body, headers)))
        elif opts["puede_elegir_institucion"] and len(opts["instituciones"]) > 1:
            other = next(i for i in opts["instituciones"] if i["id"] != original["institucion"]["id"])
            status, body, headers = http("PUT", "/api/auth/context", {"institucion_id": other["id"]}, cookie)
            check("superadmin: cambiar de institución", status == 200, describe(as_json(status, body, headers)))
            status, body, headers = http("PUT", "/api/auth/context",
                                         {"institucion_id": original["institucion"]["id"],
                                          "departamento_id": original["departamento"]["id"]}, cookie)
            check("superadmin: restaurar contexto", status == 200, describe(as_json(status, body, headers)))
    else:
        status, _, _ = http("PUT", "/api/auth/context", {"departamento_id": 999999}, cookie)
        check("rol con ámbito fijo no puede cambiar contexto", status == 403, f"status={status}")

    status, _, headers = http("POST", "/api/auth/logout", cookie=cookie)
    check("logout", status == 204 and "Max-Age=0" in (headers.get("Set-Cookie") or ""), f"status={status}")
    status, _, _ = http("GET", "/api/auth/me", cookie=cookie)
    check("la cookie anterior ya no sirve después del logout", status == 401, f"status={status}")
    del cookie
    print("\nRESULTADO:", "OK" if ok else "CON FALLAS")
    return 0 if ok else 1


def main() -> int:
    try:
        return run()
    except UnexpectedResponse as exc:
        print("FAIL  respuesta inesperada:", exc)
        print("\nRESULTADO: CON FALLAS")
        return 1


if __name__ == "__main__":
    sys.exit(main())
