"""Origen del cliente para el limite de login por IP (6A-B1).

Cadena de confianza: navegador -> [reverse proxy institucional, 6A-B4] -> Next.js (BFF) -> FastAPI (loopback).
* FastAPI acepta la cabecera ``x-deptit-client-ip`` SOLO si la conexion TCP viene de un frontend confiable
  (``DEPTIT_TRUSTED_FRONTEND_IPS``, por defecto loopback).  Next.js la construye desde cero: nunca reenvia la que
  manda el navegador (``lib/backend-proxy.ts::clientIp``).
* Next.js solo la deriva de ``X-Forwarded-For`` cuando ``DEPTIT_TRUSTED_PROXY_HOPS`` >= 1 (hay un reverse proxy propio
  delante que agrega o sobrescribe ese encabezado).  Sin proxy (desarrollo local) no la envia: Next 16 conserva el
  ``X-Forwarded-For`` del cliente (``??=``) y seria falsificable.
* Si la conexion NO viene de un frontend confiable (acceso directo, que el diseño impide), el origen es el peer TCP.
* Sin origen confiable -> ``None``: rige solo el limite por cuenta (nunca un balde compartido por todos).
"""

from __future__ import annotations

import ipaddress
from typing import Iterable, Optional

from fastapi import Request

HEADER = "x-deptit-client-ip"


def _ip(value: Optional[str]) -> Optional[str]:
    try:
        return str(ipaddress.ip_address(str(value or "").strip()))
    except ValueError:
        return None


def resolve(peer: Optional[str], header: Optional[str], trusted: Iterable[str]) -> Optional[str]:
    peer_ip = _ip(peer)
    if peer_ip is None:
        return None
    if peer_ip in set(trusted):
        return _ip(header)
    return peer_ip


def client_ip(request: Request) -> Optional[str]:
    import settings as app_settings
    peer = request.client.host if request.client else None
    return resolve(peer, request.headers.get(HEADER), app_settings.get().trusted_frontend_ips)
