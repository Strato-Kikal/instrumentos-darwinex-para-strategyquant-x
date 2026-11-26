"""Pruebas de la preparación de tablas (lo que antes hacía Claude) con respuestas reales guardadas.

    python3 -m unittest discover -s app/tests -v
"""
import datetime as dt
import json
import unittest

from apoyo import PERFIL, darwinex_modificado, fuentes_simuladas, tabla
from sqx import instrumento as I
from sqx.fuentes import URL_BCE, URL_COSTES, URL_DARWINEX, FuenteError


def preparar(simbolo, **kw):
    return I.preparar(simbolo, fuentes_simuladas(**kw), PERFIL)


class TestCompletas(unittest.TestCase):
    def test_eurusd(self):
        r = preparar("EURUSD")
        t = r["tabla"]
        self.assertEqual(r["estado"], "COMPLETA", r["avisos"])
        self.assertEqual((t["tipo"], t["pip_tick"], t["no_pip_tick"], t["point_value"]),
                         ("Forex", "0.0001", "0.00001", "100000"))
        self.assertEqual((t["swap_largo"], t["swap_corto"], t["triple_swap"]), ("-8.30", "1.30", "WEDNESDAY"))
        self.assertEqual(t["spread"], "0.5")  # 1.09712 − 1.09707 = 0.00005 → 0.5 pips
        # Comisión 2.5 EUR por orden × 2 × EURUSD del BCE
        self.assertTrue(t["comision"].endswith(" aprox."))
        eurusd = [e for e in t["fuentes"]["comision"]["entradas"] if e["nombre"] == "tipo_cambio EURUSD"][0]
        esperado = round(2.5 * 2 * float(eurusd["valor"]), 2)
        self.assertAlmostEqual(float(t["comision"].split()[0]), esperado, places=2)
        self.assertEqual(t["nombre"], "EURUSD_Darwinex")

    def test_valida_con_la_skill(self):
        for s in ("EURUSD", "USDJPY", "USDCAD", "GBPJPY", "NDX", "GDAXI", "XAUUSD", "XTIUSD", "BTCUSD", "NI225"):
            r = preparar(s)
            v = tabla.validar(r["tabla"], PERFIL)
            self.assertEqual(v.errores, [], s)
            self.assertEqual(v.estado, r["estado"], s)

    def test_fechas_actuales_y_no_de_ejemplos(self):
        hoy = dt.datetime.now(dt.timezone.utc).date().isoformat()
        r = preparar("NDX")
        t = r["tabla"]
        self.assertEqual(t["consulta"], hoy)
        for campo, f in t["fuentes"].items():
            if f.get("url") == URL_DARWINEX or f["tipo"] == "observado":
                self.assertEqual(f["fecha"], hoy, campo)
            for e in f.get("entradas", []):
                if e.get("url") in (URL_DARWINEX, URL_COSTES):
                    self.assertEqual(e["fecha"], hoy, (campo, e["nombre"]))
        self.assertNotIn("2026-10-27 08:1", json.dumps(t))  # horas de los ejemplos antiguos

    def test_usdjpy_convierte_a_usd(self):
        t = preparar("USDJPY")["tabla"]
        self.assertEqual((t["pip_tick"], t["no_pip_tick"]), ("0.01", "0.001"))
        self.assertTrue(t["point_value"].endswith(" aprox."))
        self.assertEqual(t["comision"], "5.00")  # 2.5 USD (divisa base) × 2, sin conversión
        self.assertTrue(t["swap_largo"].endswith(" aprox."))

    def test_usdcad_triple_jueves(self):
        self.assertEqual(preparar("USDCAD")["tabla"]["triple_swap"], "THURSDAY")

    def test_indice_tick_real_y_comision(self):
        t = preparar("NDX")["tabla"]
        self.assertEqual((t["pip_tick"], t["no_pip_tick"], t["point_value"], t["comision"], t["triple_swap"]),
                         ("1", "0.1", "10", "5.50", "FRIDAY"))
        self.assertEqual(t["fuentes"]["no_pip_tick"]["formula"], "tick real = tick_value ÷ contrato")

    def test_dukascopy(self):
        r = preparar("usatechidxusd")
        self.assertEqual((r["simbolo"], r["ticker_darwinex"], r["tabla"]["nombre"]),
                         ("USATECHIDXUSD", "NDX", "NDX_Darwinex"))
        self.assertTrue(any("Dukascopy" in n for n in r["tabla"]["notas"]))

    def test_indice_en_eur(self):
        t = preparar("GDAXI")["tabla"]
        for k in ("point_value", "comision", "swap_largo", "swap_corto"):
            self.assertTrue(t[k].endswith(" aprox."), k)

    def test_oro_porcentaje(self):
        t = preparar("XAUUSD")["tabla"]
        self.assertEqual((t["modelo_comision"], t["comision"], t["pip_tick"], t["no_pip_tick"], t["point_value"]),
                         ("Comisión en porcentaje", "0.005", "0.01", "0.01", "100"))


