"""Pruebas de scripts/tabla.py (solo biblioteca estándar).

    python3 -m unittest discover -s tests -v

Las pruebas que imprimen un PDF real necesitan Chrome, Edge, Chromium o Brave; si no hay
ninguno se marcan como omitidas (skipped), no como superadas.
"""
import copy
import datetime as dt
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
import unittest.mock
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SK / "scripts"))
import tabla  # noqa: E402

EJEMPLOS = SK / "examples"
SCRIPT = SK / "scripts" / "tabla.py"


def ejemplo(nombre):
    return json.loads((EJEMPLOS / f"{nombre}.json").read_text(encoding="utf-8"))


def perfil(**cambios):
    d = json.loads(tabla.PERFIL_DEFECTO.read_text(encoding="utf-8"))
    d["ajustes_personales"].update(cambios)
    return d


PERFIL = tabla.Perfil(perfil(), tabla.PERFIL_DEFECTO)


def errores(d, p=PERFIL):
    return tabla.validar(d, p).errores


def hay_navegador():
    try:
        tabla.encontrar_navegador()
        return True
    except tabla.ErrorUso:
        return False


class TestCasosCorrectos(unittest.TestCase):
    def test_ejemplos_completos(self):
        for s in ("EURUSD", "XAUUSD"):
            r = tabla.validar(ejemplo(s), PERFIL)
            self.assertEqual(r.estado, "COMPLETA", (s, r.errores, r.avisos))

    def test_indice_sin_spread_medio_queda_pendiente(self):
        # Forex Benchmark no publica índices: Default Spread pendiente, con alternativas
        r = tabla.validar(ejemplo("NDX"), PERFIL)
        self.assertEqual((r.estado, r.pendientes, r.errores), ("INCOMPLETA", ["spread"], []))
        motivo = ejemplo("NDX")["fuentes"]["spread"]["motivo"]
        self.assertIn("Forex Benchmark no publica", motivo)
        self.assertIn("Alternativas, sin aplicar", motivo)

    def test_swaps_admiten_ambos_signos(self):
        d = ejemplo("NDX")
        d["swap_largo"], d["swap_corto"] = "12.5", "-0.01"
        self.assertEqual(errores(d), [])

    def test_spread_cero_es_valido(self):
        d = ejemplo("EURUSD")
        d["spread"], d["fuentes"]["spread"]["lectura"] = "0", "0"
        self.assertEqual(errores(d), [])

    def test_spread_medio_con_mas_decimales_que_la_casilla(self):
        d = ejemplo("EURUSD")
        d["fuentes"]["spread"]["lectura"] = "0.4233"
        self.assertEqual(errores(d), [])

    def test_spread_medio_con_fecha_final_del_periodo(self):
        d = ejemplo("EURUSD")
        d["fuentes"]["spread"]["datos_hasta"] = "2026-11-26"
        self.assertEqual(errores(d), [])
        self.assertIn("30 días hasta el 2026-11-26", tabla.lineas_spread(d)[0])

    def test_spread_instantaneo_en_puntos_de_mt5(self):
        d = ejemplo("NDX")  # MT5 muestra 11 puntos de 0.1 → 1.1 pips de 1
        d["fuentes"]["spread_instantaneo"].update(unidad="puntos", lectura="11", punto="0.1")
        self.assertEqual(errores(d), [])

    def test_spread_instantaneo_es_opcional(self):
        d = ejemplo("EURUSD")
        del d["spread_instantaneo"], d["fuentes"]["spread_instantaneo"]
        self.assertEqual(tabla.validar(d, PERFIL).estado, "COMPLETA")

    def test_perfil_predeterminado(self):
        p = tabla.cargar_perfil(str(tabla.PERFIL_DEFECTO))
        self.assertEqual(p.ajustes, {"slippage": "0", "min_dist": "0", "order_mult": "1",
                                     "order_step": "0.01", "rollover": "23:59"})
        self.assertEqual((p.d["broker"], p.d["plataforma"], p.d["divisa_cuenta"]), ("Darwinex", "MT5", "USD"))
        self.assertEqual(p.d["datos"]["zona_clon"], "(EST+07) New York Trading hours, US DST")


class TestPendientes(unittest.TestCase):
    def test_tabla_incompleta(self):
        r = tabla.validar(ejemplo("BTCUSD"), PERFIL)
        self.assertEqual(r.estado, "INCOMPLETA")
        self.assertIn("comision", r.pendientes)

    def test_pendiente_sin_motivo(self):
        d = ejemplo("BTCUSD")
        d["fuentes"]["comision"] = {"tipo": "pendiente"}
        self.assertTrue(any("motivo" in e for e in errores(d)))

    def test_valor_pendiente_con_fuente_no_pendiente(self):
        d = ejemplo("EURUSD")
        d["swap_largo"] = "PENDIENTE DE VERIFICAR"
        self.assertTrue(any("PENDIENTE DE VERIFICAR va con una fuente" in e for e in errores(d)))

    def test_fuente_pendiente_con_valor(self):
        d = ejemplo("EURUSD")
        d["fuentes"]["swap_largo"] = {"tipo": "pendiente", "motivo": "x"}
        self.assertTrue(any("PENDIENTE DE VERIFICAR va con una fuente" in e for e in errores(d)))

    def test_spread_pendiente(self):
        d = ejemplo("EURUSD")
        d["spread"] = "PENDIENTE DE VERIFICAR"
        d["fuentes"]["spread"] = {"tipo": "pendiente", "motivo": "feed y web sin respuesta"}
        self.assertEqual(tabla.validar(d, PERFIL).estado, "INCOMPLETA")

    def test_html_marca_incompleta(self):
        h = tabla.html_doc([tabla.fila_pdf(ejemplo("BTCUSD"), PERFIL)], ["BTCUSD"])
        self.assertIn("TABLA INCOMPLETA", h)
        self.assertIn('class="cen pend"', h)
        self.assertIn(tabla.CREDITO, h)
        self.assertIn("BTCUSD: Default Spread PENDIENTE DE VERIFICAR", h)

    def test_html_identifica_el_spread(self):
        h = tabla.html_doc([tabla.fila_pdf(ejemplo("EURUSD"), PERFIL)])
        self.assertIn(tabla.ETIQUETA_SPREAD, h)
        self.assertIn("EURUSD: 0.42 pips", h)
        self.assertIn("consultado el 2026-11-27 01:22 UTC", h)
        self.assertIn("Forex Benchmark no indica la fecha final", h)  # periodo ≠ fecha de consulta
        self.assertIn("spread instantáneo observado en Darwinex 0.4 pips", h)
        self.assertIn("no se suman al spread", h)


