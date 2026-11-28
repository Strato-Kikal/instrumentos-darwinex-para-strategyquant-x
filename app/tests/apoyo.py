"""Utilidades comunes de las pruebas: fuentes simuladas con respuestas reales guardadas."""
import contextlib
import datetime as dt
import json
import sys
from pathlib import Path
from unittest import mock

APP = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(APP))

from sqx import tabla  # noqa: E402
from sqx import fuentes as F  # noqa: E402

DATOS = Path(__file__).resolve().parent / "datos"
PERFIL = tabla.cargar_perfil(str(tabla.PERFIL_DEFECTO))

# medias.json del muestreo automático para las pruebas. Valores SINTÉTICOS (no medidos), con la
# forma y el orden de magnitud reales; las fechas se calculan respecto a hoy. NI225 falta a
# propósito (símbolo aún sin muestras).
VALORES_MEDIAS = {"EURUSD": ("0.4234", "0.0001"), "USDJPY": ("0.98", "0.01"),
                  "USDCAD": ("0.94", "0.0001"), "GBPJPY": ("2.6", "0.01"), "GDAXI": ("1.2", "1"),
                  "NDX": ("1.1", "1"), "XTIUSD": ("3.6", "0.01"), "XAUUSD": ("48.23", "0.01"),
                  "BTCUSD": ("14.5", "1")}


def medias(dias=30, muestras=1900, quitar=(), valores=None):
    hoy = F.ahora_utc().date()
    desde = (hoy - dt.timedelta(days=dias - 1)).isoformat()
    simbolos = {s: {"spread": v, "pip": pip, "muestras": muestras, "desde": desde,
                    "hasta": hoy.isoformat(), "min": v, "max": v}
                for s, (v, pip) in dict(VALORES_MEDIAS, **(valores or {})).items() if s not in quitar}
    return {"fuente": tabla.FUENTE_MUESTREO, "broker": "Darwinex", "periodo_dias": 30,
            "intervalo_min": 15, "inicio": desde, "generado_utc": f"{hoy} 10:00",
            "simbolos": simbolos}


@contextlib.contextmanager
def en_hora(momento):
    """Fija la hora actual (UTC) de la app durante la prueba: el spread depende de si el mercado
    está abierto."""
    with mock.patch("sqx.fuentes.ahora_utc", return_value=momento), \
            mock.patch("sqx.instrumento.ahora_utc", return_value=momento):
        yield


# Momentos de referencia: jueves con el mercado abierto y sábado con todo cerrado
JUEVES = dt.datetime(2026, 11, 26, 18, tzinfo=dt.timezone.utc)
SABADO = dt.datetime(2026, 11, 28, 9, 30, tzinfo=dt.timezone.utc)


def medias_bytes(**kw):
    return json.dumps(medias(**kw)).encode()


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
        elif url == tabla.URL_DATOS_SPREAD:
            datos = medias_bytes()
        elif url == F.URL_COSTES:
            datos = respuesta("costes.html")
        else:
            raise AssertionError(f"URL inesperada en la prueba: {url}")
        return datos, hora or F.ahora_utc()
    return F.Fuentes(descargar)
