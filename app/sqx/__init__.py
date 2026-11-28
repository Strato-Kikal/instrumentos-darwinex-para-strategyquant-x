"""Instrumentos SQX: aplicación independiente basada en la skill
«Instrumentos Darwinex para StrategyQuant X» (Kike Argandona, licencia MIT).

Reutiliza scripts/tabla.py de la skill (perfil, reglas de validación, columnas y formato del PDF)
sin modificarlo.
"""
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]  # carpeta de la skill (contiene scripts/tabla.py)
APP = RAIZ / "app"
if str(RAIZ / "scripts") not in sys.path:
    sys.path.insert(0, str(RAIZ / "scripts"))

import tabla  # noqa: E402  (scripts/tabla.py de la skill)

NOMBRE = "Instrumentos SQX"
VERSION = "2.4.0"