class TestNumeros(unittest.TestCase):
    def caso(self, campo, valor, texto):
        d = ejemplo("NDX")
        d[campo] = valor
        self.assertTrue(any(texto in e for e in errores(d)), (campo, valor, errores(d)))

    def test_positivos(self):
        for campo in ("pip_tick", "no_pip_tick", "point_value"):
            self.caso(campo, "-1", "mayor que 0")
            self.caso(campo, "0", "mayor que 0")

    def test_no_negativos(self):
        self.caso("spread", "-1.1", "no puede ser negativo")
        self.caso("comision", "-5.50", "no puede ser negativo")

    def test_formato(self):
        self.caso("pip_tick", "0,01", "punto decimal")
        self.caso("point_value", "100,000", "punto decimal")
        self.caso("spread", "1.1 pips", "punto decimal")
        self.caso("spread", "NaN", "punto decimal")
        self.caso("pip_tick", "1 aprox.", "no admite « aprox.»")

    def test_tipos_json(self):
        self.caso("spread", 1.1, "texto entre comillas")
        self.caso("pip_tick", None, "texto entre comillas")
        self.caso("tipo", ["Index"], "texto entre comillas")

    def test_texto_no_basta(self):
        """Una tabla con texto en todos los campos no es completa si el texto no es válido."""
        d = ejemplo("NDX")
        for k in tabla.CAMPOS:
            d[k] = "consultado"
        r = tabla.validar(d, PERFIL)
        self.assertEqual(r.estado, "NO VÁLIDA")
        self.assertGreaterEqual(len(r.errores), 10)

    def test_vacio(self):
        self.caso("swap_corto", "  ", "vacío")

    def test_valores_cerrados(self):
        self.caso("tipo", "Indice", "«tipo»")
        self.caso("modelo_comision", "Per trade", "modelo_comision")
        self.caso("triple_swap", "Friday", "triple_swap")


class TestFechas(unittest.TestCase):
    def test_fechas_imposibles(self):
        for v in ("2026-02-30", "2026-13-01", "2026-00-10", "27/10/2026", "", 20261027):
            d = ejemplo("NDX")
            d["consulta"] = v
            self.assertTrue(any("«consulta»" in e for e in errores(d)), v)

    def test_fecha_futura(self):
        d = ejemplo("NDX")
        d["consulta"] = (dt.date.today() + dt.timedelta(days=30)).isoformat()
        self.assertTrue(any("futura" in e for e in errores(d)))

    def test_fecha_de_fuente_imposible(self):
        d = ejemplo("NDX")
        d["fuentes"]["swap_largo"]["fecha"] = "2026-02-29"
        self.assertTrue(any("no es una fecha que exista" in e for e in errores(d)))

    def test_fuente_posterior_a_consulta(self):
        d = ejemplo("NDX")
        d["consulta"] = "2026-10-26"
        self.assertTrue(any("posterior a «consulta»" in e for e in errores(d)))

    def test_horas_imposibles(self):
        for v in ("25:00", "23:60", "8:18", "08.18", None):
            for s, campo in (("NDX", "spread_instantaneo"), ("EURUSD", "spread")):
                d = ejemplo(s)
                d["fuentes"][campo]["hora_utc"] = v
                self.assertTrue(any("hora_utc" in e for e in errores(d)), (campo, v))


