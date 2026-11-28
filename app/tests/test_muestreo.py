"""Pruebas del spread medio automático (app/sqx/muestreo.py)."""
import datetime as dt
import json
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from apoyo import fuentes_simuladas, respuesta, tabla
from sqx import muestreo as M
from sqx.fuentes import leer_darwinex

UTC = dt.timezone.utc
DX = leer_darwinex(respuesta("darwinex.json"))


def registro(asset):
    for clase in ("forex", "indices", "commodities", "crypto"):
        for r in DX[clase]:
            if r["asset"] == asset:
                return r
    raise KeyError(asset)


def utc(*a):
    return dt.datetime(*a, tzinfo=UTC)


class TestHorario(unittest.TestCase):
    def test_hora_de_londres(self):
        self.assertEqual(M.hora_londres(utc(2026, 1, 15, 12)).hour, 12)   # invierno: UTC
        self.assertEqual(M.hora_londres(utc(2026, 7, 15, 12)).hour, 13)   # verano: UTC+1
        self.assertEqual(M.hora_londres(utc(2026, 3, 29, 0, 59)).hour, 0)  # justo antes del cambio
        self.assertEqual(M.hora_londres(utc(2026, 3, 29, 1)).hour, 2)
        self.assertEqual(M.hora_londres(utc(2026, 10, 25, 1)).hour, 1)    # vuelve a UTC

    def test_forex_de_domingo_a_viernes(self):
        r = registro("EURUSD")  # 17:05 → 16:55 Nueva York
        self.assertFalse(M.abierto(r, utc(2026, 11, 28, 12)))      # sábado
        self.assertFalse(M.abierto(r, utc(2026, 11, 29, 21)))      # domingo 16:00 NY
        self.assertTrue(M.abierto(r, utc(2026, 11, 29, 22, 10)))   # domingo 17:10 NY
        self.assertTrue(M.abierto(r, utc(2026, 11, 25, 3)))        # martes 22:00 NY
        self.assertFalse(M.abierto(r, utc(2026, 11, 25, 22)))      # pausa diaria 17:00 NY
        self.assertTrue(M.abierto(r, utc(2026, 11, 27, 21, 50)))   # viernes 16:50 NY
        self.assertFalse(M.abierto(r, utc(2026, 11, 27, 22)))      # viernes tras el cierre

    def test_sesion_dentro_del_dia(self):
        dax = registro("GDAXI")  # 01:30 → 20:55 Londres, de lunes a viernes
        self.assertTrue(M.abierto(dax, utc(2026, 11, 25, 10)))
        self.assertFalse(M.abierto(dax, utc(2026, 11, 25, 22)))
        self.assertFalse(M.abierto(dax, utc(2026, 11, 28, 10)))   # sábado
        nikkei = registro("NI225")  # 09:31 → 15:59 Nueva York
        self.assertFalse(M.abierto(nikkei, utc(2026, 11, 25, 3)))
        self.assertTrue(M.abierto(nikkei, utc(2026, 11, 25, 16)))  # 11:00 NY

    def test_horario_ilegible(self):
        self.assertFalse(M.abierto({"opentime": "x", "closetime": None}, utc(2026, 11, 25, 12)))


