"""Pruebas de la preparación de tablas (lo que antes hacía Claude) con respuestas reales guardadas.

    python3 -m unittest discover -s app/tests -v
"""
import datetime as dt
import json
import unittest

from apoyo import (JUEVES, PERFIL, SABADO, darwinex_modificado, en_hora, fuentes_simuladas,
                   medias_bytes, tabla)
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
        self.assertEqual(t["spread"], "0.42")  # spread medio automático (0.4234 redondeado)
        self.assertEqual(t["fuentes"]["spread"]["tipo"], "promedio")
        self.assertEqual(t["spread_instantaneo"], "0.5")  # 1.09712 − 1.09707 = 0.00005 → 0.5 pips
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
        self.assertEqual((t["spread"], t["fuentes"]["spread"]["pip_fuente"]), ("0.98", "0.01"))

    def test_usdcad_triple_jueves(self):
        self.assertEqual(preparar("USDCAD")["tabla"]["triple_swap"], "THURSDAY")

    def test_indice_tick_real_y_comision(self):
        t = preparar("NDX")["tabla"]
        self.assertEqual((t["pip_tick"], t["no_pip_tick"], t["point_value"], t["comision"], t["triple_swap"]),
                         ("1", "0.1", "10", "5.50", "FRIDAY"))
        self.assertEqual(t["fuentes"]["no_pip_tick"]["formula"], "tick real (Pip/Tick Step) = tick_value ÷ contrato")

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


class TestTextosParaSQX(unittest.TestCase):
    """Página 1: valores con su unidad, tal como se copian en SQX."""

    def test_forex(self):
        r = preparar("EURUSD")
        t = r["textos"]
        self.assertEqual(r["estado_texto"], "Datos completos · pendiente de validar en SQX")
        self.assertEqual((t["pip_tick"], t["no_pip_tick"], t["point_value"]), ("0.0001", "0.00001", "100000"))
        self.assertEqual(t["spread"], "0.42 pips\nmedio 30 días · 24 h")
        self.assertRegex(t["spread_instantaneo"], r"^0\.5 pips · \d{4}-\d{2}-\d{2} \d{2}:\d{2} UTC · no va en SQX$")
        self.assertIn(tabla.ETIQUETA_MUESTREO, r["spread_lineas"][0])
        self.assertRegex(t["comision"], r"^\d+\.\d{2} USD por lote, ida y vuelta\naprox\. · cambio BCE "
                                        r"del \d{4}-\d{2}-\d{2}$")
        self.assertEqual(t["tipo_swap"], "Dinero / Money\nUSD por lote y día")
        self.assertEqual((t["swap_largo"], t["swap_corto"]), ("-8.30", "1.30"))
        self.assertEqual(t["rollover"], "23:59 · ajuste del perfil\nDatos: (EST+07) New York Trading "
                                        "hours, US DST")
        self.assertEqual(t["cobro_swap"], "17:00 Nueva York\n= 00:00 servidor MT5")
        self.assertIn("metatrader-time", r["fila_pdf"] and
                      [f for f in r["detalle"] if f["campo"] == "cobro_swap"][0]["explicacion"])
        pruebas = " ".join(r["pruebas_sqx"])
        for esperado in ("1 lote", "23:59", "-8.30 USD por lote", "WEDNESDAY", "0.42 pips (spread medio"):
            self.assertIn(esperado, pruebas)

    def test_indice_en_eur_y_metal(self):
        r = preparar("GDAXI")
        t = r["textos"]
        self.assertEqual(t["cobro_swap"], "Al cierre del mercado")
        self.assertRegex(t["swap_largo"], r"^-?\d+\.\d{2}\naprox\. · BCE \d{4}-\d{2}-\d{2}$")
        self.assertIn("FRIDAY", " ".join(r["pruebas_sqx"]))
        t = preparar("XAUUSD")["textos"]
        self.assertEqual(t["comision"], "0.005 % del valor, ida y vuelta")
        self.assertEqual(t["swap_largo"], "-50.70")

    def test_etiquetas_de_sqx(self):
        nombres = {f["campo"]: f["casilla"] for f in preparar("EURUSD")["detalle"]}
        self.assertEqual((nombres["pip_tick"], nombres["no_pip_tick"]), ("Pip/Tick Size", "Pip/Tick Step"))
        self.assertEqual(nombres["rollover"], "Rollover (SQX)")
        self.assertEqual((nombres["spread"], nombres["spread_instantaneo"]),
                         ("Default Spread", "Spread instantáneo (informativo)"))


