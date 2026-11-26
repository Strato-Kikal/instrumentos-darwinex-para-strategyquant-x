#!/usr/bin/env python3
"""Tablas de configuración de símbolos para StrategyQuant X con Darwinex, en PDF.

El PDF lleva dos tablas:
  1. Configuración principal del instrumento
  2. Comisiones, swaps y rollover

Órdenes:
  tabla.py plantilla <SIMBOLO> [--forzar]   crea DATA/tablas/<SIMBOLO>.json para rellenar
  tabla.py validar <SIMBOLO|json> [...]     valida datos y fuentes (--estricto: incompleta = fallo)
  tabla.py generar <SIMBOLO|json> [...]     valida y genera UN PDF con todos los símbolos dados
                                            (una fila por símbolo) y actualiza el acumulado
  tabla.py todas                            regenera el PDF acumulado
  tabla.py migrar <SIMBOLO|json> [...]      pasa un JSON del formato antiguo (v1) al v2
  tabla.py perfil                           muestra el perfil activo y sus ajustes personales
  tabla.py navegador                        muestra el navegador que imprimirá el PDF
  tabla.py rutas

Opciones comunes: --perfil RUTA (o SQD_PERFIL), --navegador RUTA (o SQD_NAVEGADOR).
Carpeta de datos: SQD_DATA_DIR (por defecto ~/strategyquant-darwinex-datos).
Formato del JSON: reference/formato-json.md. Solo biblioteca estándar (Python 3.8+); el PDF
lo imprime un navegador Chromium (Chrome, Edge, Chromium o Brave).

Salida: 0 correcto · 1 tabla no válida (o incompleta con --estricto) · 2 error de uso o entorno.
"""
import argparse
import datetime as dt
import html
import json
import ntpath
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from decimal import Decimal, InvalidOperation
from pathlib import Path

SK = Path(__file__).resolve().parent.parent
PERFIL_DEFECTO = SK / "config" / "perfil.json"
ESQUEMA = 2

PEND = "PENDIENTE DE VERIFICAR"
TITULO = "Configuración de símbolos de StrategyQuant para Darwinex"
CREDITO = "Skill created by Kike Argandona"
TIPOS = {"Forex", "Index", "Forex / CFD", "Crypto / CFD"}
MODELOS = {"En función del tamaño", "Comisión en porcentaje"}
DIAS = {"MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY", "FRIDAY", "SATURDAY", "SUNDAY"}
# StrategyQuant aplica la comisión como ida y vuelta (round-turn) y Darwinex la publica por
# orden (2 órdenes por operación): comisión en SQ = comisión por orden × 2.
# Evidencia y alcance de la verificación: reference/verificacion-fuentes.md
FACTOR_IDA_VUELTA = Decimal(2)

CAMPOS = ["nombre", "tipo", "pip_tick", "point_value", "no_pip_tick", "spread",
          "modelo_comision", "comision", "swap_largo", "swap_corto", "triple_swap"]
AJUSTES = ["slippage", "min_dist", "order_mult", "order_step", "rollover"]
# campo: (signo admitido, admite « aprox.»)
NUMERICOS = {"pip_tick": (">0", False), "no_pip_tick": (">0", False), "point_value": (">0", True),
             "spread": (">=0", False), "comision": (">=0", True),
             "swap_largo": ("±", True), "swap_corto": ("±", True)}
SIGNO_AJUSTES = {"slippage": ">=0", "min_dist": ">=0", "order_mult": ">0", "order_step": ">0"}
TIPOS_FUENTE = {"dato", "observado", "calculo", "regla", "pendiente"}
UNIDADES_SPREAD = {"pips", "puntos", "precio"}
CLAVES_TABLA = {"esquema", "simbolo", "consulta", "creada", "fuentes", "notas"} | set(CAMPOS)
CLAVES_EXTRA_FUENTE = {"nota", "texto_v1"}

RE_NUM = re.compile(r"^-?\d+(\.\d+)?$")
RE_FECHA = re.compile(r"^\d{4}-\d{2}-\d{2}$")
RE_HORA = re.compile(r"^\d{2}:\d{2}$")
RE_CLAVE = re.compile(r"^[A-Z0-9][A-Z0-9._-]{0,39}$")
RESERVADOS_WIN = {"CON", "PRN", "AUX", "NUL"} | {f"{p}{n}" for p in ("COM", "LPT") for n in range(1, 10)}

# (clave JSON, cabecera, ancho relativo, alineación)
T1 = [("simbolo", "Símbolo", 205, "izq"), ("nombre", "Nombre recomendado", 292, "izq"),
      ("tipo", "Tipo", 146, "cen"), ("pip_tick", "Pip/Tick", 133, "cen"),
      ("point_value", "Point Value $", 176, "cen"), ("no_pip_tick", "No Pip/Tick", 150, "cen"),
      ("spread", "Spread", 184, "cen"), ("slippage", "Slippage", 125, "cen"),
      ("min_dist", "Min dist.", 103, "cen"), ("order_mult", "Order mult.", 125, "cen"),
      ("order_step", "Order step", 124, "cen")]
T2 = [("simbolo", "Símbolo", 240, "izq"), ("modelo_comision", "Modelo de comisión", 344, "izq"),
      ("comision", "Comisión a poner en SQ", 308, "cen"), ("swap_largo", "Swap largo", 327, "cen"),
      ("swap_corto", "Swap corto", 326, "cen"), ("triple_swap", "Triple swap", 240, "cen"),
      ("rollover", "Rollover", 172, "cen")]
# Posición y ancho de cada tabla en % del ancho de la página (A4 apaisado)
T1_IZQ, T1_ANCHO = 15.5, 69.7
T2_IZQ, T2_ANCHO = 10.8, 78.4


class ErrorUso(Exception):
    """Error de uso o de entorno: se informa con un mensaje claro y salida 2."""


def datos_dir():
    return Path(os.environ.get("SQD_DATA_DIR") or Path.home() / "strategyquant-darwinex-datos").expanduser()


