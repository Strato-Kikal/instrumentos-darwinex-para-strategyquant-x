#!/usr/bin/env python3
"""Una ronda del muestreo del spread medio automático (lo ejecuta GitHub Actions cada 15 min).

    python3 app/muestreo_spread.py --datos CARPETA

CARPETA es la copia de la rama «datos-spread» (dias/, ultimas.json y medias.json). Lee los datos
de Darwinex y el bid/ask de todos sus símbolos, añade una muestra a los que cotizan y vuelve a
calcular medias.json. Solo biblioteca estándar. Detalles: app/sqx/muestreo.py.
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqx import muestreo  # noqa: E402
from sqx.fuentes import Fuentes, FuenteError  # noqa: E402


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--datos", required=True, help="carpeta de la rama datos-spread")
    a = p.parse_args(argv)
    try:
        cuenta = muestreo.ejecutar(a.datos, Fuentes())
    except FuenteError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1
    print("Muestras añadidas: {anadidas} · mercado cerrado: {cerrados} · sin cambio: {sin_cambio} · "
          "sin datos: {sin_datos}".format(**cuenta))
    return 0


if __name__ == "__main__":
    sys.exit(main())
