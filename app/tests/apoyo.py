"""Utilidades comunes de las pruebas: fuentes simuladas con respuestas reales guardadas."""
import json
import sys
from pathlib import Path

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from sqx import tabla  # noqa: E402
from sqx import fuentes as F  # noqa: E402

DATOS = Path(__file__).resolve().parent / "datos"
PERFIL = tabla.cargar_perfil(str(tabla.PERFIL_DEFECTO))


def respuesta(nombre):
    return (DATOS / nombre).read_bytes()


def darwinex_modificado(cambio):
    """Bytes del JSON de Darwinex tras aplicar cambio(dict)."""
    d = json.loads(respuesta("darwinex.json"))
    cambio(d)
    return json.dumps(d).encode()


def fuentes_simuladas(fallos=(), sustituir=None, hora=None):
    """Fuentes con las respuestas guardadas. fallos: prefijos de URL que fallan como sin conexión.
    sustituir: {prefijo de URL: bytes}."""
    sustituir = sustituir or {}

    def descargar(url, fuente, timeout=None):
        for prefijo in fallos:
            if url.startswith(prefijo):
                raise F.FuenteError(fuente, "no se pudo conectar (simulado)")
        for prefijo, datos in sustituir.items():
            if url.startswith(prefijo):
                return datos, hora or F.ahora_utc()
        if url == F.URL_DARWINEX:
            datos = respuesta("darwinex.json")
        elif url.startswith(F.URL_PRECIOS.split("{")[0]):
            datos = respuesta("precios.json")
        elif url == F.URL_BCE:
            datos = respuesta("bce.xml")
        elif url == F.URL_COSTES:
            datos = respuesta("costes.html")
        else:
            raise AssertionError(f"URL inesperada en la prueba: {url}")
        return datos, hora or F.ahora_utc()
    return F.Fuentes(descargar)