def tablas_dir():
    return datos_dir() / "tablas"


def hoy():
    return dt.date.today()


# ---------------------------------------------------------------- utilidades de formato

def clave_segura(texto):
    """Clave de archivo de un símbolo: impide rutas fuera de la carpeta de datos."""
    c = str(texto).strip().upper()
    if not RE_CLAVE.match(c) or ".." in c or c.split(".")[0] in RESERVADOS_WIN:
        raise ErrorUso(f"símbolo «{texto}» no válido para un nombre de archivo: usa de 1 a 40 "
                       "letras, números, punto, guion o guion bajo, sin «/», «\\», «..» ni espacios")
    return c


def dentro(base, ruta):
    """Comprueba que ruta queda dentro de base (defensa adicional contra rutas fuera de DATA)."""
    try:
        ruta.resolve().relative_to(base.resolve())
    except ValueError:
        raise ErrorUso(f"la ruta {ruta} queda fuera de {base}")
    return ruta


def es_pendiente(v):
    return isinstance(v, str) and v.strip().upper() == PEND


def parse_num(v, signo, aprox_ok):
    """Devuelve (Decimal, aprox, error)."""
    if not isinstance(v, str):
        return None, False, f"debe ser texto entre comillas (p. ej. \"0.01\"), no {nombre_tipo(v)}"
    s = v.strip()
    aprox = s.endswith(" aprox.")
    if aprox:
        if not aprox_ok:
            return None, False, f"«{s}»: este campo no admite « aprox.» (no es una conversión de divisa)"
        s = s[: -len(" aprox.")]
    if not RE_NUM.match(s):
        return None, False, f"«{v}»: número con punto decimal y sin miles (p. ej. 0.01)"
    n = Decimal(s)
    if signo == ">0" and n <= 0:
        return None, False, f"«{v}»: debe ser mayor que 0"
    if signo == ">=0" and n < 0:
        return None, False, f"«{v}»: no puede ser negativo"
    return n, aprox, None


def nombre_tipo(v):
    return {dict: "un objeto", list: "una lista", bool: "un booleano", int: "un número",
            float: "un número", type(None): "null"}.get(type(v), type(v).__name__)


def fecha_real(v):
    """Devuelve (date, error). Rechaza fechas que no existen y fechas futuras."""
    if not isinstance(v, str) or not RE_FECHA.match(v.strip()):
        return None, f"«{v}» no es una fecha AAAA-MM-DD"
    try:
        f = dt.date.fromisoformat(v.strip())
    except ValueError:
        return None, f"«{v}» no es una fecha que exista"
    if f > hoy() + dt.timedelta(days=1):
        return None, f"«{v}» es una fecha futura"
    return f, None


def hora_real(v):
    if not isinstance(v, str) or not RE_HORA.match(v.strip()):
        return f"«{v}» no es una hora HH:MM"
    try:
        dt.datetime.strptime(v.strip(), "%H:%M")
    except ValueError:
        return f"«{v}» no es una hora que exista (00:00 a 23:59)"
    return None


def texto_ok(v):
    return isinstance(v, str) and v.strip() != ""


def decimales(n):
    return max(0, -n.as_tuple().exponent)


def casi_igual(esperado, valor):
    """Igualdad con la precisión con la que está escrito el valor."""
    tol = Decimal(1).scaleb(-decimales(valor)) / 2
    return abs(esperado - valor) <= tol


# ---------------------------------------------------------------- lectura de JSON

def leer_json(p, que="la tabla"):
    try:
        texto = Path(p).read_text(encoding="utf-8-sig")
    except FileNotFoundError:
        raise ErrorUso(f"no existe {p}")
    except IsADirectoryError:
        raise ErrorUso(f"{p} es una carpeta, no un JSON")
    except UnicodeDecodeError:
        raise ErrorUso(f"{p} no está en UTF-8")
    except OSError as e:
        raise ErrorUso(f"no puedo leer {p}: {e.strerror}")
    if not texto.strip():
        raise ErrorUso(f"{p} está vacío")
    try:
        d = json.loads(texto)
    except json.JSONDecodeError as e:
        raise ErrorUso(f"{p} no es un JSON válido: {e.msg} (línea {e.lineno}, columna {e.colno}). "
                       "Revisa comas, comillas y llaves")
    if not isinstance(d, dict):
        raise ErrorUso(f"{p}: {que} debe ser un objeto JSON {{…}}, no {nombre_tipo(d)}")
    return d


def ruta_json(arg):
    """(ruta, clave) de un argumento: símbolo de DATA/tablas o ruta a un .json."""
    if str(arg).lower().endswith(".json"):
        p = Path(arg).expanduser()
        return p, clave_segura(p.stem)
    clave = clave_segura(arg)
    return tablas_dir() / f"{clave}.json", clave


# ---------------------------------------------------------------- perfil

class Perfil:
    def __init__(self, d, ruta):
        self.d, self.ruta = d, ruta
        self.ajustes = d["ajustes_personales"]
        self.broker = d["broker"]


def ruta_perfil(arg=None):
    if arg:
        return Path(arg).expanduser(), "--perfil"
    if os.environ.get("SQD_PERFIL"):
        return Path(os.environ["SQD_PERFIL"]).expanduser(), "SQD_PERFIL"
    propio = datos_dir() / "perfil.json"
    if propio.exists():
        return propio, "DATA/perfil.json"
    return PERFIL_DEFECTO, "predeterminado"


