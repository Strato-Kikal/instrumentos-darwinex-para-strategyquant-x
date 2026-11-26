"""Prepara la tabla de un símbolo con datos consultados en vivo.

Hace lo que en la skill hacía Claude siguiendo SKILL.md y reference/tabla-reglas.md:
  1. identificar el ticker de Darwinex (y las equivalencias de Dukascopy comprobadas),
  2. leer contrato, tick, swaps, comisión y triple swap de los datos de Darwinex,
  3. leer el spread actual y convertirlo a pips,
  4. convertir a USD con el tipo del BCE cuando hace falta,
  5. registrar cada valor con su fuente estructurada (esquema 2 de la skill).
El resultado se valida con tabla.validar() de la skill: si hay errores, no se entrega.
Lo que no tiene evidencia queda «PENDIENTE DE VERIFICAR», nunca un valor supuesto.
"""
import datetime as dt
import difflib
import re
from decimal import ROUND_HALF_UP, Decimal

from . import tabla
from .fuentes import (URL_BCE, URL_COSTES, URL_DARWINEX, FuenteError, ahora_utc,
                      fecha_actualizacion)

PEND = tabla.PEND

CLASES = {
    "forex": {"tipo": "Forex", "nombre": "forex",
              "pagina": "https://www.darwinex.com/forex-cfds/forex"},
    "indices": {"tipo": "Index", "nombre": "índices",
                "pagina": "https://www.darwinex.com/forex-cfds/indices"},
    "commodities": {"tipo": "Forex / CFD", "nombre": "materias primas y metales",
                    "pagina": "https://www.darwinex.com/forex-cfds/commodities"},
    "crypto": {"tipo": "Crypto / CFD", "nombre": "cripto",
               "pagina": "https://www.darwinex.com/forex-cfds/crypto"},
}
FUERA_DE_ALCANCE = {"stocks": "una acción de EE. UU.", "etf": "un ETF", "futs": "un futuro"}
# Equivalencias Dukascopy → Darwinex ya comprobadas (reference/tabla-reglas.md)
DUKASCOPY = {"USATECHIDXUSD": "NDX", "USA30IDXUSD": "WS30", "USA500IDXUSD": "SP500"}

# Código «tripleSwapDay» del JSON de Darwinex: 1 = domingo … 7 = sábado. Contrastado el 2026-11-26
# con las notas que publica Darwinex en sus tablas (forex 4 → miércoles, USDCAD 5 → jueves,
# índices 6 → viernes, metales 4 → miércoles).
DIAS = {1: "SUNDAY", 2: "MONDAY", 3: "TUESDAY", 4: "WEDNESDAY", 5: "THURSDAY", 6: "FRIDAY",
        7: "SATURDAY"}
FECHA_NOTAS = "2026-11-26"
NOTAS_TRIPLE = {
    "forex": ("WEDNESDAY", "Swaps are charged daily at 17:00 NY City time. Wednesday swaps are "
                           "charged in triple size."),
    "USDCAD": ("THURSDAY", "USDCAD swaps are charged daily at 17:00 NY City time. Thursday swaps "
                           "are charged in triple size."),
    "indices": ("FRIDAY", "Swaps are charged daily on market close (in triple size on Fridays)."),
    "commodities": ("WEDNESDAY", "Swaps are charged daily at 17:00 NY City time (in triple size "
                                 "on Wednesdays)."),
}
NOTA_PROPIA = {"XTIUSD", "XNGUSD"}
URL_NOTA_PROPIA = "https://help.darwinex.com/swaps-xtiusd-xngusd"

REF_REGLAS = "reference/tabla-reglas.md"
REF_VERIF = "reference/verificacion-fuentes.md"
# Definición de Point value (administrador de SQ), verificada el 2026-10-27 en REF_VERIF
URL_SQ_PV = ("https://strategyquant.com/forum/topic/"
             "deep-explanation-of-instrument-specifications-pip-tick-size-step-value-etc/")