class TestPendientes(unittest.TestCase):
    def test_petroleo_nota_propia(self):
        r = preparar("XTIUSD")
        self.assertEqual(r["pendientes"], ["triple_swap"])
        self.assertIn("swaps-xtiusd-xngusd", r["tabla"]["fuentes"]["triple_swap"]["motivo"])

    def test_cripto_swaps_y_triple(self):
        r = preparar("BTCUSD")
        self.assertEqual(r["estado"], "INCOMPLETA")
        self.assertEqual(set(r["pendientes"]), {"swap_largo", "swap_corto", "triple_swap"})

    def test_discrepancia_en_datos_de_darwinex(self):
        r = preparar("NI225")  # tickValue ÷ contrato no coincide con tickSize
        self.assertIn("no_pip_tick", r["pendientes"])
        self.assertIn("discrepancia", r["tabla"]["fuentes"]["no_pip_tick"]["motivo"])

    def test_datos_incompletos_de_darwinex(self):
        def quitar(d):
            for x in d["forex"]:
                if x["asset"] == "EURUSD":
                    x["swapLong"] = None
                    x["tripleSwapDay"] = None
                    del x["commission"]
        r = preparar("EURUSD", sustituir={URL_DARWINEX: darwinex_modificado(quitar)})
        self.assertEqual(set(r["pendientes"]), {"swap_largo", "triple_swap", "comision"})
        for k in r["pendientes"]:
            self.assertEqual(r["tabla"][k], tabla.PEND)
            self.assertTrue(r["tabla"]["fuentes"][k]["motivo"])

    def test_triple_que_no_cuadra_con_la_nota(self):
        def cambiar(d):
            for x in d["forex"]:
                if x["asset"] == "EURUSD":
                    x["tripleSwapDay"] = 6
        r = preparar("EURUSD", sustituir={URL_DARWINEX: darwinex_modificado(cambiar)})
        self.assertEqual(r["pendientes"], ["triple_swap"])


class TestFallosDeFuentes(unittest.TestCase):
    def test_darwinex_caido_no_da_tabla(self):
        with self.assertRaises(FuenteError) as e:
            preparar("EURUSD", fallos=[URL_DARWINEX])
        self.assertEqual(e.exception.fuente, "Darwinex")

    def test_feed_de_spread_caido(self):
        r = preparar("NDX", fallos=["https://widgets.fxbluelabs.com"])
        self.assertEqual(r["pendientes"], ["spread"])
        self.assertTrue(any("spread" in a for a in r["avisos"]))
        self.assertIn("fallo", [c["estado"] for c in r["consultas"]])

    def test_feed_sin_datos_del_simbolo(self):
        sin = b'{"symbols":[{"symbol":"NDX","noData":true}]}'
        r = preparar("NDX", sustituir={"https://widgets.fxbluelabs.com": sin})
        self.assertEqual(r["pendientes"], ["spread"])

    def test_bce_caido(self):
        r = preparar("EURUSD", fallos=[URL_BCE])
        self.assertEqual(r["pendientes"], ["comision"])  # EUR → USD; el resto va en USD
        r = preparar("GDAXI", fallos=[URL_BCE])
        self.assertEqual(set(r["pendientes"]), {"point_value", "comision", "swap_largo", "swap_corto"})

    def test_bce_no_hace_falta_en_usd(self):
        r = preparar("NDX", fallos=[URL_BCE])
        self.assertEqual(r["estado"], "COMPLETA")
        self.assertNotIn("BCE (tipos de referencia)", [c["fuente"] for c in r["consultas"]])

    def test_pagina_de_costes(self):
        r = preparar("NDX", fallos=[URL_COSTES])
        self.assertEqual(r["pendientes"], ["comision"])
        r = preparar("NDX", sustituir={URL_COSTES: b"<html>otra cosa</html>"})
        self.assertEqual(r["pendientes"], ["comision"])

    def test_respuesta_dañada_de_darwinex(self):
        with self.assertRaises(FuenteError):
            preparar("EURUSD", sustituir={URL_DARWINEX: b"<html>mantenimiento</html>"})
        with self.assertRaises(FuenteError):
            preparar("EURUSD", sustituir={URL_DARWINEX: b'{"otra": 1}'})