def validar_perfil(d):
    e = []
    if d.get("broker") != "Darwinex":
        e.append(f"broker «{d.get('broker')}»: esta skill solo cubre Darwinex")
    if d.get("plataforma") not in ("MT4", "MT5"):
        e.append("plataforma debe ser MT4 o MT5")
    if d.get("divisa_cuenta") != "USD":
        e.append("divisa_cuenta: solo se admite USD (Point Value, comisión y swaps van en USD)")
    datos = d.get("datos")
    if not isinstance(datos, dict) or not all(texto_ok(datos.get(k)) for k in
                                              ("proveedor", "broker_profile_descarga", "zona_clon")):
        e.append("datos debe tener proveedor, broker_profile_descarga y zona_clon")
    if not texto_ok(d.get("sufijo_nombre", "x")):
        e.append("sufijo_nombre debe ser texto")
    aj = d.get("ajustes_personales")
    if not isinstance(aj, dict):
        return e + ["falta el objeto ajustes_personales"]
    for k in AJUSTES:
        if k not in aj:
            e.append(f"ajustes_personales.{k}: falta")
        elif k == "rollover":
            err = hora_real(aj[k])
            if err:
                e.append(f"ajustes_personales.rollover: {err}")
        else:
            _, _, err = parse_num(aj[k], SIGNO_AJUSTES[k], False)
            if err:
                e.append(f"ajustes_personales.{k}: {err}")
    return e


def cargar_perfil(arg=None):
    p, origen = ruta_perfil(arg)
    d = leer_json(p, "el perfil")
    errores = validar_perfil(d)
    if errores:
        raise ErrorUso(f"perfil no válido ({p}):\n  - " + "\n  - ".join(errores))
    perfil = Perfil(d, p)
    perfil.origen = origen
    return perfil


# ---------------------------------------------------------------- validación de una tabla

class Resultado:
    def __init__(self):
        self.errores, self.avisos, self.pendientes = [], [], []

    @property
    def estado(self):
        if self.errores:
            return "NO VÁLIDA"
        return "INCOMPLETA" if self.pendientes else "COMPLETA"


def validar_entrada(i, e, campo, consulta, r):
    pre = f"fuentes.{campo}.entradas[{i}]"
    if not isinstance(e, dict):
        r.errores.append(f"{pre}: debe ser un objeto con nombre, valor y fuente")
        return
    if not texto_ok(e.get("nombre")):
        r.errores.append(f"{pre}: falta «nombre»")
    if not texto_ok(e.get("valor")):
        r.errores.append(f"{pre}: falta «valor» (texto)")
    if "campo" in e:
        if e["campo"] not in CAMPOS or e["campo"] == campo:
            r.errores.append(f"{pre}: «campo» debe ser otro campo de la tabla ({', '.join(CAMPOS)})")
        return
    if not texto_ok(e.get("url")):
        r.errores.append(f"{pre}: falta la fuente («url») o «campo» si sale de otra casilla")
    validar_fecha_fuente(f"{pre}.fecha", e.get("fecha"), consulta, r)


def validar_fecha_fuente(pre, v, consulta, r):
    if v is None:
        r.errores.append(f"{pre}: falta la fecha de consulta")
        return None
    f, err = fecha_real(v)
    if err:
        r.errores.append(f"{pre}: {err}")
        return None
    if consulta and f > consulta:
        r.errores.append(f"{pre}: {v} es posterior a «consulta» ({consulta})")
    return f


def validar_fuente(campo, f, valor_pend, consulta, r):
    pre = f"fuentes.{campo}"
    if f is None:
        r.errores.append(f"{pre}: falta la fuente")
        return None
    if not isinstance(f, dict):
        r.errores.append(f"{pre}: debe ser un objeto con «tipo» (no {nombre_tipo(f)}); "
                         "ver reference/formato-json.md")
        return None
    tipo = f.get("tipo")
    if tipo not in TIPOS_FUENTE:
        r.errores.append(f"{pre}.tipo: «{tipo}» no válido; usa uno de {sorted(TIPOS_FUENTE)}")
        return None
    extra = set(f) - {"tipo", "url", "fecha", "hora_utc", "unidad", "lectura", "punto", "formula",
                      "entradas", "regla", "referencia", "motivo"} - CLAVES_EXTRA_FUENTE
    if extra:
        r.avisos.append(f"{pre}: claves desconocidas {sorted(extra)}")
    if valor_pend != (tipo == "pendiente"):
        r.errores.append(f"«{campo}»: el valor PENDIENTE DE VERIFICAR va con una fuente de tipo "
                         "«pendiente» (y al revés)")
    if tipo == "pendiente":
        if not texto_ok(f.get("motivo")):
            r.errores.append(f"{pre}.motivo: explica qué evidencia falta")
        return tipo
    if campo == "spread" and tipo != "observado":
        r.errores.append(f"{pre}: el spread debe ser una lectura real («observado») o «pendiente»")
        return None
    if tipo == "observado" and campo != "spread":
        r.errores.append(f"{pre}: «observado» es solo para el spread; usa «dato»")
        return None
    if tipo in ("dato", "observado"):
        if not texto_ok(f.get("url")):
            r.errores.append(f"{pre}.url: falta la fuente consultada")
        fecha = validar_fecha_fuente(f"{pre}.fecha", f.get("fecha"), consulta, r)
        if tipo == "observado":
            err = hora_real(f.get("hora_utc"))
            if err:
                r.errores.append(f"{pre}.hora_utc: {err}")
            if f.get("unidad") not in UNIDADES_SPREAD:
                r.errores.append(f"{pre}.unidad: «{f.get('unidad')}»; usa {sorted(UNIDADES_SPREAD)}")
            _, _, err = parse_num(f.get("lectura"), ">=0", False)
            if err:
                r.errores.append(f"{pre}.lectura (valor leído en la fuente): {err}")
            if fecha and consulta and fecha != consulta:
                r.avisos.append(f"spread leído el {fecha}, no el día de «consulta» ({consulta})")
    elif tipo == "calculo":
        if not texto_ok(f.get("formula")):
            r.errores.append(f"{pre}.formula: falta la fórmula")
        ent = f.get("entradas")
        if not isinstance(ent, list) or not ent:
            r.errores.append(f"{pre}.entradas: lista con cada entrada, su valor y su fuente")
        else:
            for i, e in enumerate(ent):
                validar_entrada(i, e, campo, consulta, r)
    elif tipo == "regla":
        if not texto_ok(f.get("regla")):
            r.errores.append(f"{pre}.regla: falta la regla aplicada")
        if not texto_ok(f.get("referencia")):
            r.errores.append(f"{pre}.referencia: falta de dónde sale la regla")
    return tipo