class TestMuestrear(unittest.TestCase):
    MARTES = utc(2026, 11, 24, 14)

    def test_pips_con_el_pip_de_la_tabla(self):
        dia, ultimas = {}, {}
        precios = {"EURUSD": (Decimal("1.09707"), Decimal("1.09712")),
                   "XAUUSD": (Decimal("3642.81"), Decimal("3643.22")),
                   "NDX": (Decimal("26714.3"), Decimal("26715.2"))}
        c = M.muestrear(DX, precios, ultimas, dia, self.MARTES)
        self.assertEqual(c["anadidas"], 3)
        self.assertEqual((dia["EURUSD"]["suma"], dia["EURUSD"]["pip"]), ("0.5", "0.0001"))
        self.assertEqual((dia["XAUUSD"]["suma"], dia["XAUUSD"]["pip"]), ("41", "0.01"))
        self.assertEqual((dia["NDX"]["suma"], dia["NDX"]["pip"]), ("0.9", "1"))

    def test_cotizacion_repetida_no_cuenta(self):
        dia, ultimas = {}, {}
        precios = {"EURUSD": (Decimal("1.1"), Decimal("1.10005"))}
        M.muestrear(DX, precios, ultimas, dia, self.MARTES)
        c = M.muestrear(DX, precios, ultimas, dia, self.MARTES + dt.timedelta(minutes=15))
        self.assertEqual((c["sin_cambio"], dia["EURUSD"]["n"]), (1, 1))
        precios["EURUSD"] = (Decimal("1.1001"), Decimal("1.1002"))
        M.muestrear(DX, precios, ultimas, dia, self.MARTES + dt.timedelta(minutes=30))
        self.assertEqual(dia["EURUSD"]["n"], 2)
        self.assertEqual(Decimal(dia["EURUSD"]["suma"]), Decimal("1.5"))
        self.assertEqual((dia["EURUSD"]["min"], dia["EURUSD"]["max"]), ("0.5", "1"))

    def test_mercado_cerrado_e_incoherente(self):
        dia = {}
        precios = {"EURUSD": (Decimal("1.1"), Decimal("1.2"))}
        c = M.muestrear(DX, precios, {}, dia, utc(2026, 11, 28, 12))  # sábado
        self.assertEqual((c["anadidas"], dia), (0, {}))
        c = M.muestrear(DX, {"EURUSD": (Decimal("1.2"), Decimal("1.1"))}, {}, dia, self.MARTES)
        self.assertNotIn("EURUSD", dia)  # ask < bid


class TestMedias(unittest.TestCase):
    def dia(self, n, suma, pip="0.0001"):
        return {"EURUSD": {"n": n, "suma": suma, "pip": pip, "min": "0.3", "max": "0.9"}}

    def test_media_de_los_ultimos_30_dias(self):
        hoy = dt.date(2026, 12, 31)
        dias = {"2026-11-30": self.dia(100, "100"),        # fuera de la ventana
                "2026-12-02": self.dia(96, "38.4"),
                "2026-12-31": self.dia(4, "2")}
        m = M.calcular_medias(dias, hoy, "2026-11-30", utc(2026, 12, 31, 10))
        e = m["simbolos"]["EURUSD"]
        self.assertEqual((e["muestras"], e["desde"], e["hasta"]), (100, "2026-12-02", "2026-12-31"))
        self.assertEqual(e["spread"], "0.404")  # (38.4 + 2) / 100
        self.assertEqual(m["fuente"], tabla.FUENTE_MUESTREO)
        v, f = tabla.spread_desde_medias("EURUSD", m, "0.0001", utc(2026, 12, 31, 11))
        self.assertEqual(v, "0.40")
        self.assertEqual(f["muestras"], "100")

    def test_cambio_de_pip_reinicia(self):
        dias = {"2026-12-01": self.dia(50, "50", pip="0.001"), "2026-12-02": self.dia(60, "30")}
        e = M.calcular_medias(dias, dt.date(2026, 12, 2), "2026-12-01",
                              utc(2026, 12, 2, 1))["simbolos"]["EURUSD"]
        self.assertEqual((e["muestras"], e["pip"], e["desde"]), (60, "0.0001", "2026-12-02"))


class TestRonda(unittest.TestCase):
    def test_ronda_completa_en_disco(self):
        with tempfile.TemporaryDirectory() as tmp:
            carpeta = Path(tmp)
            viejo = carpeta / "dias" / "2026-10-01.json"
            viejo.parent.mkdir()
            viejo.write_text("{}", encoding="utf-8")
            ahora = utc(2026, 11, 24, 14)
            c = M.ejecutar(carpeta, fuentes_simuladas(), ahora)
            self.assertGreater(c["anadidas"], 0)
            self.assertFalse(viejo.exists())  # más de 40 días: se borra
            m = json.loads((carpeta / "medias.json").read_text(encoding="utf-8"))
            self.assertEqual((m["inicio"], m["generado_utc"]), ("2026-11-24", "2026-11-24 14:00"))
            self.assertIn("EURUSD", m["simbolos"])
            # Segunda ronda con las mismas cotizaciones: no se cuentan dos veces
            c2 = M.ejecutar(carpeta, fuentes_simuladas(), ahora + dt.timedelta(minutes=15))
            self.assertEqual(c2["anadidas"], 0)
            m2 = json.loads((carpeta / "medias.json").read_text(encoding="utf-8"))
            self.assertEqual(m2["simbolos"]["EURUSD"]["muestras"], 1)
            self.assertEqual(m2["inicio"], "2026-11-24")


if __name__ == "__main__":
    unittest.main()