class TestSpreadMedio(unittest.TestCase):
    """Default Spread = spread medio automático de Darwinex (medias.json), sin escribir nada; el
    instantáneo, solo informativo."""

    def test_oro_en_pips_de_001(self):
        t = preparar("XAUUSD")["tabla"]
        self.assertEqual((t["spread"], t["fuentes"]["spread"]["pip_fuente"]), ("48.23", "0.01"))
        self.assertEqual(t["spread_instantaneo"], "41")  # 0.41 USD de precio

    def test_criterio_registrado(self):
        f = preparar("EURUSD")["tabla"]["fuentes"]["spread"]
        for k, v in tabla.CRITERIO_MUESTREO.items():
            self.assertEqual(f[k], v, k)
        self.assertEqual((f["url"], f["muestras"]), (tabla.URL_DATOS_SPREAD, "1900"))
        self.assertNotEqual(f["fecha"], f["desde"])  # consulta ≠ periodo

    def test_indices_petroleo_y_cripto_tienen_spread(self):
        for s, esperado in (("NDX", "1.10"), ("GDAXI", "1.20"), ("XTIUSD", "3.60"), ("BTCUSD", "14.50")):
            t = preparar(s)["tabla"]
            self.assertEqual(t["spread"], esperado, s)
            self.assertEqual(t["fuentes"]["spread"]["tipo"], "promedio", s)

    def test_simbolo_aun_sin_muestras(self):
        with en_hora(JUEVES):  # mercado abierto: no hay último spread de cierre que usar
            r = preparar("NI225")
        self.assertIn("spread", r["pendientes"])
        self.assertIn("todavía no tiene datos de NI225", r["tabla"]["fuentes"]["spread"]["motivo"])

    def test_mercado_cerrado_usa_el_ultimo_spread(self):
        """Sábado, sin media: Default Spread = último spread antes del cierre del viernes."""
        with en_hora(SABADO):
            r = preparar("EURUSD", sustituir={tabla.URL_DATOS_SPREAD: medias_bytes(muestras=12)})
        t = r["tabla"]
        f = t["fuentes"]["spread"]
        self.assertEqual((r["estado"], r["pendientes"]), ("COMPLETA", []))
        self.assertEqual((t["spread"], f["tipo"], f["lectura"]), ("0.50", "cierre", "0.5"))
        self.assertEqual((f["cierre_utc"], f["reabre_utc"]), ("2026-11-27 21:55", "2026-11-29 22:05"))
        self.assertTrue(any("provisional" in a for a in r["avisos"]))

    def test_cierre_publicado_por_el_muestreo_tiene_prioridad(self):
        m = json.loads(medias_bytes(quitar=("EURUSD",)))
        m["cierres"] = {"EURUSD": {"spread": "0.8", "pip": "0.0001", "bid": "1.1", "ask": "1.10008",
                                   "cierre_utc": "2026-11-27 21:55", "reabre_utc": "2026-11-29 22:05"}}
        with en_hora(SABADO):
            r = preparar("EURUSD", sustituir={tabla.URL_DATOS_SPREAD: json.dumps(m).encode()})
        f = r["tabla"]["fuentes"]["spread"]
        self.assertEqual((r["tabla"]["spread"], f["url"]), ("0.80", tabla.URL_DATOS_SPREAD))

    def test_pocas_muestras_queda_pendiente(self):
        with en_hora(JUEVES):
            r = preparar("EURUSD", sustituir={tabla.URL_DATOS_SPREAD: medias_bytes(muestras=12)})
        self.assertEqual((r["estado"], r["pendientes"]), ("INCOMPLETA", ["spread"]))
        self.assertIn("se rellena solo", r["tabla"]["fuentes"]["spread"]["motivo"])
        self.assertEqual(r["tabla"]["spread_instantaneo"], "0.5")  # se informa, pero no sustituye

    def test_periodo_aun_corto(self):
        r = preparar("EURUSD", sustituir={tabla.URL_DATOS_SPREAD: medias_bytes(dias=4)})
        self.assertEqual(r["estado"], "COMPLETA")
        self.assertTrue(any("cubre de momento 4 días" in a for a in r["avisos"]))
        self.assertIn("llegará a 30 días sola", r["spread_lineas"][0])

    def test_medias_no_disponibles(self):
        r = preparar("EURUSD", fallos=[tabla.URL_DATOS_SPREAD])
        self.assertEqual(r["pendientes"], ["spread"])
        self.assertTrue(any("spread medio automático" in a for a in r["avisos"]))
        r = preparar("EURUSD", sustituir={tabla.URL_DATOS_SPREAD: b"<html>no</html>"})
        self.assertEqual(r["pendientes"], ["spread"])

    def test_aviso_si_no_se_parece_al_instantaneo(self):
        r = preparar("EURUSD", sustituir={tabla.URL_DATOS_SPREAD: medias_bytes(
            valores={"EURUSD": ("42", "0.0001")})})
        self.assertEqual(r["estado"], "COMPLETA")
        self.assertTrue(any("se diferencian más de" in a for a in r["avisos"]))

    def test_comision_aparte_del_spread(self):
        r = preparar("EURUSD")
        self.assertEqual(r["tabla"]["fuentes"]["spread"]["comision"], "excluida")
        self.assertIn("sin comisiones", r["spread_etiqueta"])