def entrada(f, nombre):
    if isinstance(f, dict) and isinstance(f.get("entradas"), list):
        for e in f["entradas"]:
            if isinstance(e, dict) and e.get("nombre") == nombre and isinstance(e.get("valor"), str):
                n, _, err = parse_num(e["valor"], "±", False)
                return n if not err else "no-num"
    return None


def validar(d, perfil):
    r = Resultado()
    if not isinstance(d, dict):
        r.errores.append("la tabla debe ser un objeto JSON")
        return r
    fu = d.get("fuentes")
    if d.get("esquema") != ESQUEMA:
        if isinstance(fu, dict) and any(isinstance(v, str) for v in fu.values()):
            r.errores.append("formato antiguo (v1): las fuentes son texto libre. Conviértelo con "
                             "«tabla.py migrar <SÍMBOLO>» y completa lo que indique")
            return r
        r.errores.append(f"«esquema» debe ser {ESQUEMA}")
    desconocidas = set(d) - CLAVES_TABLA - set(AJUSTES)
    if desconocidas:
        r.avisos.append(f"claves desconocidas (se ignoran): {sorted(desconocidas)}")

    s = d.get("simbolo")
    if not texto_ok(s):
        r.errores.append("«simbolo»: falta (texto)")
    elif len(s) > 40 or any(ord(c) < 32 for c in s):
        r.errores.append("«simbolo»: máximo 40 caracteres, sin saltos de línea")
    consulta = None
    for k in ("consulta", "creada"):
        f, err = fecha_real(d.get(k))
        if err:
            r.errores.append(f"«{k}»: {err}")
        elif k == "consulta":
            consulta = f
            dias = (hoy() - f).days
            if dias > 7:
                r.avisos.append(f"consulta de hace {dias} días: spread, swaps y tipos de cambio pueden "
                                "haber cambiado")

    for k in AJUSTES:
        if k in d and d[k] != perfil.ajustes[k]:
            r.errores.append(f"«{k}» = «{d[k]}» es un ajuste personal del perfil "
                             f"({perfil.ajustes[k]}); quítalo de la tabla o cambia el perfil")

    nums, aprox = {}, {}
    for k in CAMPOS:
        if k not in d:
            r.errores.append(f"«{k}»: falta")
            continue
        v = d[k]
        if not isinstance(v, str):
            r.errores.append(f"«{k}»: debe ser texto entre comillas, no {nombre_tipo(v)}")
            continue
        if not v.strip():
            r.errores.append(f"«{k}»: vacío (pon el valor o PENDIENTE DE VERIFICAR)")
            continue
        if es_pendiente(v):
            r.pendientes.append(k)
            continue
        if k in NUMERICOS:
            n, ap, err = parse_num(v, *NUMERICOS[k])
            if err:
                r.errores.append(f"«{k}»: {err}")
            else:
                nums[k], aprox[k] = n, ap
        elif k == "tipo" and v not in TIPOS:
            r.errores.append(f"«tipo» = «{v}»: usa uno de {sorted(TIPOS)}")
        elif k == "modelo_comision" and v not in MODELOS:
            r.errores.append(f"«modelo_comision» = «{v}»: usa uno de {sorted(MODELOS)}")
        elif k == "triple_swap" and v not in DIAS:
            r.errores.append(f"«triple_swap» = «{v}»: día en inglés y mayúsculas, {sorted(DIAS)}")
        elif k == "nombre" and not v.endswith(perfil.d.get("sufijo_nombre", "")):
            r.avisos.append(f"«nombre» = «{v}» no sigue la convención <ticker>{perfil.d.get('sufijo_nombre', '')}")

    tipos_fuente = {}
    if not isinstance(fu, dict):
        r.errores.append("«fuentes»: falta (objeto con una fuente por campo)")
        fu = {}
    else:
        for k in CAMPOS:
            if k in d:
                tipos_fuente[k] = validar_fuente(k, fu.get(k), es_pendiente(d[k]), consulta, r)
    notas = d.get("notas", [])
    if not isinstance(notas, list) or not all(isinstance(n, str) for n in notas):
        r.errores.append("«notas»: lista de textos")

    coherencia(d, fu, nums, aprox, tipos_fuente, r)
    return r


