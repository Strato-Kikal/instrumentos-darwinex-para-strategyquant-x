"""Consulta de las fuentes en vivo (solo biblioteca estándar).

Fuentes (comprobadas el 2026-11-26):
  - Darwinex: JSON que alimenta las tablas de https://www.darwinex.com/forex-cfds/<clase>.
    Rechaza peticiones con una cabecera «Origin» ajena («Invalid CORS request»), así que un
    navegador no puede leerlo desde otra web: lo consulta este servidor.
  - Spread: feed de precios que usa la propia web de Darwinex (widgets.fxbluelabs.com).
    Permite CORS, pero se consulta aquí para registrar la hora junto al resto.
  - Spread medio: medias.json del muestreo automático (rama «datos-spread» del repositorio),
    que publica cada 15 minutos la tarea de GitHub Actions (app/sqx/muestreo.py).
  - BCE: tipos de referencia diarios (XML). No envía cabeceras CORS.
  - help.darwinex.com/execution-costs: se comprueba en vivo que la comisión se publica por orden.

Cada consulta devuelve el contenido y la hora UTC a la que se obtuvo. Los fallos se elevan como
FuenteError con un mensaje claro para el usuario.
"""
import datetime as dt
import json
import re
import socket
import threading
import time
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from decimal import Decimal

from . import tabla

URL_DARWINEX = "https://www.darwinex.com/graphics/spreads?dx_platform=DX"
URL_PRECIOS = "https://widgets.fxbluelabs.com/webwidgets/getPriceData.aspx?id=Darwinex&f=bid,ask&s={}"
URL_BCE = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"
URL_BCE_WEB = ("https://www.ecb.europa.eu/stats/policy_and_exchange_rates/"
               "euro_reference_exchange_rates/html/index.en.html")
URL_COSTES = "https://help.darwinex.com/execution-costs"

AGENTE = "Mozilla/5.0 (compatible; InstrumentosSQX/1.0)"
TIEMPO_MAX = 15  # segundos por petición


class FuenteError(Exception):
    """Una fuente no respondió o respondió algo inesperado."""

    def __init__(self, fuente, motivo):
        super().__init__(f"{fuente}: {motivo}")
        self.fuente, self.motivo = fuente, motivo


def ahora_utc():
    return dt.datetime.now(dt.timezone.utc)


def descargar(url, fuente, timeout=TIEMPO_MAX):
    """(bytes, hora UTC). Sin cabecera Origin: Darwinex rechaza las de otros dominios."""
    peticion = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "*/*"})
    try:
        with urllib.request.urlopen(peticion, timeout=timeout) as r:
            datos = r.read()
    except urllib.error.HTTPError as e:
        raise FuenteError(fuente, f"respondió con el código HTTP {e.code}")
    except urllib.error.URLError as e:
        motivo = e.reason
        if isinstance(motivo, socket.timeout):
            raise FuenteError(fuente, f"no respondió en {timeout} s")
        raise FuenteError(fuente, f"no se pudo conectar ({motivo})")
    except socket.timeout:
        raise FuenteError(fuente, f"no respondió en {timeout} s")
    except OSError as e:
        raise FuenteError(fuente, f"error de conexión ({e})")
    return datos, ahora_utc()


# ---------------------------------------------------------------- interpretación