class TestSimbolos(unittest.TestCase):
    def test_desconocido_con_sugerencias(self):
        with self.assertRaises(I.SimboloNoEncontrado) as e:
            preparar("EURUSX")
        self.assertIn("EURUSD", e.exception.sugerencias)
        with self.assertRaises(I.SimboloNoEncontrado) as e:
            preparar("ZZZZZZ")
        self.assertEqual(e.exception.sugerencias, [])

    def test_fuera_de_alcance(self):
        with self.assertRaises(I.FueraDeAlcance):
            preparar("AAPL")

    def test_entrada_no_valida(self):
        for mal in ("", "   ", "../etc", "EUR USD€", "A" * 41):
            with self.assertRaises(I.ErrorEntrada, msg=mal):
                I.normalizar(mal)
        self.assertEqual(I.normalizar(" eur/usd "), "EURUSD")


class TestUtilidades(unittest.TestCase):
    def test_hora_nueva_york(self):
        utc = dt.timezone.utc
        self.assertEqual(I.hora_nueva_york(dt.datetime(2026, 7, 1, 12, tzinfo=utc)).hour, 8)
        self.assertEqual(I.hora_nueva_york(dt.datetime(2026, 12, 1, 12, tzinfo=utc)).hour, 7)
        # 2026: cambio de EE. UU. el 8 de marzo y el 1 de noviembre
        self.assertEqual(I.hora_nueva_york(dt.datetime(2026, 3, 10, 12, tzinfo=utc)).hour, 8)
        self.assertEqual(I.hora_nueva_york(dt.datetime(2026, 11, 2, 12, tzinfo=utc)).hour, 7)

    def test_fin_de_semana(self):
        utc = dt.timezone.utc
        self.assertTrue(I.fin_de_semana(dt.datetime(2026, 11, 28, 12, tzinfo=utc)))   # sábado
        self.assertFalse(I.fin_de_semana(dt.datetime(2026, 11, 26, 12, tzinfo=utc)))  # jueves
        self.assertTrue(I.fin_de_semana(dt.datetime(2026, 11, 27, 22, tzinfo=utc)))   # vie 17:00 NY
        self.assertFalse(I.fin_de_semana(dt.datetime(2026, 11, 29, 22, 10, tzinfo=utc)))  # dom 17:10 NY

    def test_aviso_mercado_cerrado(self):
        sabado = dt.datetime(2026, 11, 28, 12, tzinfo=dt.timezone.utc)
        f = fuentes_simuladas(hora=sabado)
        p = I.Preparacion("NDX", f, PERFIL)
        p.f_dx, p.ticker, p.d, p.fu = "2026-11-28", "NDX", {"pip_tick": "1"}, {}
        p.campo_spread()
        self.assertTrue(any("Mercado cerrado" in a for a in p.avisos))

    def test_detalle_distingue_origenes(self):
        r = preparar("EURUSD")
        tipos = {f["campo"]: f["tipo"] for f in r["detalle"]}
        self.assertEqual(tipos["spread"], "observado")
        self.assertEqual(tipos["comision"], "calculo")
        self.assertEqual(tipos["tipo"], "regla")
        self.assertEqual(tipos["swap_largo"], "dato")
        for k in tabla.AJUSTES:
            self.assertEqual(tipos[k], "ajuste")
        self.assertEqual(r["perfil"]["divisa_cuenta"], "USD")
        self.assertEqual(r["fila_pdf"]["rollover"], PERFIL.ajustes["rollover"])


if __name__ == "__main__":
    unittest.main()