FECHA_SQ_PV = "2026-10-27"

ETIQUETAS = {k: cab for k, cab, _, _ in tabla.T1 + tabla.T2}
ETIQUETAS["comision"] = "Comisión a poner en SQ"
ORIGENES = {"dato": "Dato del bróker", "observado": "Lectura en vivo", "calculo": "Cálculo",
            "regla": "Regla de formato", "pendiente": "Pendiente de verificar",
            "ajuste": "Ajuste personal"}


class ErrorEntrada(Exception):
    """El texto escrito no es un símbolo válido."""


class SimboloNoEncontrado(Exception):
    def __init__(self, simbolo, sugerencias):
        self.simbolo, self.sugerencias = simbolo, sugerencias
        texto = (f"«{simbolo}» no aparece en las tablas de Darwinex (forex, índices, materias "
                 "primas y cripto).")
        if sugerencias:
            texto += " ¿Quizá " + ", ".join(sugerencias) + "?"
        super().__init__(texto)


class FueraDeAlcance(Exception):
    """El símbolo existe en Darwinex, pero no es de las clases que cubre la skill."""


class ErrorInterno(Exception):
    """La tabla preparada no pasa la validación de la skill (no debería ocurrir)."""


# ---------------------------------------------------------------- utilidades

def normalizar(texto):
    s = re.sub(r"[\s/]", "", str(texto or "")).upper()
    if not s:
        raise ErrorEntrada("Escribe un símbolo, por ejemplo EURUSD.")
    if not re.match(r"^[A-Z0-9._-]{1,40}$", s) or ".." in s:
        raise ErrorEntrada(f"«{str(texto).strip()[:40]}» no es un símbolo válido: usa letras y "
                           "números, por ejemplo EURUSD, NDX o XAUUSD.")
    return s


def txt(n):
    """Decimal → texto con punto decimal y sin notación científica."""
    if n == 0:
        return "0"
    return format(n.normalize(), "f")