class TestPendientes(unittest.TestCase):
    def test_petroleo_nota_propia(self):
        r = preparar("XTIUSD")
        self.assertEqual(r["pendientes"], ["triple_swap", "cobro_swap"])
        self.assertEqual(r["faltan"], ["Triple swap", "Cobro del swap (Darwinex)"])
        self.assertEqual(r["fila_pdf"]["tipo_swap"], "Dinero / Money")
        self.assertIn("swaps-xtiusd-xngusd", r["tabla"]["fuentes"]["triple_swap"]["motivo"])

    def test_cripto_swaps_y_triple(self):
        r = preparar("BTCUSD")
        self.assertEqual(r["estado"], "INCOMPLETA")
        self.assertEqual(set(r["pendientes"]), {"swap_largo", "swap_corto", "triple_swap",
                                                "tipo_swap", "cobro_swap"})
        self.assertTrue(r["estado_texto"].startswith("Datos incompletos · faltan: Swap largo, "))
        self.assertEqual(r["textos"]["comision"], "0.1 % del valor, ida y vuelta")

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
        self.assertEqual(set(r["pendientes"]), {"swap_largo", "triple_swap", "comision", "tipo_swap"})
        for k in r["pendientes"]:
            self.assertEqual(r["fila_pdf"][k], tabla.PEND)
            fuente = [f for f in r["detalle"] if f["campo"] == k][0]["fuente"]
            self.assertTrue(fuente["motivo"])

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
        # El instantáneo es solo informativo: si falla, Default Spread no cambia
        r = preparar("EURUSD", fallos=["https://widgets.fxbluelabs.com"])
        self.assertEqual((r["estado"], r["tabla"]["spread"]), ("COMPLETA", "0.42"))
        self.assertNotIn("spread_instantaneo", r["tabla"])
        self.assertTrue(any("spread instantáneo" in a for a in r["avisos"]))
        self.assertIn("fallo", [c["estado"] for c in r["consultas"]])

    def test_feed_sin_datos_del_simbolo(self):
        sin = b'{"symbols":[{"symbol":"EURUSD","noData":true}]}'
        r = preparar("EURUSD", sustituir={"https://widgets.fxbluelabs.com": sin})
        self.assertEqual(r["estado"], "COMPLETA")
        self.assertNotIn("spread_instantaneo", r["tabla"])

    def test_bce_caido(self):
        r = preparar("EURUSD", fallos=[URL_BCE])
        self.assertEqual(r["pendientes"], ["comision"])  # EUR → USD; el resto va en USD
        r = preparar("GDAXI", fallos=[URL_BCE])
        self.assertEqual(set(r["pendientes"]), {"point_value", "comision", "swap_largo", "swap_corto",
                                                "tipo_swap"})

    def test_bce_no_hace_falta_en_usd(self):
        r = preparar("XAUUSD", fallos=[URL_BCE])
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
        p.leer_spread_instantaneo()
        self.assertTrue(any("Mercado cerrado" in a for a in p.avisos))

    def test_detalle_distingue_origenes(self):
        r = preparar("EURUSD")
        tipos = {f["campo"]: f["tipo"] for f in r["detalle"]}
        self.assertEqual((tipos["spread"], tipos["spread_instantaneo"]), ("promedio", "observado"))
        self.assertEqual(tipos["comision"], "calculo")
        self.assertEqual(tipos["tipo"], "regla")
        self.assertEqual(tipos["swap_largo"], "dato")
        for k in tabla.AJUSTES:
            self.assertEqual(tipos[k], "ajuste")
        self.assertEqual(r["perfil"]["divisa_cuenta"], "USD")
        self.assertEqual(r["fila_pdf"]["rollover"], PERFIL.ajustes["rollover"])


if __name__ == "__main__":
    unittest.main()
