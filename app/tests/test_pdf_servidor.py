"""Pruebas del PDF, de la lectura de fuentes y del servidor."""
import base64
import http.client
import json
import re
import socket
import tempfile
import threading
import unittest
import unittest.mock
import urllib.error
import zlib
from pathlib import Path

from apoyo import APP, PERFIL, fuentes_simuladas, respuesta, tabla
from sqx import fuentes as F
from sqx import instrumento as I
from sqx import pdf

import servidor


def textos_pdf(datos):
    """Textos dibujados en el PDF (cadenas hexadecimales de los flujos comprimidos)."""
    textos = []
    for m in re.finditer(rb"stream\n(.*?)\nendstream", datos, re.S):
        flujo = zlib.decompress(m.group(1)).decode("latin-1")
        textos += [bytes.fromhex(h).decode("cp1252") for h in re.findall(r"<([0-9a-f]+)> Tj", flujo)]
    return textos


class TestPdf(unittest.TestCase):
    def generar(self, *simbolos):
        rs = [I.preparar(s, fuentes_simuladas(), PERFIL) for s in simbolos]
        return rs, pdf.generar(rs)

    def test_pdf_valido_con_estructura_de_la_skill(self):
        rs, datos = self.generar("EURUSD")
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "x.pdf"
            p.write_bytes(datos)
            self.assertIsNone(tabla.comprobar_pdf(p))
        t = textos_pdf(datos)
        for esperado in (tabla.TITULO, tabla.CREDITO, "1. Configuración principal del instrumento",
                         "2. Comisiones, swaps y rollover", "EURUSD_Darwinex", "WEDNESDAY", "23:59",
                         "Anexo: fuentes, fechas, cálculos y ajustes", "Ajuste personal"):
            self.assertIn(esperado, " ".join(t), esperado)
        cabeceras = " ".join(t)
        for _, cab, _, _ in tabla.T1 + tabla.T2:
            for palabra in cab.split():
                self.assertIn(palabra, cabeceras)
        self.assertNotIn("TABLA INCOMPLETA", cabeceras)
        self.assertIn("cuenta en USD", cabeceras)

    def test_pdf_incompleto(self):
        rs, datos = self.generar("EURUSD", "BTCUSD")
        t = " ".join(textos_pdf(datos))
        self.assertIn("TABLA INCOMPLETA", t)
        self.assertIn(tabla.PEND, t)
        self.assertEqual(pdf.nombre_archivo(rs)[-15:], "_INCOMPLETA.pdf")
        self.assertGreaterEqual(datos.count(b"/Type /Page /Parent"), 3)

    def test_nombre_archivo(self):
        rs, _ = self.generar("USATECHIDXUSD")
        self.assertRegex(pdf.nombre_archivo(rs), r"^USATECHIDXUSD_Darwinex_\d{4}-\d{2}-\d{2}\.pdf$")

    def test_texto_fuera_de_cp1252(self):
        self.assertEqual(pdf.a_cp1252("a → b ≠ c − d"), b"a -> b != c - d")
        self.assertEqual(pdf.a_cp1252("€ ñ « » ÷ ×"), "€ ñ « » ÷ ×".encode("cp1252"))

    def test_envolver(self):
        url = "https://www.darwinex.com/graphics/spreads?dx_platform=DX" * 3
        for linea in pdf.envolver(url, "normal", 7, 100):
            self.assertLessEqual(pdf.ancho_texto(linea, "normal", 7), 100)


class TestLecturaFuentes(unittest.TestCase):
    def test_precios(self):
        p = F.leer_precios(respuesta("precios.json"))
        self.assertIsNone(p["FOO"])
        bid, ask = p["EURUSD"]
        self.assertEqual(str(ask - bid), "0.000050")

    def test_bce(self):
        fecha, tipos = F.leer_bce(respuesta("bce.xml"))
        self.assertRegex(fecha, r"^\d{4}-\d{2}-\d{2}$")
        self.assertEqual(tipos["EUR"], 1)
        self.assertIn("JPY", tipos)
        with self.assertRaises(F.FuenteError):
            F.leer_bce(b"<html/>")

    def test_costes(self):
        self.assertIn("2 orders", F.leer_costes(respuesta("costes.html")))
        self.assertIsNone(F.leer_costes(b"<p>nada</p>"))

    def test_errores_de_conexion(self):
        casos = [urllib.error.URLError("Name or service not known"),
                 urllib.error.URLError(socket.timeout("timed out")), socket.timeout("timed out"),
                 urllib.error.HTTPError(F.URL_DARWINEX, 403, "Forbidden", {}, None),
                 ConnectionResetError("reset")]
        for exc in casos:
            with unittest.mock.patch("urllib.request.urlopen", side_effect=exc):
                with self.assertRaises(F.FuenteError) as e:
                    F.descargar(F.URL_DARWINEX, "Darwinex")
                self.assertTrue(e.exception.motivo)

    def test_sin_cabecera_origin(self):
        capturada = {}

        class Resp:
            def __enter__(self): return self
            def __exit__(self, *a): return False
            def read(self): return b"{}"

        def falso(req, timeout):
            capturada.update(dict(req.header_items()))
            return Resp()
        with unittest.mock.patch("urllib.request.urlopen", side_effect=falso):
            F.descargar(F.URL_DARWINEX, "Darwinex")
        self.assertNotIn("Origin", capturada)

    def test_cache_de_darwinex(self):
        llamadas = []

        def descargar(url, fuente, timeout=None):
            llamadas.append(url)
            return respuesta("darwinex.json"), F.ahora_utc()
        f = F.Fuentes(descargar)
        f.darwinex()
        f.darwinex()
        self.assertEqual(len(llamadas), 1)