def coherencia(d, fu, nums, aprox, tipos_fuente, r):
    pip, tick = nums.get("pip_tick"), nums.get("no_pip_tick")
    if pip and tick:
        if tick > pip:
            r.avisos.append(f"No Pip/Tick ({tick}) mayor que Pip/Tick ({pip}): revisa el tick real")
        else:
            razon = pip / tick
            if razon != razon.to_integral_value() or str(int(razon)).strip("0") != "1":
                r.avisos.append(f"Pip/Tick ÷ No Pip/Tick = {razon}: lo normal es una potencia de 10")
        if d.get("tipo") == "Forex" and tick * 10 != pip:
            r.avisos.append("Forex en Darwinex cotiza con 5 decimales (3 en JPY): lo normal es "
                            "No Pip/Tick = Pip/Tick ÷ 10; confirma el tick real")
    f_tick = fu.get("no_pip_tick") if isinstance(fu, dict) else None
    if (d.get("tipo") not in ("Forex", None) and isinstance(f_tick, dict)
            and re.search(r"[÷/]\s*10\b", str(f_tick.get("formula", "")) + str(f_tick.get("regla", "")))):
        r.avisos.append("No Pip/Tick con «÷ 10» fuera de forex: usa el tick real del instrumento "
                        "(tick value ÷ contrato), no la regla del forex")

    # Spread: la lectura convertida debe dar el valor en pips de la tabla.
    f_sp = fu.get("spread") if isinstance(fu, dict) else None
    sp = nums.get("spread")
    if sp is not None and pip and tipos_fuente.get("spread") == "observado":
        lect, _, err = parse_num(f_sp.get("lectura"), ">=0", False)
        unidad = f_sp.get("unidad")
        if not err and unidad in UNIDADES_SPREAD:
            if unidad == "pips":
                esperado = lect
            elif unidad == "precio":
                esperado = lect / pip
            else:
                punto = f_sp.get("punto")
                if punto is None:
                    punto_n = tick
                    r.avisos.append("spread en puntos de MT5 sin «punto»: se supone punto = No Pip/Tick")
                else:
                    punto_n, _, err = parse_num(punto, ">0", False)
                    if err:
                        r.errores.append(f"fuentes.spread.punto: {err}")
                esperado = lect * punto_n / pip if punto_n else None
            if esperado is not None and not casi_igual(esperado, sp):
                r.errores.append(f"spread {sp} no cuadra con la lectura {lect} {unidad}: en pips de "
                                 f"{pip} da {esperado.normalize():f}")

    # Comisión: Darwinex publica por orden; SQ la aplica ida y vuelta.
    if "comision" in d and not es_pendiente(d["comision"]) and tipos_fuente.get("comision"):
        if tipos_fuente["comision"] != "calculo":
            r.errores.append("comisión: Darwinex la publica por orden y StrategyQuant la aplica ida y "
                             "vuelta; regístrala como «calculo» con la entrada «comision_por_orden»")
        else:
            cpo = entrada(fu["comision"], "comision_por_orden")
            if cpo is None:
                r.errores.append("fuentes.comision: falta la entrada «comision_por_orden»")
            elif cpo == "no-num":
                r.errores.append("fuentes.comision: «comision_por_orden» debe ser un número")
            elif "comision" in nums and not aprox.get("comision"):
                if not casi_igual(cpo * FACTOR_IDA_VUELTA, nums["comision"]):
                    r.errores.append(f"comisión {nums['comision']} ≠ comision_por_orden {cpo} × 2 "
                                     "(ida y vuelta)")

    # Point value sin conversión = contrato × 1 unidad de precio.
    pv = nums.get("point_value")
    if pv is not None and not aprox.get("point_value") and tipos_fuente.get("point_value") == "calculo":
        contrato = entrada(fu["point_value"], "contrato")
        if isinstance(contrato, Decimal) and contrato != pv:
            r.errores.append(f"Point Value {pv} ≠ contrato {contrato} (sin conversión debe coincidir)")
    # Tick real = tick value ÷ contrato (instrumentos cotizados en USD).
    if tick is not None and tipos_fuente.get("no_pip_tick") == "calculo":
        tv, ct = entrada(fu["no_pip_tick"], "tick_value"), entrada(fu["no_pip_tick"], "contrato")
        if isinstance(tv, Decimal) and isinstance(ct, Decimal) and ct > 0 and not aprox.get("point_value"):
            if not casi_igual(tv / ct, tick):
                r.errores.append(f"No Pip/Tick {tick} ≠ tick_value {tv} ÷ contrato {ct}")


# ---------------------------------------------------------------- informes

def cargar_tabla(arg, perfil):
    """(clave, datos, Resultado). Los errores de lectura se devuelven como tabla no válida."""
    try:
        p, clave = ruta_json(arg)
        d = leer_json(p)
    except ErrorUso as e:
        r = Resultado()
        r.errores.append(str(e))
        return None, None, r
    return clave, d, validar(d, perfil)


def informe(etiqueta, r):
    print(f"[{etiqueta}]")
    for e in r.errores:
        print(f"  ✗ {e}")
    for a in r.avisos:
        print(f"  ! {a}")
    if r.pendientes and not r.errores:
        print(f"  PENDIENTE DE VERIFICAR: {', '.join(r.pendientes)}")
    texto = {"NO VÁLIDA": "NO VÁLIDA",
             "INCOMPLETA": f"válida · TABLA INCOMPLETA ({len(r.pendientes)} datos PENDIENTE DE VERIFICAR)",
             "COMPLETA": "válida · TABLA COMPLETA (datos y fuentes comprobados)"}[r.estado]
    print(f"  RESULTADO: {texto}")


# ---------------------------------------------------------------- HTML y PDF

# Formato del PDF (líneas de tabla #7A93B2).
CSS = """
@page { size: A4 landscape; margin: 12mm 0; }
* { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
body { margin: 0; font-family: Arial, Helvetica, sans-serif; color: #000; }
.credito { position: fixed; bottom: 0; left: 0; right: 0; text-align: center;
           font-size: 7pt; font-style: italic; color: #7F7F7F; }
h1 { font-family: Arial, Helvetica, sans-serif; font-weight: bold; color: #2C4D76;
     font-size: 20pt; text-align: center; margin: 0 0 8mm 0; }
.incompleta { text-align: center; color: #9C0006; font-weight: bold; font-size: 10pt;
              margin: -5mm 8% 6mm 8%; padding: 1.5mm; border: 1px solid #9C0006; background: #FFE7E7; }
h2 { font-family: Calibri, Carlito, "Segoe UI", Arial, sans-serif; font-weight: bold;
     color: #2C4D76; font-size: 12pt; margin: 0 0 2mm 3.1%; }
.bloque { margin-bottom: 8mm; }
table { border-collapse: collapse; table-layout: fixed; font-size: 7pt; }
th { background: #2C4D76; color: #fff; font-weight: bold; text-align: center;
     border: 0.8px solid #7A93B2; padding: 3.2mm 1mm; overflow-wrap: anywhere; line-height: 1.15; }
td { border: 0.8px solid #7A93B2; padding: 1.05mm 1.2mm; line-height: 1.15; white-space: nowrap; }
tr:nth-child(odd) td { background: #F4F6FA; }
tr:nth-child(even) td { background: #FFFFFF; }
td.izq { text-align: left; }
td.cen { text-align: center; }
tr td.pend { background: #FFE7E7; color: #9C0006; font-weight: bold; white-space: normal; font-size: 6pt; }
"""