class TestFuentes(unittest.TestCase):
    def test_dato_sin_fecha_ni_url(self):
        d = ejemplo("NDX")
        d["fuentes"]["swap_largo"] = {"tipo": "dato"}
        e = errores(d)
        self.assertTrue(any("swap_largo.url" in x for x in e))
        self.assertTrue(any("swap_largo.fecha" in x for x in e))

    def test_fuente_texto_libre(self):
        d = ejemplo("NDX")
        d["fuentes"]["swap_largo"] = "darwinex.com 2026-10-27"
        self.assertTrue(any("debe ser un objeto" in x for x in errores(d)))

    def test_spread_instantaneo_sin_hora_ni_unidad(self):
        d = ejemplo("NDX")
        del d["fuentes"]["spread_instantaneo"]["hora_utc"]
        del d["fuentes"]["spread_instantaneo"]["unidad"]
        e = errores(d)
        self.assertTrue(any("hora_utc" in x for x in e))
        self.assertTrue(any("unidad" in x for x in e))

    def test_spread_no_es_un_dato(self):
        d = ejemplo("EURUSD")
        d["fuentes"]["spread"] = {"tipo": "dato", "url": "x", "fecha": "2026-10-27"}
        self.assertTrue(any("spread medio («promedio»" in x for x in errores(d)))

    def test_lectura_instantanea_no_vale_como_default_spread(self):
        d = ejemplo("EURUSD")
        d["spread"] = d["spread_instantaneo"]
        d["fuentes"]["spread"] = d["fuentes"]["spread_instantaneo"]
        self.assertTrue(any("no una lectura instantánea" in x for x in errores(d)))

    def test_criterio_de_la_academia(self):
        for clave, valor in (("periodo_dias", "7"), ("franja", "Day"), ("comision", "incluida"),
                             ("broker", "IC Markets (Raw)"), ("unidad", "puntos")):
            d = ejemplo("EURUSD")
            d["fuentes"]["spread"][clave] = valor
            self.assertTrue(any(f"spread.{clave}" in x and "criterio de la academia" in x
                                for x in errores(d)), clave)
        d = ejemplo("EURUSD")
        d["fuentes"]["spread"]["fuente"] = "Myfxbook"
        self.assertTrue(any("spread.fuente" in x and tabla.FUENTE_MUESTREO in x for x in errores(d)))
        d = ejemplo("EURUSD")
        d["fuentes"]["spread"]["url"] = "https://www.myfxbook.com/forex-broker-spreads"
        self.assertTrue(any("spread.url" in x for x in errores(d)))

    def test_spread_medio_de_simbolo_sin_cobertura(self):
        d = ejemplo("NDX")
        d["spread"] = "1.2"
        d["fuentes"]["spread"] = dict(ejemplo("EURUSD")["fuentes"]["spread"], lectura="1.2",
                                      pip_fuente="1", fecha="2026-10-27")
        self.assertTrue(any("Forex Benchmark no publica" in x for x in errores(d)))

    def test_unidad_de_forex_benchmark_sin_comprobar(self):
        # XAGUSD comprobado el 2026-11-28 contra bid/ask de Darwinex: pips de 0.01
        self.assertEqual(tabla.pip_forex_benchmark("XAGUSD"), tabla.Decimal("0.01"))
        self.assertIsNone(tabla.pip_forex_benchmark("USDMXN"))
        self.assertIn("no está comprobada", tabla.motivo_sin_spread_medio("USDMXN"))
        self.assertEqual(tabla.pip_forex_benchmark("gbpjpy"), tabla.Decimal("0.01"))

    def test_pip_de_forex_benchmark_equivocado(self):
        d = ejemplo("XAUUSD")
        d["fuentes"]["spread"]["pip_fuente"] = "0.1"
        self.assertTrue(any("pip_fuente" in x for x in errores(d)))

    def test_fecha_final_del_periodo(self):
        d = ejemplo("EURUSD")
        d["fuentes"]["spread"]["datos_hasta"] = "2026-11-28"
        self.assertTrue(any("datos_hasta" in x for x in errores(d)))
        d["fuentes"]["spread"]["datos_hasta"] = "2026-11-01"
        self.assertTrue(any("termina el 2026-11-01" in x for x in tabla.validar(d, PERFIL).avisos))

    def test_aviso_si_medio_e_instantaneo_no_se_parecen(self):
        d = ejemplo("EURUSD")
        d["spread"], d["fuentes"]["spread"]["lectura"] = "4.2", "4.2"  # coma mal copiada
        r = tabla.validar(d, PERFIL)
        self.assertEqual(r.errores, [])
        self.assertTrue(any("se diferencian más de" in a for a in r.avisos))

    def test_spread_instantaneo_sin_fuente(self):
        d = ejemplo("EURUSD")
        del d["fuentes"]["spread_instantaneo"]
        self.assertTrue(any("spread_instantaneo" in x for x in errores(d)))

    def test_calculo_sin_formula_ni_entradas(self):
        d = ejemplo("NDX")
        d["fuentes"]["point_value"] = {"tipo": "calculo"}
        e = errores(d)
        self.assertTrue(any("formula" in x for x in e))
        self.assertTrue(any("entradas" in x for x in e))

    def test_entrada_sin_fuente(self):
        d = ejemplo("NDX")
        d["fuentes"]["point_value"]["entradas"] = [{"nombre": "contrato", "valor": "10"}]
        self.assertTrue(any("falta la fuente" in x for x in errores(d)))

    def test_regla_sin_referencia(self):
        d = ejemplo("NDX")
        d["fuentes"]["tipo"] = {"tipo": "regla", "regla": "índices = Index"}
        self.assertTrue(any("referencia" in x for x in errores(d)))

    def test_falta_fuentes(self):
        d = ejemplo("NDX")
        del d["fuentes"]
        self.assertTrue(any("«fuentes»" in x for x in errores(d)))

    def test_tipo_de_fuente_desconocido(self):
        d = ejemplo("NDX")
        d["fuentes"]["swap_corto"]["tipo"] = "supuesto"
        self.assertTrue(any("no válido" in x for x in errores(d)))