def leer_darwinex(datos):
    """Comprueba la estructura del JSON de Darwinex. Números como Decimal (sin perder decimales)."""
    try:
        d = json.loads(datos.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
    except (UnicodeDecodeError, ValueError):
        raise FuenteError("Darwinex", "la respuesta no es un JSON válido")
    if not isinstance(d, dict) or not any(isinstance(d.get(k), list) for k in
                                          ("forex", "indices", "commodities", "crypto")):
        raise FuenteError("Darwinex", "la respuesta no tiene las tablas esperadas (forex, índices…)")
    return d


def fecha_actualizacion(d):
    """Hora UTC de «updateDate» del JSON de Darwinex (la web la muestra como UTC), o None."""
    u = d.get("updateDate")
    try:
        return dt.datetime(int(u["year"]), int(u["monthValue"]), int(u["dayOfMonth"]),
                           int(u["hour"]), int(u["minute"]), tzinfo=dt.timezone.utc)
    except (TypeError, KeyError, ValueError):
        return None


def leer_precios(datos):
    """{símbolo: (bid, ask)} o {símbolo: None} si el feed no tiene datos de ese símbolo."""
    try:
        d = json.loads(datos.decode("utf-8"), parse_float=Decimal, parse_int=Decimal)
        simbolos = d["symbols"]
    except (UnicodeDecodeError, ValueError, KeyError, TypeError):
        raise FuenteError("Feed de spread", "la respuesta no es el JSON esperado")
    res = {}
    for s in simbolos if isinstance(simbolos, list) else []:
        if not isinstance(s, dict) or "symbol" not in s:
            continue
        bid, ask = s.get("bid"), s.get("ask")
        ok = isinstance(bid, Decimal) and isinstance(ask, Decimal) and bid > 0 and ask > 0
        res[str(s["symbol"])] = (bid, ask) if ok and not s.get("noData") else None
    return res


def leer_medias(datos):
    """medias.json del muestreo automático, comprobando su estructura."""
    try:
        d = json.loads(datos.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        raise FuenteError("Spread medio automático", "la respuesta no es un JSON válido")
    if (not isinstance(d, dict) or d.get("fuente") != tabla.FUENTE_MUESTREO
            or not isinstance(d.get("simbolos"), dict)):
        raise FuenteError("Spread medio automático", "la respuesta no tiene el formato esperado")
    return d


def leer_bce(datos):
    """(fecha AAAA-MM-DD, {divisa: unidades por 1 EUR}) del XML diario del BCE."""
    try:
        raiz = ET.fromstring(datos)
    except ET.ParseError:
        raise FuenteError("BCE", "la respuesta no es el XML esperado")
    fecha, tipos = None, {}
    for e in raiz.iter():
        if e.tag.endswith("Cube"):
            if "time" in e.attrib:
                fecha = e.attrib["time"]
            if "currency" in e.attrib and "rate" in e.attrib:
                try:
                    tipos[e.attrib["currency"]] = Decimal(e.attrib["rate"])
                except ArithmeticError:
                    pass
    if not fecha or not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha) or "USD" not in tipos:
        raise FuenteError("BCE", "no encuentro la fecha o el tipo EUR/USD en el XML")
    tipos["EUR"] = Decimal(1)
    return fecha, tipos


RE_POR_ORDEN = re.compile(r"displayed\s+per\s+order.{0,80}?2\s+orders", re.I | re.S)


def leer_costes(datos):
    """Fragmento que confirma «commissions are displayed per order … 2 orders», o None."""
    texto = re.sub(r"<[^>]+>", " ", datos.decode("utf-8", "replace"))
    m = RE_POR_ORDEN.search(re.sub(r"\s+", " ", texto))
    return m.group(0) if m else None


# ---------------------------------------------------------------- acceso con caché corta

class Fuentes:
    """Acceso a las fuentes en vivo. Darwinex se guarda 60 s (el JSON pesa ~0,5 MB y la web lo
    actualiza cada pocos minutos); BCE y la página de costes, 1 h. El spread nunca se guarda."""

    CACHE_DARWINEX, CACHE_MEDIAS, CACHE_LENTA = 60, 300, 3600

    def __init__(self, descargar_fn=descargar):
        self._descargar = descargar_fn
        self._cache = {}
        self._cerrojo = threading.Lock()

    def _con_cache(self, clave, segundos, fn):
        with self._cerrojo:
            v = self._cache.get(clave)
            if v and time.monotonic() - v[0] < segundos:
                return v[1]
        valor = fn()
        with self._cerrojo:
            self._cache[clave] = (time.monotonic(), valor)
        return valor

    def darwinex(self):
        """(datos, hora UTC de la descarga)."""
        def f():
            datos, hora = self._descargar(URL_DARWINEX, "Darwinex")
            return leer_darwinex(datos), hora
        return self._con_cache("darwinex", self.CACHE_DARWINEX, f)

    def precios(self, simbolo):
        """((bid, ask) o None, hora UTC, url)."""
        url = URL_PRECIOS.format(simbolo)
        datos, hora = self._descargar(url, "Feed de spread")
        return leer_precios(datos).get(simbolo), hora, url

    def precios_varios(self, simbolos):
        """{símbolo: (bid, ask) o None} de varios símbolos en una sola petición."""
        datos, _ = self._descargar(URL_PRECIOS.format(",".join(simbolos)), "Feed de spread")
        return leer_precios(datos)

    def medias(self):
        """(medias.json del spread medio automático, hora UTC). Se guarda 5 minutos."""
        def f():
            datos, hora = self._descargar(tabla.URL_DATOS_SPREAD, "Spread medio automático")
            return leer_medias(datos), hora
        return self._con_cache("medias", self.CACHE_MEDIAS, f)

    def bce(self):
        """(fecha del BCE, tipos, hora UTC)."""
        def f():
            datos, hora = self._descargar(URL_BCE, "BCE")
            fecha, tipos = leer_bce(datos)
            return fecha, tipos, hora
        return self._con_cache("bce", self.CACHE_LENTA, f)

    def costes(self):
        """(fragmento o None, hora UTC)."""
        def f():
            datos, hora = self._descargar(URL_COSTES, "Ayuda de Darwinex (costes)")
            return leer_costes(datos), hora
        return self._con_cache("costes", self.CACHE_LENTA, f)