def tabla_html(datos, cols, izq, ancho):
    total = sum(c[2] for c in cols)
    colgroup = "".join(f'<col style="width:{c[2] / total * 100:.3f}%">' for c in cols)
    cab = "".join(f"<th>{html.escape(c[1])}</th>" for c in cols)
    filas = []
    for d in datos:
        celdas = []
        for k, _, _, al in cols:
            v = str(d.get(k, ""))
            clase = f"{al} pend" if es_pendiente(v) else al
            celdas.append(f'<td class="{clase}">{html.escape(v)}</td>')
        filas.append("<tr>" + "".join(celdas) + "</tr>")
    return (f'<table style="margin-left:{izq}%;width:{ancho}%"><colgroup>{colgroup}</colgroup>'
            f"<thead><tr>{cab}</tr></thead><tbody>{''.join(filas)}</tbody></table>")


def html_doc(datos, incompletas=()):
    aviso = ""
    if incompletas:
        aviso = ('<p class="incompleta">TABLA INCOMPLETA · Hay datos «PENDIENTE DE VERIFICAR» en: '
                 f"{html.escape(', '.join(incompletas))}. No uses esas filas en StrategyQuant hasta "
                 "completarlas.</p>")
    return f"""<!doctype html><html lang="es"><head><meta charset="utf-8"><title>{TITULO}</title><style>{CSS}</style></head><body>
<div class="credito">{CREDITO}</div>
<h1>{TITULO}</h1>{aviso}
<div class="bloque"><h2>1. Configuración principal del instrumento</h2>{tabla_html(datos, T1, T1_IZQ, T1_ANCHO)}</div>
<div class="bloque"><h2>2. Comisiones, swaps y rollover</h2>{tabla_html(datos, T2, T2_IZQ, T2_ANCHO)}</div>
</body></html>"""


EJECUTABLES = ["google-chrome", "google-chrome-stable", "chromium", "chromium-browser",
               "microsoft-edge", "microsoft-edge-stable", "brave-browser", "chrome", "msedge"]


def candidatos_navegador(sistema=None, entorno=None, home=None):
    """Rutas habituales de navegadores Chromium en macOS, Windows y Linux, por orden de preferencia."""
    sistema = sistema or platform.system()
    env = os.environ if entorno is None else entorno
    home = Path(home) if home else Path.home()
    rutas = []
    if sistema == "Darwin":
        apps = ["Google Chrome", "Chromium", "Microsoft Edge", "Brave Browser"]
        for base in ("/Applications", str(home / "Applications")):
            rutas += [f"{base}/{a}.app/Contents/MacOS/{a}" for a in apps]
    elif sistema == "Windows":
        rel = [r"Google\Chrome\Application\chrome.exe", r"Microsoft\Edge\Application\msedge.exe",
               r"Chromium\Application\chrome.exe", r"BraveSoftware\Brave-Browser\Application\brave.exe"]
        for var in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA"):
            base = env.get(var) or env.get(var.title())
            if base:
                rutas += [ntpath.join(base, r) for r in rel]
    else:
        rutas += [f"/usr/bin/{e}" for e in EJECUTABLES[:7]] + ["/snap/bin/chromium",
                                                               "/opt/google/chrome/chrome"]
    return rutas


def resolver_manual(ruta):
    p = Path(ruta).expanduser()
    if p.suffix == ".app" and p.is_dir():  # macOS: se admite el paquete .app
        macos = p / "Contents" / "MacOS"
        exe = macos / p.stem
        if not exe.exists() and macos.is_dir():
            exe = next((x for x in sorted(macos.iterdir()) if os.access(x, os.X_OK)), exe)
        p = exe
    if not p.is_file():
        raise ErrorUso(f"el navegador indicado no existe o no es un archivo: {p}")
    if not os.access(p, os.X_OK):
        raise ErrorUso(f"el navegador indicado no es ejecutable: {p}")
    return str(p)


def encontrar_navegador(manual=None):
    manual = manual or os.environ.get("SQD_NAVEGADOR")
    if manual:
        return resolver_manual(manual)
    for r in candidatos_navegador():
        if os.path.isfile(r) and os.access(r, os.X_OK):
            return r
    for e in EJECUTABLES:
        w = shutil.which(e)
        if w:
            return w
    raise ErrorUso(
        "no encuentro un navegador compatible para imprimir el PDF (Google Chrome, Microsoft Edge, "
        "Chromium o Brave).\n  Instala uno o indica su ruta con --navegador RUTA o la variable "
        "SQD_NAVEGADOR. Ejemplos:\n"
        "    macOS:   --navegador \"/Applications/Google Chrome.app\"\n"
        "    Windows: --navegador \"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe\"\n"
        "    Linux:   --navegador /usr/bin/chromium")


def comprobar_pdf(p):
    """None si p es un PDF completo con al menos una página; si no, el motivo."""
    p = Path(p)
    if not p.exists():
        return "no se creó el archivo"
    datos = p.read_bytes()
    if len(datos) < 800:
        return f"el archivo solo tiene {len(datos)} bytes"
    if not datos.startswith(b"%PDF-"):
        return "el archivo no empieza por la cabecera %PDF-"
    if b"%%EOF" not in datos[-2048:]:
        return "el PDF está truncado (falta %%EOF)"
    if not re.search(rb"/Type\s*/Page[^s]", datos):
        return "el PDF no tiene páginas"
    return None


