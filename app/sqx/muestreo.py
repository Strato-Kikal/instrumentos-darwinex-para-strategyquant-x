"""Spread medio automático: muestreo del bid/ask de Darwinex (solo biblioteca estándar).

Una tarea programada de GitHub Actions (.github/workflows/spread-medio.yml) ejecuta
app/muestreo_spread.py cada 15 minutos:
  1. lee la lista de símbolos y sus horarios de los datos de Darwinex,
  2. lee el bid/ask de todos ellos en el feed de precios que usa la web de Darwinex,
  3. guarda ask − bid en pips (mismo Pip/Tick Size que la tabla) solo si el mercado está abierto
     y la cotización ha cambiado desde la muestra anterior (así no cuentan festivos ni pausas),
  4. publica medias.json con la media de los últimos 30 días de cada símbolo.
Los datos viven en la rama «datos-spread» del repositorio; la app y la skill los leen de
tabla.URL_DATOS_SPREAD. Sin comisiones: es solo el spread.
"""
import datetime as dt
import json
from decimal import Decimal
from pathlib import Path

from . import tabla
from .instrumento import CLASES, hora_nueva_york, pip_regla

DIAS_MEDIA = 30          # ventana de la media (días naturales, el de hoy incluido)
DIAS_GUARDADOS = 40      # se borran los días más antiguos
POR_PETICION = 30        # símbolos por petición al feed de precios


def hora_londres(utc):
    """Hora de Londres con el horario de verano del Reino Unido (último domingo de marzo a último
    domingo de octubre, a la 01:00 UTC)."""
    a = utc.year

    def ultimo_domingo(mes):
        d = dt.date(a, mes + 1, 1) - dt.timedelta(days=1) if mes < 12 else dt.date(a, 12, 31)
        return d - dt.timedelta(days=(d.weekday() + 1) % 7)

    inicio = dt.datetime.combine(ultimo_domingo(3), dt.time(1), dt.timezone.utc)
    fin = dt.datetime.combine(ultimo_domingo(10), dt.time(1), dt.timezone.utc)
    return utc + dt.timedelta(hours=1 if inicio <= utc < fin else 0)


def hora_local(zona, utc):
    if zona == "Europe/London":
        return hora_londres(utc)
    return hora_nueva_york(utc)  # America/New_York y, si llega otra zona, la de Darwinex


def leer_hora(texto):
    try:
        h, m, *s = (int(x) for x in str(texto).split(":"))
        return dt.time(h, m, s[0] if s else 0)
    except (ValueError, TypeError):
        return None


def abierto(r, utc):
    """True si el instrumento cotiza en ese momento según el horario que publica Darwinex
    (opentime/closetime en su zona). Sesión dentro del día (p. ej., 01:30–20:55): de lunes a
    viernes. Sesión que cruza la medianoche (17:05–16:55): abre el domingo y cierra el viernes."""
    apertura, cierre = leer_hora(r.get("opentime")), leer_hora(r.get("closetime"))
    if apertura is None or cierre is None:
        return False
    local = hora_local(r.get("timezone"), utc)
    dia, hora = local.weekday(), local.time()  # lunes = 0 … domingo = 6
    if apertura < cierre:
        return dia <= 4 and apertura <= hora < cierre
    return (dia in (6, 0, 1, 2, 3) and hora >= apertura) or (dia <= 4 and hora < cierre)


def instrumentos(dx):
    """[(ticker, clase, registro de Darwinex, Pip/Tick Size)] de las clases que cubre la skill."""
    res = []
    for clase in CLASES:
        for r in dx.get(clase) or []:
            if not isinstance(r, dict) or not r.get("asset"):
                continue
            pip = pip_regla(clase, r)
            if pip is not None:
                res.append((str(r["asset"]).upper(), clase, r, pip))
    return res


def cargar(ruta, defecto):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return defecto


def guardar(ruta, datos):
    Path(ruta).parent.mkdir(parents=True, exist_ok=True)
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
                          encoding="utf-8")


