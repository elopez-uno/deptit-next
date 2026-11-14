"""Punto de entrada del backend (6A-B1): valida la configuracion ANTES de levantar uvicorn y fija lo que no debe variar.

* Un solo worker: las sesiones viven en la memoria del proceso (B12G); mas workers romperian la autenticacion.
* Host/puerto desde ``DEPTIT_BACKEND_HOST`` / ``DEPTIT_BACKEND_PORT`` (loopback salvo excepcion explicita).
* Sin ``--proxy-headers``: FastAPI no confia en ``X-Forwarded-*``; el origen del cliente llega solo por la cabecera
  propia de Next.js desde un frontend confiable (``auth/client_ip.py``).
* Sin cabecera ``Server``.  El servicio del sistema (systemd / WinSW) y la rotacion de logs son 6A-B2.

Uso: ``python serve.py`` desde ``backend/`` (con el entorno del proceso o ``backend/.env`` en desarrollo).
"""

from __future__ import annotations

import sys

import settings


def main() -> int:
    import main as _composicion  # noqa: F401  (registra los validadores de la capa de composicion, p. ej. el gate de backup)
    try:
        cfg = settings.load()
    except settings.ConfigError as exc:
        print(f"CONFIGURACION INVALIDA: el backend no arranca: {exc}", file=sys.stderr)
        return 2
    import uvicorn
    uvicorn.run("main:app", host=cfg.backend_host, port=cfg.backend_port, workers=1, proxy_headers=False,
                server_header=False, access_log=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