def imprimir_pdf(html_text, destino, navegador, timeout=120):
    destino = Path(destino)
    destino.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        h = Path(tmp) / "tabla.html"
        h.write_text(html_text, encoding="utf-8")
        salida = Path(tmp) / "salida.pdf"
        args = ["--disable-gpu", "--no-first-run", "--no-default-browser-check",
                f"--user-data-dir={Path(tmp) / 'perfil-navegador'}", "--no-pdf-header-footer",
                "--print-to-pdf-no-header", f"--print-to-pdf={salida}"]
        if platform.system() == "Linux" and hasattr(os, "geteuid") and os.geteuid() == 0:
            args.append("--no-sandbox")  # Chromium no arranca como root sin esta opción
        motivo = ""
        for modo in ("--headless=new", "--headless"):  # el segundo, para navegadores antiguos
            try:
                r = subprocess.run([navegador, modo] + args + [h.as_uri()], stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, timeout=timeout)
            except subprocess.TimeoutExpired:
                motivo = f"el navegador tardó más de {timeout} s"
                continue
            except OSError as e:
                raise ErrorUso(f"no puedo ejecutar el navegador {navegador}: {e}")
            motivo = comprobar_pdf(salida)
            if motivo is None:
                temporal = destino.with_name(destino.name + ".tmp")
                shutil.copyfile(salida, temporal)
                os.replace(temporal, destino)
                return
            err = r.stderr.decode("utf-8", "replace").strip().splitlines()
            if err:
                motivo += f" (salida {r.returncode}: {err[-1][:200]})"
    raise ErrorUso(f"el navegador {navegador} no generó un PDF válido: {motivo}")


# ---------------------------------------------------------------- órdenes

def fila_pdf(d, perfil):
    fila = dict(d)
    fila.update(perfil.ajustes)
    return fila


def generar_todas(perfil, navegador):
    tablas = tablas_dir()
    filas, incompletas, excluidas = [], [], []
    for p in sorted(tablas.glob("*.json")):
        clave, d, r = cargar_tabla(str(p), perfil)
        if r.estado == "NO VÁLIDA":
            excluidas.append(f"{p.name} ({r.errores[0]})")
            continue
        filas.append((d.get("creada", d["consulta"]), clave, fila_pdf(d, perfil)))
        if r.pendientes:
            incompletas.append(d["simbolo"])
    for x in excluidas:
        print(f"  ! acumulado: se excluye {x}")
    if not filas:
        print("Acumulado: no hay tablas válidas; no se modifica")
        return
    destino = dentro(tablas, tablas / f"Tablas_{perfil.broker}_todas.pdf")
    if excluidas and destino.exists():
        # El acumulado nuevo pierde las tablas excluidas: guarda antes el anterior.
        marca = dt.datetime.now().strftime("%Y-%m-%d_%H%M%S")
        copia = dentro(tablas, tablas / f"Tablas_{perfil.broker}_todas_anterior_{marca}.pdf")
        shutil.copyfile(destino, copia)
        print(f"  ! acumulado: {len(excluidas)} tablas excluidas; copia del anterior en {copia}")
    imprimir_pdf(html_doc([f for *_, f in sorted(filas, key=lambda x: x[:2])], incompletas),
                 destino, navegador)
    estado = f", {len(incompletas)} INCOMPLETAS" if incompletas else ""
    print(f"Acumulado ({len(filas)} símbolos{estado}): {destino}")


