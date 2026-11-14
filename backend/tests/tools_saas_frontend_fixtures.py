"""Genera ``frontend/tests/fixtures/saas_ui.json``: los textos y catálogos que el backend envía en ``ui``/``catalogos``
(``saas/textos.py``, sin base de datos ni datos personales), para que el test del frontend use exactamente los mismos."""
import json
import sys
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from saas import textos as T  # noqa: E402

salida = Path(__file__).resolve().parents[2] / "frontend" / "tests" / "fixtures" / "saas_ui.json"
salida.write_text(json.dumps({
    "ui": T.UI,
    "catalogos": {"roles": T.AUTH_ROLES, "planes": T.PLANES_COMERCIALES, "pagos": T.ESTADOS_PAGO,
                  "suscripciones": T.ESTADOS_SUSCRIPCION, "accesos": T.ESTADOS_INSTITUCION,
                  "estados_usuario": T.ESTADOS_USUARIO, "estados_departamento": T.ESTADOS_DEPARTAMENTO,
                  "sin_departamento": T.SIN_DEPARTAMENTO,
                  "cupo": {"min": T.CUPO_MIN, "max": T.CUPO_MAX, "default": T.CUPO_DEFAULT}},
}, ensure_ascii=False, indent=1), encoding="utf-8")
print("ok", salida.name)