class TestServidor(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        servidor.Manejador.log_message = lambda *a: None
        cls.fuentes = fuentes_simuladas()
        cls.srv = servidor.crear_servidor("127.0.0.1", 0, fuentes=cls.fuentes, perfil=PERFIL)
        cls.puerto = cls.srv.server_address[1]
        threading.Thread(target=cls.srv.serve_forever, daemon=True).start()

    @classmethod
    def tearDownClass(cls):
        cls.srv.shutdown()
        cls.srv.server_close()

    def get(self, ruta):
        c = http.client.HTTPConnection("127.0.0.1", self.puerto, timeout=20)
        c.request("GET", ruta)
        r = c.getresponse()
        cuerpo = r.read()
        c.close()
        return r.status, dict(r.getheaders()), cuerpo

    def test_pagina_principal(self):
        s, h, cuerpo = self.get("/")
        texto = cuerpo.decode()
        self.assertEqual(s, 200)
        self.assertIn("<h1>Instrumentos SQX</h1>", texto)
        self.assertIn("<title>Instrumentos SQX</title>", texto)
        self.assertIn("¿De qué activo quieres obtener los datos?", texto)
        self.assertIn("Obtener datos", texto)
        self.assertIn("Descargar PDF", texto)
        self.assertIn("default-src 'self'", h["Content-Security-Policy"])

    def test_manifiesto(self):
        s, h, cuerpo = self.get("/manifest.webmanifest")
        m = json.loads(cuerpo)
        self.assertEqual((m["name"], m["short_name"]), ("Instrumentos SQX", "Instrumentos SQX"))
        self.assertEqual(m["display"], "standalone")
        for icono in m["icons"]:
            self.assertTrue((APP / "web" / icono["src"]).is_file(), icono["src"])
        self.assertEqual(self.get("/sw.js")[0], 200)

    def test_consulta_correcta_con_pdf(self):
        s, _, cuerpo = self.get("/api/instrumento?simbolo=EURUSD")
        d = json.loads(cuerpo)
        self.assertEqual(s, 200)
        self.assertEqual(d["estado"], "COMPLETA")
        self.assertTrue(base64.b64decode(d["pdf"]["base64"]).startswith(b"%PDF-"))
        self.assertEqual(d["perfil"]["divisa_cuenta"], "USD")

    def test_errores(self):
        for ruta, codigo, clave in (("/api/instrumento?simbolo=", 400, "simbolo_no_valido"),
                                    ("/api/instrumento?simbolo=EURUSX", 404, "simbolo_desconocido"),
                                    ("/api/instrumento?simbolo=AAPL", 422, "fuera_de_alcance"),
                                    ("/api/otra", 404, "no_existe")):
            s, _, cuerpo = self.get(ruta)
            self.assertEqual(s, codigo, ruta)
            self.assertEqual(json.loads(cuerpo)["error"]["codigo"], clave)

    def test_fuente_caida(self):
        codigo, d = servidor.consultar("EURUSD", fuentes_simuladas(fallos=[F.URL_DARWINEX]), PERFIL)
        self.assertEqual(codigo, 502)
        self.assertIn("Darwinex", d["error"]["mensaje"])

    def test_rutas_fuera_de_web(self):
        for ruta in ("/../servidor.py", "/%2e%2e/servidor.py", "/../../scripts/tabla.py", "/no-existe.js"):
            self.assertEqual(self.get(ruta)[0], 404, ruta)

    def test_limite_de_consultas(self):
        lim = servidor.Limitador(limite=2)
        self.assertTrue(lim.permitir("1.2.3.4"))
        self.assertTrue(lim.permitir("1.2.3.4"))
        self.assertFalse(lim.permitir("1.2.3.4"))
        self.assertTrue(lim.permitir("5.6.7.8"))


if __name__ == "__main__":
    unittest.main()