def cmd_plantilla(a):
    tablas = tablas_dir()
    clave = clave_segura(a.simbolo)
    p = dentro(tablas, tablas / f"{clave}.json")
    if p.exists() and not a.forzar:
        raise ErrorUso(f"ya existe {p} (actualízalo, o usa --forzar para empezar de cero)")
    tablas.mkdir(parents=True, exist_ok=True)
    f = hoy().isoformat()
    d = {"esquema": ESQUEMA, "simbolo": clave, "consulta": f, "creada": f,
         **{k: "" for k in CAMPOS}, "fuentes": {k: {"tipo": ""} for k in CAMPOS}, "notas": []}
    p.write_text(json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(p)
    return 0


def cmd_validar(a):
    perfil = cargar_perfil(a.perfil)
    codigo = 0
    for s in a.simbolos:
        clave, _, r = cargar_tabla(s, perfil)
        informe(clave or s, r)
        if r.estado == "NO VÁLIDA" or (a.estricto and r.estado == "INCOMPLETA"):
            codigo = 1
    return codigo


def cmd_generar(a):
    """Un PDF con todos los símbolos pedidos, una fila por símbolo y en el orden pedido."""
    perfil = cargar_perfil(a.perfil)
    navegador = encontrar_navegador(a.navegador)
    filas, claves, fechas, incompletas, ok = [], [], [], [], True
    for s in a.simbolos:
        clave, d, r = cargar_tabla(s, perfil)
        informe(clave or s, r)
        if r.estado == "NO VÁLIDA":
            ok = False
            continue
        filas.append(fila_pdf(d, perfil))
        claves.append(clave)
        fechas.append(d["consulta"])
        if r.pendientes:
            incompletas.append(d["simbolo"])
    if not ok:
        print("No se genera el PDF: corrige las tablas NO VÁLIDAS.")
        return 1
    tablas = tablas_dir()
    base = "_".join(claves) if len(claves) <= 4 else f"{len(claves)}_simbolos"
    sufijo = "_INCOMPLETA" if incompletas else ""
    destino = dentro(tablas, tablas / f"{base}_{perfil.broker}_{max(fechas)}{sufijo}.pdf")
    imprimir_pdf(html_doc(filas, incompletas), destino, navegador)
    print(f"PDF: {destino}")
    if incompletas:
        print(f"  ATENCIÓN: TABLA INCOMPLETA ({', '.join(incompletas)}): hay datos PENDIENTE DE VERIFICAR")
    generar_todas(perfil, navegador)
    return 0


def cmd_todas(a):
    generar_todas(cargar_perfil(a.perfil), encontrar_navegador(a.navegador))
    return 0


RE_URL = re.compile(r"((?:https?://)?(?:[a-z0-9-]+\.)+[a-z]{2,}(?:/[^\s,;)«»]*)?)", re.I)
RE_FECHA_TXT = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
RE_HORA_TXT = re.compile(r"\b(\d{2}:\d{2}) UTC")


def migrar_fuente(campo, valor, texto):
    """Borrador v2 a partir del texto libre v1. Lo que no se deduce queda vacío para completarlo."""
    texto = texto.strip()
    url = (RE_URL.search(texto) or [None, ""])[1]
    fecha = (RE_FECHA_TXT.search(texto) or [None, ""])[1]
    if es_pendiente(valor):
        motivo = re.sub(r"^PENDIENTE DE VERIFICAR:?\s*", "", texto, flags=re.I)
        return {"tipo": "pendiente", "motivo": motivo or "falta evidencia (sin detalle en v1)"}
    if campo == "spread":
        f = {"tipo": "observado", "url": url, "fecha": fecha,
             "hora_utc": (RE_HORA_TXT.search(texto) or [None, ""])[1], "unidad": "", "lectura": ""}
        m = re.search(r"ask ([\d.]+) − bid ([\d.]+)", texto)
        if m:
            f["unidad"], f["lectura"] = "precio", format(Decimal(m[1]) - Decimal(m[2]), "f")
        elif "pips" in texto and "Current spread" in texto:
            f["unidad"], f["lectura"] = "pips", valor
        return dict(f, texto_v1=texto)
    if texto.upper().startswith(("CÁLCULO", "CALCULO")):
        return {"tipo": "calculo", "formula": texto.split("|")[0].split(":", 1)[-1].strip(),
                "entradas": [], "texto_v1": texto}
    if texto.startswith("Convención"):
        return {"tipo": "regla", "regla": texto, "referencia": "reference/tabla-reglas.md"}
    return {"tipo": "dato", "url": url, "fecha": fecha, "texto_v1": texto}


def cmd_migrar(a):
    perfil = cargar_perfil(a.perfil)
    codigo = 0
    for s in a.simbolos:
        p, clave = ruta_json(s)
        d = leer_json(p)
        if d.get("esquema") == ESQUEMA:
            print(f"[{clave}] ya está en el esquema {ESQUEMA}")
            continue
        fu = d.get("fuentes") if isinstance(d.get("fuentes"), dict) else {}
        nuevo = {"esquema": ESQUEMA}
        nuevo.update({k: v for k, v in d.items() if k not in AJUSTES and k != "fuentes"})
        nuevo["fuentes"] = {k: migrar_fuente(k, d.get(k, ""), str(fu.get(k, ""))) for k in CAMPOS}
        copia = p.with_name(p.name + ".v1")
        if not copia.exists():
            shutil.copyfile(p, copia)
        p.write_text(json.dumps(nuevo, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"[{clave}] migrado a v2: {p} (original en {copia.name})")
        r = validar(nuevo, perfil)
        informe(clave, r)
        if r.estado == "NO VÁLIDA":
            codigo = 1
    return codigo


def cmd_perfil(a):
    perfil = cargar_perfil(a.perfil)
    d = perfil.d
    print(f"Perfil: {d.get('nombre', '(sin nombre)')} [{perfil.origen}] {perfil.ruta}")
    print(f"  Bróker {d['broker']} · {d['plataforma']} · cuenta en {d['divisa_cuenta']}")
    dat = d["datos"]
    print(f"  Datos {dat['proveedor']} con «{dat['broker_profile_descarga']}», clonados a «{dat['zona_clon']}»")
    aj = perfil.ajustes
    print(f"  Ajustes personales (decisión de configuración, no datos del bróker): slippage {aj['slippage']} · "
          f"min dist. {aj['min_dist']} · order mult. {aj['order_mult']} · order step {aj['order_step']} · "
          f"rollover {aj['rollover']}")
    return 0


def cmd_navegador(a):
    print(encontrar_navegador(a.navegador))
    return 0


def cmd_rutas(a):
    p, origen = ruta_perfil(a.perfil)
    print(f"SK={SK}\nDATA={datos_dir()}\nTABLAS={tablas_dir()}\nPERFIL={p} ({origen})")
    return 0


def main(argv=None):
    # Windows escribe en cp1252 cuando la salida va a otro programa (Claude, Git Bash, pruebas),
    # y python -I ignora PYTHONUTF8 y PYTHONIOENCODING: la salida siempre en UTF-8.
    for flujo in (sys.stdout, sys.stderr):
        if hasattr(flujo, "reconfigure"):
            flujo.reconfigure(encoding="utf-8", errors="replace")
    comun = argparse.ArgumentParser(add_help=False)
    comun.add_argument("--perfil", help="perfil JSON (por defecto SQD_PERFIL, DATA/perfil.json o config/perfil.json)")
    nav = argparse.ArgumentParser(add_help=False)
    nav.add_argument("--navegador", help="ruta de Chrome/Edge/Chromium/Brave (o SQD_NAVEGADOR)")
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    s = p.add_subparsers(dest="orden", required=True)
    x = s.add_parser("plantilla", parents=[comun]); x.add_argument("simbolo")
    x.add_argument("--forzar", action="store_true"); x.set_defaults(f=cmd_plantilla)
    x = s.add_parser("validar", parents=[comun]); x.add_argument("simbolos", nargs="+")
    x.add_argument("--estricto", action="store_true", help="una tabla incompleta cuenta como fallo")
    x.set_defaults(f=cmd_validar)
    x = s.add_parser("generar", parents=[comun, nav]); x.add_argument("simbolos", nargs="+"); x.set_defaults(f=cmd_generar)
    x = s.add_parser("todas", parents=[comun, nav]); x.set_defaults(f=cmd_todas)
    x = s.add_parser("migrar", parents=[comun]); x.add_argument("simbolos", nargs="+"); x.set_defaults(f=cmd_migrar)
    x = s.add_parser("perfil", parents=[comun]); x.set_defaults(f=cmd_perfil)
    x = s.add_parser("navegador", parents=[nav]); x.set_defaults(f=cmd_navegador)
    x = s.add_parser("rutas", parents=[comun]); x.set_defaults(f=cmd_rutas)
    a = p.parse_args(argv)
    try:
        return a.f(a)
    except ErrorUso as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