class TestCoherencia(unittest.TestCase):
    def test_comision_no_duplicada(self):
        d = ejemplo("NDX")
        d["comision"] = "2.75"  # se puso la comisión por orden sin pasarla a ida y vuelta
        self.assertTrue(any("× 2" in e for e in errores(d)))

    def test_comision_como_dato_directo(self):
        d = ejemplo("NDX")
        d["fuentes"]["comision"] = {"tipo": "dato", "url": "x", "fecha": "2026-10-27"}
        self.assertTrue(any("ida y vuelta" in e for e in errores(d)))

    def test_comision_sin_entrada_por_orden(self):
        d = ejemplo("NDX")
        d["fuentes"]["comision"]["entradas"][0]["nombre"] = "comision"
        self.assertTrue(any("comision_por_orden" in e for e in errores(d)))

    def test_spread_mal_convertido(self):
        d = ejemplo("XAUUSD")
        d["spread"] = "0.48"  # 48.23 pips de 0.01 escritos como precio
        self.assertTrue(any("no cuadra con Forex Benchmark" in e for e in errores(d)))
        d = ejemplo("XAUUSD")
        d["spread_instantaneo"] = "0.44"  # lectura en precio sin pasar a pips de 0.01
        self.assertTrue(any("spread instantáneo 0.44 no cuadra" in e for e in errores(d)))

    def test_tick_real_no_cuadra(self):
        d = ejemplo("NDX")
        d["no_pip_tick"] = "0.01"
        self.assertTrue(any("tick_value" in e for e in errores(d)))

    def test_point_value_no_cuadra(self):
        d = ejemplo("NDX")
        d["point_value"] = "100"
        self.assertTrue(any("Point Value" in e for e in errores(d)))

    def test_forex_sin_division_entre_10_avisa(self):
        d = ejemplo("EURUSD")
        d["no_pip_tick"] = "0.0001"
        self.assertTrue(any("÷ 10" in a for a in tabla.validar(d, PERFIL).avisos))

    def test_division_entre_10_fuera_de_forex_avisa(self):
        d = ejemplo("NDX")
        d["fuentes"]["no_pip_tick"] = {"tipo": "regla", "regla": "Pip/Tick ÷ 10", "referencia": "x"}
        self.assertTrue(any("tick real" in a for a in tabla.validar(d, PERFIL).avisos))

    def test_ajuste_personal_distinto_en_la_tabla(self):
        d = ejemplo("NDX")
        d["slippage"] = "2"
        self.assertTrue(any("ajuste personal" in e for e in errores(d)))


class TestPerfil(unittest.TestCase):
    def test_perfil_valido_de_otro_usuario(self):
        self.assertEqual(tabla.validar_perfil(perfil(slippage="1.5", order_step="0.1", rollover="00:00")), [])

    def test_perfil_invalido(self):
        casos = {"order_step": "0", "order_mult": "-1", "slippage": "-0.5", "min_dist": "x",
                 "rollover": "24:00"}
        for k, v in casos.items():
            self.assertTrue(tabla.validar_perfil(perfil(**{k: v})), k)
        d = perfil()
        d["broker"] = "OANDA"
        self.assertTrue(tabla.validar_perfil(d))

    def test_ajustes_del_perfil_llegan_al_pdf(self):
        p = tabla.Perfil(perfil(slippage="1", rollover="23:00"), tabla.PERFIL_DEFECTO)
        fila = tabla.fila_pdf(ejemplo("NDX"), p)
        self.assertEqual((fila["slippage"], fila["rollover"]), ("1", "23:00"))


class TestRutas(unittest.TestCase):
    def test_simbolos_peligrosos(self):
        for s in ("../../etc/passwd", "a/b", "a\\b", "..", "DAX / GDAXI", "", "CON", "x" * 41, "A..B"):
            with self.assertRaises(tabla.ErrorUso, msg=s):
                tabla.clave_segura(s)

    def test_simbolos_validos(self):
        for s in ("eurusd", "USATECHIDXUSD", "DAX_GDAXI", "BRK.B", "US-500"):
            self.assertTrue(tabla.clave_segura(s))

    def test_ruta_json_dentro_de_datos(self):
        p, clave = tabla.ruta_json("eurusd")
        self.assertEqual((p.name, clave), ("EURUSD.json", "EURUSD"))
        self.assertEqual(p.parent, tabla.tablas_dir())

    def test_dentro(self):
        base = Path(tempfile.gettempdir())
        with self.assertRaises(tabla.ErrorUso):
            tabla.dentro(base / "a", base / "a" / ".." / "b.pdf")