def muestrear(dx, precios, ultimas, dia, ahora):
    """Añade a «dia» ({símbolo: {n, suma, min, max, pip}}) una muestra por símbolo abierto cuya
    cotización ha cambiado. precios: {símbolo: (bid, ask) o None}. ultimas: {símbolo: [bid, ask]}
    de la muestra anterior (se actualiza). Devuelve {"anadidas", "cerrados", "sin_cambio",
    "sin_datos"}."""
    cuenta = {"anadidas": 0, "cerrados": 0, "sin_cambio": 0, "sin_datos": 0}
    for ticker, _, r, pip in instrumentos(dx):
        if not abierto(r, ahora):
            cuenta["cerrados"] += 1
            continue
        q = precios.get(ticker)
        if not q or q[1] < q[0]:
            cuenta["sin_datos"] += 1
            continue
        bid, ask = q
        actual = [format(bid, "f"), format(ask, "f")]
        if ultimas.get(ticker) == actual:
            cuenta["sin_cambio"] += 1
            continue
        ultimas[ticker] = actual
        pips = (ask - bid) / pip
        e = dia.setdefault(ticker, {"n": 0, "suma": "0", "pip": format(pip.normalize(), "f")})
        if e.get("pip") != format(pip.normalize(), "f"):  # cambió el Pip/Tick Size: se reinicia
            e = dia[ticker] = {"n": 0, "suma": "0", "pip": format(pip.normalize(), "f")}
        e["n"] += 1
        e["suma"] = format(Decimal(e["suma"]) + pips, "f")
        e["min"] = format(min(Decimal(e.get("min", pips)), pips), "f")
        e["max"] = format(max(Decimal(e.get("max", pips)), pips), "f")
        cuenta["anadidas"] += 1
    return cuenta


def calcular_medias(dias, hoy, inicio, generado):
    """medias.json a partir de {fecha: {símbolo: acumulado}} de los últimos DIAS_MEDIA días."""
    desde_min = hoy - dt.timedelta(days=DIAS_MEDIA - 1)
    acum = {}
    for fecha in sorted(dias):
        f = dt.date.fromisoformat(fecha)
        if not desde_min <= f <= hoy:
            continue
        for s, e in dias[fecha].items():
            a = acum.get(s)
            if a and a["pip"] != e["pip"]:  # Pip/Tick Size distinto: solo cuentan los días nuevos
                a = None
            if not a:
                a = acum[s] = {"n": 0, "suma": Decimal(0), "pip": e["pip"], "desde": fecha,
                               "min": Decimal(e["min"]), "max": Decimal(e["max"])}
            a["n"] += e["n"]
            a["suma"] += Decimal(e["suma"])
            a["hasta"] = fecha
            a["min"] = min(a["min"], Decimal(e["min"]))
            a["max"] = max(a["max"], Decimal(e["max"]))
    simbolos = {}
    for s, a in sorted(acum.items()):
        if not a["n"]:
            continue
        media = (a["suma"] / a["n"]).quantize(Decimal("0.000001"))
        simbolos[s] = {"spread": format(media.normalize(), "f"), "pip": a["pip"],
                       "muestras": a["n"], "desde": a["desde"], "hasta": a["hasta"],
                       "min": tabla.redondear_spread(a["min"]),
                       "max": tabla.redondear_spread(a["max"])}
    return {"fuente": tabla.FUENTE_MUESTREO, "broker": "Darwinex", "unidad": "pips",
            "comision": "excluida", "franja": "24 horas", "periodo_dias": DIAS_MEDIA,
            "intervalo_min": tabla.INTERVALO_MUESTREO, "inicio": inicio,
            "generado_utc": generado.strftime("%Y-%m-%d %H:%M"),
            "metodo": ("media de ask − bid del feed de precios de Darwinex (widgets.fxbluelabs.com), "
                       "en pips del Pip/Tick Size de la tabla, una muestra cada 15 min con el mercado "
                       "abierto según el horario de Darwinex y solo si la cotización cambió"),
            "simbolos": simbolos}


def ejecutar(carpeta, fuentes, ahora=None):
    """Una ronda de muestreo sobre la carpeta de datos. Devuelve el recuento."""
    ahora = ahora or dt.datetime.now(dt.timezone.utc)
    carpeta = Path(carpeta)
    dx, _ = fuentes.darwinex()
    tickers = [t for t, *_ in instrumentos(dx)]
    precios = {}
    for i in range(0, len(tickers), POR_PETICION):
        precios.update(fuentes.precios_varios(tickers[i:i + POR_PETICION]))
    ultimas = cargar(carpeta / "ultimas.json", {})
    hoy = ahora.date()
    ruta_dia = carpeta / "dias" / f"{hoy.isoformat()}.json"
    dia = cargar(ruta_dia, {})
    cuenta = muestrear(dx, precios, ultimas, dia, ahora)
    guardar(ruta_dia, dia)
    guardar(carpeta / "ultimas.json", ultimas)
    dias = {}
    for p in sorted((carpeta / "dias").glob("*.json")):
        try:
            f = dt.date.fromisoformat(p.stem)
        except ValueError:
            continue
        if (hoy - f).days >= DIAS_GUARDADOS:
            p.unlink()
            continue
        dias[p.stem] = cargar(p, {})
    inicio = cargar(carpeta / "medias.json", {}).get("inicio") or hoy.isoformat()
    guardar(carpeta / "medias.json", calcular_medias(dias, hoy, inicio, ahora))
    return cuenta
