#!/usr/bin/env python3
"""Instrumentos SQX: servidor local de la aplicación (solo biblioteca estándar, Python 3.8+).

    python3 app/servidor.py                 # http://127.0.0.1:8000 (solo este ordenador)
    python3 app/servidor.py --red           # también desde el móvil en la misma Wi-Fi
    python3 app/servidor.py --puerto 9000

Sirve la aplicación web (app/web/) y la API:
    GET /api/instrumento?simbolo=EURUSD&spread_medio=0.42[&datos_hasta=AAAA-MM-DD]
                                          consulta las fuentes, prepara y valida la tabla y
                                          devuelve los datos y el PDF (base64). spread_medio es
                                          el valor de Forex Benchmark que copia el usuario
    GET /api/salud                        comprobación de vida

Variables: PORT (puerto, para alojamientos), SQD_PERFIL (perfil JSON de la skill).
"""
import argparse
import base64
import json
import mimetypes
import os
import socket
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent))

from sqx import NOMBRE, VERSION, tabla  # noqa: E402
from sqx import instrumento, pdf  # noqa: E402
from sqx.fuentes import FuenteError, Fuentes  # noqa: E402

WEB = Path(__file__).resolve().parent / "web"
TIPOS = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
         ".css": "text/css; charset=utf-8", ".webmanifest": "application/manifest+json",
         ".png": "image/png", ".svg": "image/svg+xml", ".ico": "image/x-icon",
         ".json": "application/json"}
CSP = ("default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; manifest-src 'self'; worker-src 'self'; frame-ancestors 'none'; "
       "base-uri 'none'; form-action 'self'")
LIMITE_POR_MINUTO = 20


class Limitador:
    """Pocas consultas por IP y minuto, para no cargar las fuentes si se publica."""

    def __init__(self, limite=LIMITE_POR_MINUTO):
        self.limite, self.registro, self.cerrojo = limite, {}, threading.Lock()

    def permitir(self, ip):
        ahora = time.monotonic()
        with self.cerrojo:
            marcas = [t for t in self.registro.get(ip, []) if ahora - t < 60]
            if len(marcas) >= self.limite:
                self.registro[ip] = marcas
                return False
            marcas.append(ahora)
            self.registro[ip] = marcas
            return True


def consultar(simbolo, fuentes, perfil, spread_medio=None, datos_hasta=None):
    """(código HTTP, cuerpo JSON) de /api/instrumento."""
    try:
        res = instrumento.preparar(simbolo, fuentes, perfil, spread_medio, datos_hasta)
    except instrumento.ErrorEntrada as e:
        return 400, {"error": {"codigo": "simbolo_no_valido", "mensaje": str(e)}}
    except instrumento.SimboloNoEncontrado as e:
        return 404, {"error": {"codigo": "simbolo_desconocido", "mensaje": str(e),
                               "sugerencias": e.sugerencias}}
    except instrumento.FueraDeAlcance as e:
        return 422, {"error": {"codigo": "fuera_de_alcance", "mensaje": str(e)}}
    except FuenteError as e:
        return 502, {"error": {"codigo": "fuente_no_disponible",
                               "mensaje": f"No se pudo consultar {e.fuente}: {e.motivo}. Sin los "
                                          "datos del bróker no se prepara la tabla. Inténtalo de "
                                          "nuevo en unos minutos."}}
    except instrumento.ErrorInterno as e:
        return 500, {"error": {"codigo": "tabla_no_valida",
                               "mensaje": "Los datos obtenidos no pasan la validación de la skill; "
                                          "no se entrega la tabla.", "detalle": str(e)}}
    datos = pdf.generar([res])
    res["pdf"] = {"nombre": pdf.nombre_archivo([res]),
                  "base64": base64.b64encode(datos).decode("ascii")}
    return 200, res