class TestJsonDanado(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def leer(self, contenido, modo="w"):
        p = self.tmp / "X.json"
        if modo == "wb":
            p.write_bytes(contenido)
        else:
            p.write_text(contenido, encoding="utf-8")
        with self.assertRaises(tabla.ErrorUso) as c:
            tabla.leer_json(p)
        return str(c.exception)

    def test_mensajes_claros(self):
        self.assertIn("línea 1, columna", self.leer('{"simbolo": "EURUSD",'))
        self.assertIn("vacío", self.leer(""))
        self.assertIn("objeto JSON", self.leer("[1, 2]"))
        self.assertIn("UTF-8", self.leer(b"\xff\xfe\x00{", "wb"))
        with self.assertRaises(tabla.ErrorUso):
            tabla.leer_json(self.tmp / "no-existe.json")

    def test_formato_v1_detectado(self):
        d = ejemplo("NDX")
        del d["esquema"]
        d["fuentes"] = {k: "texto libre" for k in tabla.CAMPOS}
        self.assertTrue(any("formato antiguo" in e for e in errores(d)))

    def test_raiz_no_objeto(self):
        self.assertEqual(tabla.validar([], PERFIL).estado, "NO VÁLIDA")


class TestNavegador(unittest.TestCase):
    def test_candidatos_por_sistema(self):
        mac = tabla.candidatos_navegador("Darwin", {}, "/Users/u")
        self.assertIn("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", mac)
        self.assertIn("/Users/u/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge", mac)
        win = tabla.candidatos_navegador("Windows", {"PROGRAMFILES": r"C:\Program Files",
                                                     "LOCALAPPDATA": r"C:\Users\u\AppData\Local"})
        self.assertIn(r"C:\Program Files\Google\Chrome\Application\chrome.exe", win)
        self.assertIn(r"C:\Users\u\AppData\Local\Microsoft\Edge\Application\msedge.exe", win)
        lin = tabla.candidatos_navegador("Linux", {})
        self.assertIn("/usr/bin/chromium", lin)
        self.assertIn("/usr/bin/google-chrome", lin)

    def test_ruta_manual_inexistente(self):
        with self.assertRaises(tabla.ErrorUso) as c:
            tabla.encontrar_navegador("/no/existe/chrome")
        self.assertIn("no existe", str(c.exception))

    def test_sin_navegador_mensaje_util(self):
        viejo = (tabla.candidatos_navegador, tabla.shutil.which, os.environ.pop("SQD_NAVEGADOR", None))
        tabla.candidatos_navegador = lambda: []
        tabla.shutil.which = lambda _: None
        try:
            with self.assertRaises(tabla.ErrorUso) as c:
                tabla.encontrar_navegador()
            self.assertIn("--navegador", str(c.exception))
        finally:
            tabla.candidatos_navegador, tabla.shutil.which = viejo[:2]
            if viejo[2]:
                os.environ["SQD_NAVEGADOR"] = viejo[2]


class TestPdf(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_comprobar_pdf(self):
        p = self.tmp / "x.pdf"
        self.assertIsNotNone(tabla.comprobar_pdf(p))
        p.write_bytes(b"<html>" + b"x" * 2000)
        self.assertIn("cabecera", tabla.comprobar_pdf(p))
        p.write_bytes(b"%PDF-1.4\n" + b"x" * 2000)
        self.assertIn("truncado", tabla.comprobar_pdf(p))
        p.write_bytes(b"%PDF-1.4\n" + b"x" * 2000 + b"\n%%EOF\n")
        self.assertIn("páginas", tabla.comprobar_pdf(p))

    @unittest.skipIf(os.name == "nt", "usa un script de shell como navegador falso")
    def test_navegador_que_no_genera_pdf_valido(self):
        falso = self.tmp / "falso.sh"
        falso.write_text('#!/bin/sh\nfor a in "$@"; do case "$a" in --print-to-pdf=*) '
                         'printf "no soy un pdf" > "${a#--print-to-pdf=}";; esac; done\n')
        falso.chmod(falso.stat().st_mode | stat.S_IEXEC)
        destino = self.tmp / "out.pdf"
        with self.assertRaises(tabla.ErrorUso) as c:
            tabla.imprimir_pdf("<p>x</p>", destino, str(falso))
        self.assertIn("no generó un PDF válido", str(c.exception))
        self.assertFalse(destino.exists(), "no debe quedar un PDF roto")

    @unittest.skipUnless(hay_navegador(), "no hay navegador Chromium instalado")
    def test_pdf_real(self):
        destino = self.tmp / "real.pdf"
        filas = [tabla.fila_pdf(ejemplo(s), PERFIL) for s in ("EURUSD", "BTCUSD")]
        tabla.imprimir_pdf(tabla.html_doc(filas, ["BTCUSD"]), destino, tabla.encontrar_navegador())
        self.assertIsNone(tabla.comprobar_pdf(destino))



def medias(**cambios):
    """medias.json de prueba (valores sintéticos, no medidos)."""
    hoy = dt.date.today()
    info = {"spread": "0.4234", "pip": "0.0001", "muestras": 2000, "min": "0.30", "max": "2.10",
            "desde": (hoy - dt.timedelta(days=29)).isoformat(), "hasta": hoy.isoformat()}
    info.update(cambios)
    return {"fuente": tabla.FUENTE_MUESTREO, "intervalo_min": 15, "inicio": info["desde"],
            "generado_utc": f"{hoy} 10:00", "simbolos": {"EURUSD": info}}


def con_muestreo(**cambios):
    d = ejemplo("EURUSD")
    ahora = dt.datetime.now(dt.timezone.utc)
    d["spread"], d["fuentes"]["spread"] = tabla.spread_desde_medias("EURUSD", medias(**cambios),
                                                                     "0.0001", ahora)
    d["consulta"] = d["creada"] = ahora.date().isoformat()
    return d


class TestSpreadAutomatico(unittest.TestCase):
    """Default Spread del muestreo automático de Darwinex (medias.json)."""

    def test_tabla_completa_sin_escribir_nada(self):
        d = con_muestreo()
        r = tabla.validar(d, PERFIL)
        self.assertEqual(r.errores, [])
        self.assertEqual(d["spread"], "0.42")
        f = d["fuentes"]["spread"]
        self.assertEqual((f["tipo"], f["fuente"], f["url"]),
                         ("promedio", tabla.FUENTE_MUESTREO, tabla.URL_DATOS_SPREAD))
        self.assertEqual(tabla.etiqueta_spread(f), tabla.ETIQUETA_MUESTREO)
        self.assertIn("2000 muestras", tabla.periodo_spread(f))

    def test_pocas_muestras_queda_pendiente(self):
        d = con_muestreo(muestras=10)
        self.assertEqual(d["spread"], tabla.PEND)
        self.assertIn("se rellena solo", d["fuentes"]["spread"]["motivo"])
        self.assertEqual(tabla.validar(d, PERFIL).errores, [])

    def test_simbolo_sin_datos_queda_pendiente(self):
        v, f = tabla.spread_desde_medias("NDX", medias(), "1", dt.datetime.now(dt.timezone.utc))
        self.assertEqual(v, tabla.PEND)
        self.assertIn("todavía no tiene datos de NDX", f["motivo"])

    def test_pip_distinto_no_se_mezcla(self):
        v, f = tabla.spread_desde_medias("EURUSD", medias(), "0.01", dt.datetime.now(dt.timezone.utc))
        self.assertEqual(v, tabla.PEND)
        self.assertIn("Pip/Tick Size", f["motivo"])

    def test_periodo_corto_avisa(self):
        hoy = dt.date.today()
        d = con_muestreo(desde=(hoy - dt.timedelta(days=2)).isoformat())
        r = tabla.validar(d, PERFIL)
        self.assertEqual(r.errores, [])
        self.assertTrue(any("cubre 3 días" in a for a in r.avisos))
        self.assertIn("llegará a 30 días sola", tabla.periodo_spread(d["fuentes"]["spread"]))

    def test_validacion_estricta(self):
        d = con_muestreo()
        d["fuentes"]["spread"]["muestras"] = "12"
        self.assertTrue(any("muestras" in x for x in errores(d)))
        d = con_muestreo()
        d["fuentes"]["spread"]["periodo_dias"] = "7"
        self.assertTrue(any("periodo_dias" in x for x in errores(d)))
        d = con_muestreo()
        d["fuentes"]["spread"]["url"] = "https://example.com/medias.json"
        self.assertTrue(any("spread.url" in x for x in errores(d)))
        d = con_muestreo()
        d["fuentes"]["spread"]["desde"] = "2020-01-01"
        self.assertTrue(any("pasa de 30 días" in x for x in errores(d)))
        d = con_muestreo()
        d["spread"] = "0.55"
        self.assertTrue(any("no cuadra con la media del muestreo" in x for x in errores(d)))
        d = con_muestreo()
        d["fuentes"]["spread"]["pip_fuente"] = "0.00001"
        self.assertTrue(any("pip_fuente" in x for x in errores(d)))

    def test_redondeo(self):
        self.assertEqual(tabla.redondear_spread("0.4234"), "0.42")
        self.assertEqual(tabla.redondear_spread("48.2351"), "48.24")
        self.assertEqual(tabla.redondear_spread("0.000312"), "0.00031")
        self.assertEqual(tabla.redondear_spread("0"), "0")

    def test_orden_spread(self):
        ruta = Path(tempfile.mkdtemp()) / "medias.json"
        ruta.write_text(json.dumps(medias()), encoding="utf-8")
        salida, err = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(err):
            codigo = tabla.main(["spread", "eurusd", "--url", ruta.as_uri()])
        self.assertEqual(codigo, 0, err.getvalue())
        d = json.loads(salida.getvalue())
        self.assertEqual(d["spread"], "0.42")
        self.assertEqual(d["fuentes"]["spread"]["fuente"], tabla.FUENTE_MUESTREO)
        with redirect_stdout(io.StringIO()), redirect_stderr(err):
            self.assertEqual(tabla.main(["spread", "NDX", "--url", ruta.as_uri()]), 1)
        shutil.rmtree(ruta.parent)


def con_cierre(antes=1, despues=1, **cambios):
    """medias.json con pocas muestras de EURUSD y su último spread antes del cierre; el cierre
    fue hace «antes» horas y reabre dentro de «despues» horas."""
    ahora = dt.datetime.now(dt.timezone.utc)
    m = medias(muestras=10)
    c = {"spread": "0.8", "pip": "0.0001", "bid": "1.1", "ask": "1.10008",
         "cierre_utc": (ahora - dt.timedelta(hours=antes)).strftime("%Y-%m-%d %H:%M"),
         "reabre_utc": (ahora + dt.timedelta(hours=despues)).strftime("%Y-%m-%d %H:%M")}
    c.update(cambios)
    m["cierres"] = {"EURUSD": c}
    return m, ahora


class TestSpreadMercadoCerrado(unittest.TestCase):
    """Mercado cerrado y media pendiente: último spread de la última sesión abierta."""

    def tabla_cierre(self, **kw):
        m, ahora = con_cierre(**kw)
        d = ejemplo("EURUSD")
        d["spread"], d["fuentes"]["spread"] = tabla.spread_desde_medias("EURUSD", m, "0.0001", ahora)
        d["consulta"] = d["creada"] = ahora.date().isoformat()
        return d

    def test_rellena_con_el_ultimo_spread(self):
        d = self.tabla_cierre()
        f = d["fuentes"]["spread"]
        self.assertEqual((d["spread"], f["tipo"], f["lectura"]), ("0.80", "cierre", "0.8"))
        r = tabla.validar(d, PERFIL)
        self.assertEqual((r.estado, r.errores), ("COMPLETA", []))
        self.assertTrue(any("provisional" in a for a in r.avisos))
        self.assertEqual(tabla.etiqueta_spread(f), tabla.ETIQUETA_CIERRE)
        self.assertIn("última cotización antes del cierre", tabla.lineas_spread(d)[0])

    def test_la_media_tiene_prioridad(self):
        m, ahora = con_cierre()
        m["simbolos"]["EURUSD"]["muestras"] = 2000
        v, f = tabla.spread_desde_medias("EURUSD", m, "0.0001", ahora)
        self.assertEqual((v, f["tipo"]), ("0.42", "promedio"))

    def test_mercado_ya_reabierto_queda_pendiente(self):
        m, ahora = con_cierre(antes=3, despues=-1)
        v, f = tabla.spread_desde_medias("EURUSD", m, "0.0001", ahora)
        self.assertEqual(v, tabla.PEND)
        self.assertIn("se rellena solo", f["motivo"])

    def test_pip_distinto_queda_pendiente(self):
        m, ahora = con_cierre()
        self.assertEqual(tabla.spread_desde_medias("EURUSD", m, "0.01", ahora)[0], tabla.PEND)

    def test_validacion(self):
        d = self.tabla_cierre()
        f = d["fuentes"]["spread"]
        momento = dt.datetime.strptime(f["reabre_utc"], "%Y-%m-%d %H:%M")
        if momento.date().isoformat() == f["fecha"]:  # misma fecha: consulta después de reabrir
            f["hora_utc"] = (momento + dt.timedelta(minutes=1)).strftime("%H:%M")
            self.assertTrue(any("ya reabierto" in x for x in errores(d)))
        d = self.tabla_cierre()
        d["spread"] = "0.55"
        self.assertTrue(any("no cuadra con el último spread" in x for x in errores(d)))
        d = self.tabla_cierre()
        d["fuentes"]["spread"]["reabre_utc"] = d["fuentes"]["spread"]["cierre_utc"]
        self.assertTrue(any("no es anterior a la reapertura" in x for x in errores(d)))
        d = self.tabla_cierre()
        d["fuentes"]["spread"]["comision"] = "incluida"
        self.assertTrue(any("spread.comision" in x for x in errores(d)))
        d = ejemplo("EURUSD")
        d["fuentes"]["swap_largo"] = dict(self.tabla_cierre()["fuentes"]["spread"])
        self.assertTrue(any("solo para Default Spread" in x for x in errores(d)))

    def test_orden_spread(self):
        m, _ = con_cierre()
        del m["simbolos"]["EURUSD"]  # aún sin ninguna muestra: el pip sale del cierre
        ruta = Path(tempfile.mkdtemp()) / "medias.json"
        ruta.write_text(json.dumps(m), encoding="utf-8")
        salida, err = io.StringIO(), io.StringIO()
        with redirect_stdout(salida), redirect_stderr(err):
            codigo = tabla.main(["spread", "EURUSD", "--url", ruta.as_uri()])
        shutil.rmtree(ruta.parent)
        self.assertEqual(codigo, 0, err.getvalue())
        self.assertEqual(json.loads(salida.getvalue())["fuentes"]["spread"]["tipo"], "cierre")
        self.assertIn("provisional", err.getvalue())


class TestCli(unittest.TestCase):
    """La herramienta completa, como la llama Claude."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        (self.tmp / "tablas").mkdir()
        for s in ("EURUSD", "NDX", "BTCUSD"):
            shutil.copy(EJEMPLOS / f"{s}.json", self.tmp / "tablas")
        self.env = dict(os.environ, SQD_DATA_DIR=str(self.tmp))
        self.env.pop("SQD_PERFIL", None)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-I", str(SCRIPT)] + list(args), env=self.env,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True,
                              encoding="utf-8")

    def test_validar_codigos(self):
        self.assertEqual(self.run_cli("validar", "EURUSD", "NDX").returncode, 0)
        r = self.run_cli("validar", "BTCUSD")
        self.assertEqual(r.returncode, 0)
        self.assertIn("TABLA INCOMPLETA", r.stdout)
        self.assertEqual(self.run_cli("validar", "--estricto", "BTCUSD").returncode, 1)

    def test_simbolo_con_ruta(self):
        r = self.run_cli("plantilla", "../../fuera")
        self.assertEqual(r.returncode, 2)
        self.assertIn("no válido para un nombre de archivo", r.stderr)
        self.assertFalse((self.tmp.parent / "FUERA.json").exists())

    def test_json_danado_por_cli(self):
        (self.tmp / "tablas" / "ROTO.json").write_text('{"simbolo": ', encoding="utf-8")
        r = self.run_cli("validar", "ROTO")
        self.assertEqual(r.returncode, 1)
        self.assertIn("no es un JSON válido", r.stdout)

    def test_plantilla_no_es_valida_hasta_rellenarla(self):
        self.assertEqual(self.run_cli("plantilla", "GBPUSD").returncode, 0)
        self.assertEqual(self.run_cli("plantilla", "GBPUSD").returncode, 2)  # ya existe
        r = self.run_cli("validar", "GBPUSD")
        self.assertEqual(r.returncode, 1)
        self.assertIn("NO VÁLIDA", r.stdout)

    def test_perfil_por_variable(self):
        p = self.tmp / "otro.json"
        p.write_text(json.dumps(perfil(slippage="1")), encoding="utf-8")
        self.env["SQD_PERFIL"] = str(p)
        r = self.run_cli("perfil")
        self.assertEqual(r.returncode, 0)
        self.assertIn("slippage 1", r.stdout)

    def test_perfil_danado(self):
        p = self.tmp / "malo.json"
        p.write_text(json.dumps(perfil(order_step="-0.01")), encoding="utf-8")
        r = self.run_cli("validar", "--perfil", str(p), "NDX")
        self.assertEqual(r.returncode, 2)
        self.assertIn("perfil no válido", r.stderr)

    def test_migrar_v1(self):
        v1 = copy.deepcopy(ejemplo("BTCUSD"))
        del v1["esquema"]
        v1["fuentes"] = {k: ("PENDIENTE DE VERIFICAR: sin datos" if tabla.es_pendiente(v1[k]) else
                             "Convención de la skill") for k in tabla.CAMPOS}
        v1["fuentes"]["nombre"] = "ticker en help.darwinex.com/assets-available (consultada 2026-10-27)"
        del v1["spread_instantaneo"]
        v1["spread"] = "11"
        v1["fuentes"]["spread"] = ("OBSERVADO: widgets.fxbluelabs.com/webwidgets/getPriceData.aspx: "
                                   "ask 79773.5 − bid 79762.5 = 11.0 USD, 2026-10-27 08:18 UTC")
        (self.tmp / "tablas" / "BTCUSD.json").write_text(json.dumps(v1), encoding="utf-8")
        r = self.run_cli("migrar", "BTCUSD")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("TABLA INCOMPLETA", r.stdout)
        self.assertTrue((self.tmp / "tablas" / "BTCUSD.json.v1").exists())
        d = json.loads((self.tmp / "tablas" / "BTCUSD.json").read_text(encoding="utf-8"))
        # la lectura instantánea no pasa a Default Spread
        self.assertEqual((d["esquema"], d["spread"], d["spread_instantaneo"]), (3, tabla.PEND, "11"))

    def test_migrar_v2_lectura_instantanea(self):
        v2 = ejemplo("EURUSD")
        v2["esquema"], v2["spread"] = 2, v2["spread_instantaneo"]
        v2["fuentes"]["spread"] = v2["fuentes"].pop("spread_instantaneo")
        del v2["spread_instantaneo"]
        p = self.tmp / "tablas" / "EURUSD.json"
        p.write_text(json.dumps(v2), encoding="utf-8")
        self.assertIn("esquema 2", self.run_cli("validar", "EURUSD").stdout)
        r = self.run_cli("migrar", "EURUSD")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        d = json.loads(p.read_text(encoding="utf-8"))
        self.assertEqual((d["spread"], d["spread_instantaneo"]), (tabla.PEND, "0.4"))
        self.assertIn("tabla.py spread EURUSD", d["fuentes"]["spread"]["motivo"])
        self.assertTrue((self.tmp / "tablas" / "EURUSD.json.v2").exists())

    @unittest.skipUnless(hay_navegador(), "no hay navegador Chromium instalado")
    def test_generar(self):
        r = self.run_cli("generar", "EURUSD", "BTCUSD")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        pdf = self.tmp / "tablas" / f"EURUSD_BTCUSD_Darwinex_2026-11-27_INCOMPLETA.pdf"
        self.assertIsNone(tabla.comprobar_pdf(pdf))
        self.assertIsNone(tabla.comprobar_pdf(self.tmp / "tablas" / "Tablas_Darwinex_todas.pdf"))

    def test_acumulado_guarda_copia_si_excluye_tablas(self):
        tablas = self.tmp / "tablas"
        anterior = tablas / "Tablas_Darwinex_todas.pdf"
        anterior.write_bytes(b"acumulado anterior")
        (tablas / "VIEJO.json").write_text('{"simbolo": "VIEJO"}', encoding="utf-8")  # no válido
        escritos = []
        original = tabla.imprimir_pdf
        tabla.imprimir_pdf = lambda html_text, destino, navegador: escritos.append(destino)
        try:
            with unittest.mock.patch.dict(os.environ, {"SQD_DATA_DIR": str(self.tmp)}), \
                    redirect_stdout(io.StringIO()) as out:
                tabla.generar_todas(PERFIL, "navegador")
        finally:
            tabla.imprimir_pdf = original
        copias = list(tablas.glob("Tablas_Darwinex_todas_anterior_*.pdf"))
        self.assertEqual(len(copias), 1, out.getvalue())
        self.assertEqual(copias[0].read_bytes(), b"acumulado anterior")
        self.assertEqual(escritos, [anterior])
        self.assertIn("excluidas", out.getvalue())

    def test_acumulado_sin_excluidas_no_copia(self):
        tablas = self.tmp / "tablas"
        (tablas / "Tablas_Darwinex_todas.pdf").write_bytes(b"x")
        original = tabla.imprimir_pdf
        tabla.imprimir_pdf = lambda *a: None
        try:
            with unittest.mock.patch.dict(os.environ, {"SQD_DATA_DIR": str(self.tmp)}), \
                    redirect_stdout(io.StringIO()):
                tabla.generar_todas(PERFIL, "navegador")
        finally:
            tabla.imprimir_pdf = original
        self.assertEqual(list(tablas.glob("*_anterior_*.pdf")), [])

    @unittest.skipUnless(hay_navegador(), "no hay navegador Chromium instalado")
    def test_generar_no_crea_pdf_si_hay_errores(self):
        d = ejemplo("NDX")
        d["pip_tick"] = "-1"
        (self.tmp / "tablas" / "NDX.json").write_text(json.dumps(d), encoding="utf-8")
        r = self.run_cli("generar", "NDX")
        self.assertEqual(r.returncode, 1)
        self.assertEqual(list((self.tmp / "tablas").glob("*.pdf")), [])


if __name__ == "__main__":
    unittest.main()