def cent(n):
    return format(n.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def importe(n):
    """Importe con 2 decimales, o los que tenga si son más (no se pierde precisión)."""
    return txt(n) if -n.normalize().as_tuple().exponent > 2 else cent(n)


def num(r, k):
    v = r.get(k)
    return v if isinstance(v, Decimal) else None


def hora_nueva_york(utc):
    """Hora de Nueva York con el horario de verano de EE. UU. (desde 2007)."""
    a = utc.year

    def domingo(mes, n):
        d = dt.date(a, mes, 1)
        d += dt.timedelta(days=(6 - d.weekday()) % 7)
        return d + dt.timedelta(weeks=n - 1)

    inicio = dt.datetime.combine(domingo(3, 2), dt.time(7), dt.timezone.utc)   # 2:00 EST
    fin = dt.datetime.combine(domingo(11, 1), dt.time(6), dt.timezone.utc)     # 2:00 EDT
    return utc + dt.timedelta(hours=-4 if inicio <= utc < fin else -5)


def fin_de_semana(utc):
    """True entre el viernes 16:55 y el domingo 17:05 de Nueva York (horario de Darwinex)."""
    ny = hora_nueva_york(utc)
    dia, hm = ny.weekday(), (ny.hour, ny.minute)
    return dia == 5 or (dia == 4 and hm >= (16, 55)) or (dia == 6 and hm < (17, 5))


def buscar(dx, simbolo):
    """(clase, registro de Darwinex, ticker buscado)."""
    objetivo = DUKASCOPY.get(simbolo, simbolo)

    def coincide(r):
        return isinstance(r, dict) and objetivo in (str(r.get("asset", "")).upper(),
                                                    str(r.get("assetContract", "")).upper())
    for clase in CLASES:
        for r in dx.get(clase) or []:
            if coincide(r):
                return clase, r, objetivo
    for clase, que in FUERA_DE_ALCANCE.items():
        if any(coincide(r) for r in dx.get(clase) or []):
            raise FueraDeAlcance(f"«{simbolo}» es {que} en Darwinex. Esta versión solo prepara "
                                 "forex, índices, materias primas y cripto, como la skill.")
    todos = sorted({str(r.get("asset")) for c in CLASES for r in dx.get(c) or []
                    if isinstance(r, dict) and r.get("asset")})
    raise SimboloNoEncontrado(simbolo, difflib.get_close_matches(objetivo, todos, n=4, cutoff=0.6))


# ---------------------------------------------------------------- preparación de la tabla

class Preparacion:
    def __init__(self, simbolo, fuentes, perfil):
        self.simbolo, self.fuentes, self.perfil = simbolo, fuentes, perfil
        self.d, self.fu, self.notas, self.avisos, self.consultas = {}, {}, [], [], []
        self._bce = None

    # -- registro de fuentes consultadas (para la pantalla y el PDF)
    def consulta(self, nombre, url, hora, estado, detalle=""):
        self.consultas.append({"fuente": nombre, "url": url, "estado": estado, "detalle": detalle,
                               "hora_utc": hora.strftime("%Y-%m-%d %H:%M") if hora else None})

    def pend(self, campo, motivo):
        self.d[campo] = PEND
        self.fu[campo] = {"tipo": "pendiente", "motivo": motivo}

    def dato(self, nota):
        return {"tipo": "dato", "url": URL_DARWINEX, "fecha": self.f_dx,
                "nota": f"{nota} (datos de la tabla {self.pagina})"}

    def ent(self, nombre, valor, **extra):
        e = {"nombre": nombre, "valor": valor, "url": URL_DARWINEX, "fecha": self.f_dx}
        e.update(extra)
        return e

    # -- tipos de cambio del BCE, solo si hacen falta
    def usd_por(self, divisa):
        """(USD por 1 unidad de divisa, entradas, texto de la fórmula) o (None, motivo, None)."""
        if divisa == "USD":
            return Decimal(1), [], ""
        if self._bce is None:
            try:
                fecha, tipos, hora = self.fuentes.bce()
                self._bce = (fecha, tipos)
                self.consulta("BCE (tipos de referencia)", URL_BCE, hora, "correcto",
                              f"tipos del {fecha}")
            except FuenteError as e:
                self._bce = False
                self.consulta("BCE (tipos de referencia)", URL_BCE, None, "fallo", e.motivo)
                self.avisos.append(f"No se pudo consultar el BCE ({e.motivo}): los valores que "
                                   "necesitan conversión a USD quedan PENDIENTE DE VERIFICAR.")
        if not self._bce:
            return None, "no se pudo consultar el tipo de cambio del BCE", None
        fecha, tipos = self._bce
        if divisa not in tipos:
            return None, f"el BCE no publica el tipo de {divisa}", None
        e_usd = {"nombre": "tipo_cambio EURUSD", "valor": txt(tipos["USD"]), "url": URL_BCE,
                 "fecha": fecha}
        if divisa == "EUR":
            return tipos["USD"], [e_usd], "EURUSD"
        e_div = {"nombre": f"tipo_cambio EUR{divisa}", "valor": txt(tipos[divisa]), "url": URL_BCE,
                 "fecha": fecha}
        return tipos["USD"] / tipos[divisa], [e_usd, e_div], f"(EURUSD ÷ EUR{divisa})"

    # -- paso principal
    def preparar(self):
        dx, hora_dx = self.fuentes.darwinex()  # sin Darwinex no hay tabla: FuenteError sube
        act = fecha_actualizacion(dx)
        self.consulta("Darwinex (condiciones de trading)", URL_DARWINEX, hora_dx, "correcto",
                      f"datos actualizados por Darwinex el {act:%Y-%m-%d %H:%M} UTC" if act else "")
        self.clase, self.r, self.ticker = buscar(dx, self.simbolo)
        self.hora_dx, self.f_dx = hora_dx, hora_dx.date().isoformat()
        self.pagina = CLASES[self.clase]["pagina"]
        self.divisa = str(self.r.get("currency") or "").upper() or None

        self.campo_nombre_tipo()
        self.campo_pip()
        self.campo_tick()
        self.campo_point_value()
        self.campo_spread()
        self.campo_comision()
        self.campos_swap()
        self.campo_triple()

        if self.ticker != self.simbolo:
            self.notas.append(f"{self.simbolo} (Dukascopy) es el mismo mercado que {self.ticker} "
                              "en Darwinex (equivalencia comprobada en reference/tabla-reglas.md).")
        if act:
            self.notas.append(f"Darwinex indica que sus datos se actualizaron el {act:%Y-%m-%d %H:%M} UTC.")
        if self.r.get("spreadAverage") not in (None, ""):
            self.notas.append(f"Spread medio publicado por Darwinex: {self.r['spreadAverage']} "
                              "(referencia; la tabla usa la lectura actual).")
        self.notas.append("Spread, swaps y tipos de cambio son lecturas del momento: vuelve a "
                          "consultarlos antes de usarlos.")

        fechas = [self.f_dx] + [f["fecha"] for f in self.fu.values() if f.get("fecha")]
        consulta = max(fechas)
        tabla_d = {"esquema": tabla.ESQUEMA, "simbolo": self.simbolo, "consulta": consulta,
                   "creada": consulta}
        tabla_d.update({k: self.d[k] for k in tabla.CAMPOS})
        tabla_d["fuentes"] = {k: self.fu[k] for k in tabla.CAMPOS}
        tabla_d["notas"] = self.notas
        r = tabla.validar(tabla_d, self.perfil)
        if r.errores:
            raise ErrorInterno("; ".join(r.errores))
        return tabla_d, r

    # ---------------------------------------------------------- campos
    def campo_nombre_tipo(self):
        sufijo = self.perfil.d.get("sufijo_nombre", "")
        self.d["nombre"] = f"{self.ticker}{sufijo}"
        self.fu["nombre"] = self.dato(f"ticker {self.ticker} + sufijo del perfil ({sufijo})")
        tipo = CLASES[self.clase]["tipo"]
        self.d["tipo"] = tipo
        self.fu["tipo"] = {"tipo": "regla", "regla": f"{CLASES[self.clase]['nombre']} = {tipo}",
                           "referencia": f"{REF_REGLAS} (Tabla 1: Tipo)"}

    def campo_pip(self):
        if self.clase == "forex":
            jpy = self.divisa == "JPY"
            self.d["pip_tick"] = "0.01" if jpy else "0.0001"
            self.fu["pip_tick"] = {"tipo": "regla", "regla": "forex 0.0001 (0.01 si cotiza en JPY)",
                                   "referencia": f"{REF_REGLAS}; https://strategyquant.com/doc/"
                                                 "import-history-data-metatrader-4/"}
        elif self.clase in ("indices", "crypto"):
            self.d["pip_tick"] = "1"
            self.fu["pip_tick"] = {"tipo": "regla",
                                   "regla": "índices: 1" if self.clase == "indices" else "cripto: 1",
                                   "referencia": f"{REF_REGLAS} (convenciones de la skill)"}
            if self.clase == "crypto":
                self.avisos.append("La convención Pip/Tick = 1 de cripto se definió con BTCUSD; "
                                   "con precios bajos, revisa si te conviene otro Pip/Tick.")
        else:
            tick = num(self.r, "tickSize")
            if tick is None or tick <= 0:
                self.pend("pip_tick", "Darwinex no da el tick de este instrumento (tickSize)")
            else:
                self.d["pip_tick"] = txt(tick)
                self.fu["pip_tick"] = self.dato(f"tickSize = {txt(tick)}; convención: en metales y "
                                                "materias primas Pip/Tick = tick real")

    def campo_tick(self):
        pip = self.pip()
        tick_dx = num(self.r, "tickSize")
        if self.clase == "forex":
            if pip is None:
                return self.pend("no_pip_tick", "falta Pip/Tick")
            calc = pip / 10
            if tick_dx is None:
                return self.pend("no_pip_tick", "Darwinex no da el tick (tickSize) para confirmarlo")
            if calc != tick_dx:
                return self.pend("no_pip_tick", f"discrepancia: Pip/Tick ÷ 10 = {txt(calc)}, pero "
                                                f"Darwinex da tickSize = {txt(tick_dx)}")
            self.d["no_pip_tick"] = txt(calc)
            self.fu["no_pip_tick"] = {
                "tipo": "calculo",
                "formula": "Pip/Tick ÷ 10 (Darwinex cotiza el forex con 5 decimales, 3 en JPY)",
                "entradas": [{"nombre": "pip_tick", "valor": self.d["pip_tick"], "campo": "pip_tick"},
                             self.ent("tickSize de Darwinex (comprobación)", txt(tick_dx))]}
            return
        tv, ct = num(self.r, "tickValue"), num(self.r, "contractSize")
        if tv is None or ct is None or ct <= 0 or tv <= 0:
            return self.pend("no_pip_tick", "Darwinex no da el tick value o el contrato")
        calc = tv / ct
        if tick_dx is not None and calc != tick_dx:
            return self.pend("no_pip_tick", f"discrepancia en los datos de Darwinex: tick value "
                                            f"{txt(tv)} ÷ contrato {txt(ct)} = {txt(calc)}, pero "
                                            f"tickSize = {txt(tick_dx)}. Compruébalo en MT5 → "
                                            "Especificación")
        self.d["no_pip_tick"] = txt(calc)
        entradas = [self.ent("tick_value", txt(tv), unidad=self.divisa or ""),
                    self.ent("contrato", txt(ct))]
        if tick_dx is not None:
            entradas.append(self.ent("tickSize de Darwinex (comprobación)", txt(tick_dx)))
        self.fu["no_pip_tick"] = {"tipo": "calculo", "formula": "tick real = tick_value ÷ contrato",
                                  "entradas": entradas}

    def campo_point_value(self):
        ct = num(self.r, "contractSize")
        if ct is None or ct <= 0:
            return self.pend("point_value", "Darwinex no da el tamaño del contrato")
        if not self.divisa:
            return self.pend("point_value", "Darwinex no indica la divisa de cotización")
        definicion = {"nombre": "definición de Point value",
                      "valor": "valor en USD de un movimiento de 1.0 con 1 lote",
                      "url": URL_SQ_PV, "fecha": FECHA_SQ_PV}
        if self.divisa == "USD":
            self.d["point_value"] = txt(ct)
            self.fu["point_value"] = {"tipo": "calculo",
                                      "formula": "contrato × 1.0 de precio (cotizado en USD, sin conversión)",
                                      "entradas": [self.ent("contrato", txt(ct)), definicion]}
            return
        f, entradas, formula = self.usd_por(self.divisa)
        if f is None:
            return self.pend("point_value", f"cotiza en {self.divisa} y {entradas}")
        self.d["point_value"] = f"{cent(ct * f)} aprox."
        self.fu["point_value"] = {
            "tipo": "calculo",
            "formula": f"contrato × 1.0 {self.divisa} × {formula} (BCE)",
            "entradas": [self.ent("contrato", txt(ct), unidad=f"cotizado en {self.divisa}")] + entradas
                        + [definicion]}

    def pip(self):
        v = self.d.get("pip_tick")
        return None if v in (None, PEND) else Decimal(v)

    def campo_spread(self):
        pip = self.pip()
        try:
            precio, hora, url = self.fuentes.precios(self.ticker)
        except FuenteError as e:
            self.consulta("Feed de spread (fxbluelabs)", "https://widgets.fxbluelabs.com", None,
                          "fallo", e.motivo)
            self.avisos.append(f"No se pudo leer el spread actual ({e.motivo}).")
            return self.pend("spread", f"el feed de precios de Darwinex no respondió ({e.motivo}); "
                                       "usa la columna Spread de MT5 → Observación de mercado")
        if precio is None:
            self.consulta("Feed de spread (fxbluelabs)", url, hora, "sin datos",
                          f"sin cotización para {self.ticker}")
            return self.pend("spread", f"el feed de precios no tiene cotización de {self.ticker}; "
                                       "usa la columna Spread de MT5 → Observación de mercado")
        bid, ask = precio
        lectura = ask - bid
        self.consulta("Feed de spread (fxbluelabs)", url, hora, "correcto",
                      f"bid {txt(bid)} · ask {txt(ask)}")
        if lectura < 0:
            return self.pend("spread", f"lectura incoherente (ask {txt(ask)} < bid {txt(bid)})")
        if pip is None:
            return self.pend("spread", "falta Pip/Tick para pasar la lectura a pips")
        pips = lectura / pip
        self.d["spread"] = txt(pips) if pips == pips.quantize(Decimal("0.01")) else cent(pips)
        self.fu["spread"] = {"tipo": "observado", "url": url, "fecha": hora.date().isoformat(),
                             "hora_utc": hora.strftime("%H:%M"), "unidad": "precio",
                             "lectura": txt(lectura),
                             "nota": f"ask {txt(ask)} − bid {txt(bid)}; feed de precios que usa "
                                     "la web de Darwinex"}
        if fin_de_semana(hora):
            self.avisos.append("Mercado cerrado por el fin de semana: el feed puede dar la última "
                               "cotización del viernes y el spread puede no ser representativo.")
            self.notas.append(f"Spread leído con el mercado cerrado ({hora:%Y-%m-%d %H:%M} UTC).")

    def campo_comision(self):
        porcentaje = self.clase in ("commodities", "crypto")
        self.d["modelo_comision"] = "Comisión en porcentaje" if porcentaje else "En función del tamaño"
        self.fu["modelo_comision"] = self.dato(
            "Darwinex muestra la comisión como % del valor de la orden → Comisión en porcentaje"
            if porcentaje else
            "Darwinex muestra la comisión como importe fijo por contrato y orden → En función del tamaño")
        c = num(self.r, "commission")
        if c is None or c < 0:
            return self.pend("comision", "Darwinex no da la comisión de este instrumento")
        try:
            fragmento, hora = self.fuentes.costes()
        except FuenteError as e:
            self.consulta("Ayuda de Darwinex (costes)", URL_COSTES, None, "fallo", e.motivo)
            return self.pend("comision", "no se pudo confirmar hoy que Darwinex publica la comisión "
                                         f"por orden ({e.motivo})")
        self.consulta("Ayuda de Darwinex (costes)", URL_COSTES, hora,
                      "correcto" if fragmento else "sin confirmar",
                      f"«{fragmento}»" if fragmento else "no aparece el texto «displayed per order … 2 orders»")
        if not fragmento:
            return self.pend("comision", "la página de costes de Darwinex ya no dice que la comisión "
                                         "se publica por orden: revisa la regla de ida y vuelta")
        ordenes = {"nombre": "órdenes por operación", "valor": "2", "url": URL_COSTES,
                   "fecha": hora.date().isoformat(), "nota": f"«{fragmento}»"}
        f2 = tabla.FACTOR_IDA_VUELTA
        if porcentaje:
            cpo, extra = c, []
            if self.clase == "crypto":
                # La web de Darwinex muestra la comisión de cripto como commission ÷ 100 (en %)
                cpo = c / 100
                extra = [self.ent("commission en los datos de Darwinex", txt(c),
                                  nota="la web lo muestra ÷ 100 como % del valor de la orden")]
            self.d["comision"] = txt(cpo * f2)
            self.fu["comision"] = {"tipo": "calculo", "formula": "comision_por_orden (%) × 2 (ida y vuelta)",
                                   "entradas": [self.ent("comision_por_orden", txt(cpo),
                                                         unidad="% del valor de la orden")]
                                               + extra + [ordenes]}
            return
        # Importe fijo: forex en la divisa base; índices en la divisa de cotización (así lo
        # muestra la web de Darwinex).
        divisa = self.ticker[:3] if self.clase == "forex" else self.divisa
        if not divisa:
            return self.pend("comision", "Darwinex no indica la divisa de la comisión")
        f, entradas, formula = self.usd_por(divisa)
        if f is None:
            return self.pend("comision", f"la comisión está en {divisa} y {entradas}")
        cpo_e = self.ent("comision_por_orden", txt(c), unidad=f"{divisa} por lote")
        if divisa == "USD":
            self.d["comision"] = cent(c * f2)
            formula_txt = "comision_por_orden × 2 (ida y vuelta)"
        else:
            self.d["comision"] = f"{cent(c * f2 * f)} aprox."
            formula_txt = f"comision_por_orden × 2 (ida y vuelta) × {formula} (BCE)"
        self.fu["comision"] = {"tipo": "calculo", "formula": formula_txt,
                               "entradas": [cpo_e, ordenes] + entradas}

    def campos_swap(self):
        for campo, k in (("swap_largo", "swapLong"), ("swap_corto", "swapShort")):
            v = num(self.r, k)
            if self.clase == "crypto":
                self.pend(campo, "Darwinex no explica en su tabla la unidad del swap de cripto "
                                 f"({k} = {txt(v) if v is not None else '—'}); compruébalo en MT5 "
                                 "→ Especificación")
                continue
            if v is None:
                self.pend(campo, "Darwinex no da este swap")
                continue
            if not self.divisa:
                self.pend(campo, "Darwinex no indica la divisa del swap")
                continue
            if self.divisa == "USD":
                self.d[campo] = importe(v)
                self.fu[campo] = self.dato("USD por contrato y día; lectura del día")
                continue
            f, entradas, formula = self.usd_por(self.divisa)
            if f is None:
                self.pend(campo, f"el swap está en {self.divisa} y {entradas}")
                continue
            self.d[campo] = f"{cent(v * f)} aprox."
            self.fu[campo] = {"tipo": "calculo",
                              "formula": f"swap por contrato y día en {self.divisa} × {formula} (BCE)",
                              "entradas": [self.ent(k, txt(v), unidad=f"{self.divisa} por contrato y día")]
                                          + entradas}

    def campo_triple(self):
        codigo = self.r.get("tripleSwapDay")
        cod = int(codigo) if isinstance(codigo, Decimal) and codigo == int(codigo) else None
        dia = DIAS.get(cod)
        if self.ticker in NOTA_PROPIA:
            return self.pend("triple_swap", f"{self.ticker} tiene su propia nota de triple swap "
                                            f"({URL_NOTA_PROPIA}); compruébala")
        nota = NOTAS_TRIPLE.get(self.ticker) or NOTAS_TRIPLE.get(self.clase)
        if nota is None:
            return self.pend("triple_swap", "Darwinex no publica una nota de triple swap para "
                                            f"{CLASES[self.clase]['nombre']} (tripleSwapDay = "
                                            f"{codigo if codigo is not None else '—'})")
        if dia is None:
            return self.pend("triple_swap", "Darwinex no da el día de triple swap (tripleSwapDay)")
        if dia != nota[0]:
            return self.pend("triple_swap", f"discrepancia: tripleSwapDay = {cod} ({dia}), pero la "
                                            f"nota de Darwinex dice «{nota[1]}»")
        self.d["triple_swap"] = dia
        self.fu["triple_swap"] = self.dato(
            f"tripleSwapDay = {cod} (1 = domingo … 7 = sábado) → {dia}; coincide con la nota de "
            f"Darwinex «{nota[1]}» (leída el {FECHA_NOTAS})")


# ---------------------------------------------------------------- explicación para personas

def explicar(fuente):
    """(origen, texto) de la fuente de una casilla, para la pantalla y el PDF."""
    t = fuente.get("tipo")
    if t == "pendiente":
        return ORIGENES[t], fuente.get("motivo", "")
    if t == "dato":
        texto = f"{fuente.get('url')} · consultado el {fuente.get('fecha')}"
        if fuente.get("nota"):
            texto += f" · {fuente['nota']}"
        return ORIGENES[t], texto
    if t == "observado":
        return ORIGENES[t], (f"{fuente.get('url')} · {fuente.get('fecha')} {fuente.get('hora_utc')} UTC · "
                             f"lectura {fuente.get('lectura')} ({fuente.get('unidad')}) ÷ Pip/Tick · "
                             f"{fuente.get('nota', '')}").rstrip(" ·")
    if t == "regla":
        return ORIGENES[t], f"{fuente.get('regla')} · {fuente.get('referencia')}"
    if t == "calculo":
        partes = []
        for e in fuente.get("entradas", []):
            p = f"{e.get('nombre')} = {e.get('valor')}"
            if e.get("unidad"):
                p += f" {e['unidad']}"
            if e.get("campo"):
                p += " (otra casilla)"
            elif e.get("url"):
                p += f" ({e['url']}, {e.get('fecha')})"
            partes.append(p)
        return ORIGENES[t], f"{fuente.get('formula')}. Entradas: " + "; ".join(partes)
    return t or "", ""


def detalle(tabla_d, perfil):
    """Casillas en el orden del PDF, con valor, origen y explicación; después, los ajustes."""
    filas = []
    for k in tabla.CAMPOS:
        origen, texto = explicar(tabla_d["fuentes"][k])
        filas.append({"campo": k, "casilla": ETIQUETAS.get(k, k), "valor": tabla_d[k],
                      "tipo": tabla_d["fuentes"][k]["tipo"], "origen": origen, "explicacion": texto})
    for k in tabla.AJUSTES:
        filas.append({"campo": k, "casilla": ETIQUETAS.get(k, k), "valor": perfil.ajustes[k],
                      "tipo": "ajuste", "origen": ORIGENES["ajuste"],
                      "explicacion": f"Decisión de configuración del perfil «{perfil.d.get('nombre')}», "
                                     "no es un dato del bróker"})
    return filas


def describir_perfil(perfil):
    d = perfil.d
    return {"nombre": d.get("nombre"), "broker": d["broker"], "plataforma": d["plataforma"],
            "divisa_cuenta": d["divisa_cuenta"], "datos": d["datos"], "ajustes": perfil.ajustes,
            "origen": getattr(perfil, "origen", "")}


def preparar(texto, fuentes, perfil):
    """Consulta las fuentes y devuelve el resultado completo de un símbolo."""
    simbolo = normalizar(texto)
    inicio = ahora_utc()
    p = Preparacion(simbolo, fuentes, perfil)
    tabla_d, r = p.preparar()
    return {
        "simbolo": simbolo, "ticker_darwinex": p.ticker, "clase": CLASES[p.clase]["nombre"],
        "consulta_utc": inicio.strftime("%Y-%m-%d %H:%M"),
        "estado": r.estado, "pendientes": r.pendientes,
        "avisos": p.avisos + r.avisos, "consultas": p.consultas,
        "perfil": describir_perfil(perfil), "tabla": tabla_d,
        "fila_pdf": tabla.fila_pdf(tabla_d, perfil), "detalle": detalle(tabla_d, perfil),
    }