class Manejador(BaseHTTPRequestHandler):
    server_version = f"InstrumentosSQX/{VERSION}"
    fuentes = None
    perfil = None
    limitador = None

    def log_message(self, formato, *args):  # registro breve en la consola
        sys.stderr.write(f"[{self.log_date_time_string()}] {self.address_string()} {formato % args}\n")

    def cabeceras_comunes(self):
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)

    def enviar(self, codigo, cuerpo, tipo, cache="no-store"):
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(cuerpo)))
        self.send_header("Cache-Control", cache)
        self.cabeceras_comunes()
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(cuerpo)

    def enviar_json(self, codigo, datos):
        self.enviar(codigo, json.dumps(datos, ensure_ascii=False).encode("utf-8"),
                    "application/json; charset=utf-8")

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/salud":
            return self.enviar_json(200, {"ok": True, "app": NOMBRE, "version": VERSION})
        if url.path == "/api/instrumento":
            if not self.limitador.permitir(self.client_address[0]):
                return self.enviar_json(429, {"error": {"codigo": "demasiadas_consultas",
                                                        "mensaje": "Demasiadas consultas seguidas. "
                                                                   "Espera un minuto."}})
            q = parse_qs(url.query)
            simbolo = q.get("simbolo", [""])[0]
            codigo, datos = consultar(simbolo, self.fuentes, self.perfil,
                                      q.get("spread_medio", [""])[0], q.get("datos_hasta", [""])[0])
            return self.enviar_json(codigo, datos)
        if url.path.startswith("/api/"):
            return self.enviar_json(404, {"error": {"codigo": "no_existe", "mensaje": "Ruta desconocida."}})
        return self.estatico(url.path)

    def estatico(self, ruta):
        rel = "index.html" if ruta in ("/", "") else ruta.lstrip("/")
        destino = (WEB / rel).resolve()
        try:
            destino.relative_to(WEB.resolve())
        except ValueError:
            return self.enviar(404, b"No encontrado", "text/plain; charset=utf-8")
        if not destino.is_file():
            return self.enviar(404, b"No encontrado", "text/plain; charset=utf-8")
        tipo = TIPOS.get(destino.suffix) or mimetypes.guess_type(destino.name)[0] or "application/octet-stream"
        # index.html y sw.js siempre se revalidan para que las actualizaciones lleguen enseguida
        cache = "no-cache" if destino.name in ("index.html", "sw.js") else "public, max-age=300"
        self.enviar(200, destino.read_bytes(), tipo, cache)


def crear_servidor(host, puerto, fuentes=None, perfil=None):
    Manejador.fuentes = fuentes or Fuentes()
    Manejador.perfil = perfil or tabla.cargar_perfil()
    Manejador.limitador = Limitador()
    return ThreadingHTTPServer((host, puerto), Manejador)


def ip_local():
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 80))  # dirección de documentación: no se envía nada
            return s.getsockname()[0]
    except OSError:
        return None


def main(argv=None):
    p = argparse.ArgumentParser(description=f"{NOMBRE}: servidor local")
    p.add_argument("--puerto", type=int, default=int(os.environ.get("PORT", 8000)))
    p.add_argument("--red", action="store_true",
                   help="escuchar en todas las interfaces (móvil en la misma Wi-Fi)")
    p.add_argument("--host", help="interfaz concreta (por defecto 127.0.0.1, o 0.0.0.0 con --red)")
    a = p.parse_args(argv)
    host = a.host or ("0.0.0.0" if a.red or os.environ.get("PORT") else "127.0.0.1")
    try:
        perfil = tabla.cargar_perfil()
    except tabla.ErrorUso as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    srv = crear_servidor(host, a.puerto, perfil=perfil)
    print(f"{NOMBRE} {VERSION}")
    print(f"Perfil: {perfil.d.get('nombre')} · {perfil.broker} · {perfil.d['plataforma']} · "
          f"cuenta en {perfil.d['divisa_cuenta']} ({perfil.origen})")
    print(f"Abre en este ordenador: http://127.0.0.1:{a.puerto}")
    if host == "0.0.0.0":
        ip = ip_local()
        if ip:
            print(f"Desde el móvil (misma Wi-Fi): http://{ip}:{a.puerto}")
    print("Para parar: Ctrl+C")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nServidor detenido.")
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
