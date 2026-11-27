"""PDF sin dependencias (solo biblioteca estándar) para usar en un servidor sin navegador.

Página 1: lo que se copia en StrategyQuant X. Título y firma de la skill, estado de los datos,
«1. Configuración principal del instrumento» y «2. Comisiones, swaps y rollover» con los nombres
de las casillas de SQX, sus unidades y los ajustes personales señalados; debajo, las comprobaciones
que faltan dentro de SQX.
Página 2 (y siguientes solo si hacen falta): fuentes con enlaces, horas de consulta, fórmulas con
sus entradas, perfil y avisos, para poder reproducir cada valor.

Fuentes tipográficas estándar de PDF (Helvetica ≈ Arial) con codificación WinAnsi (cp1252).
"""
import datetime as dt
import zlib

import re

from . import NOMBRE, VERSION, tabla
from .fuentes import URL_BCE, URL_COSTES, URL_DARWINEX
from .instrumento import (ETIQUETAS, ORIGENES, URL_HORA_MT, URL_NOTA_PROPIA, URL_REPO,
                          URL_SQ_PV)
from .metricas import HELVETICA, HELVETICA_BOLD

MM = 72 / 25.4
ANCHO, ALTO = 297 * MM, 210 * MM  # A4 apaisado
MARGEN_V = 12 * MM
AZUL, LINEA, FILA_IMPAR = "#2C4D76", "#7A93B2", "#F4F6FA"
ROJO, ROSA, GRIS = "#9C0006", "#FFE7E7", "#7F7F7F"
VERDE, VERDE_FONDO, ENLACE = "#2E5A1F", "#EEF5E9", "#1F5FAD"
X0 = 12 * MM            # margen lateral
ANCHO_UTIL = ANCHO - 2 * X0
LIMITE = ALTO - MARGEN_V - 8 * MM   # por debajo va la firma
FUENTES = {"normal": ("F1", HELVETICA), "negrita": ("F2", HELVETICA_BOLD),
           "cursiva": ("F3", HELVETICA)}
SUSTITUCIONES = {"→": "->", "←": "<-", "≠": "!=", "≈": "~", "−": "-", "✗": "x", "✓": "v",
                 " ": " ", " ": " ", "≤": "<=", "≥": ">="}


def a_cp1252(texto):
    texto = "".join(SUSTITUCIONES.get(c, c) for c in str(texto))
    return texto.encode("cp1252", errors="replace")


def ancho_texto(texto, estilo, tam):
    tabla_anchos = FUENTES[estilo][1]
    return sum(tabla_anchos[b - 32] if 32 <= b <= 255 else 500 for b in a_cp1252(texto)) * tam / 1000


def color(hexa):
    h = hexa.lstrip("#")
    return " ".join(f"{int(h[i:i + 2], 16) / 255:.4f}" for i in (0, 2, 4))


def envolver(texto, estilo, tam, ancho):
    """Líneas que caben en «ancho». Parte palabras largas (p. ej., URL) si hace falta."""
    lineas = []
    for parrafo in str(texto).split("\n"):
        actual = ""
        for palabra in parrafo.split(" "):
            prueba = f"{actual} {palabra}" if actual else palabra
            if ancho_texto(prueba, estilo, tam) <= ancho:
                actual = prueba
                continue
            if actual:
                lineas.append(actual)
            actual = ""
            while ancho_texto(palabra, estilo, tam) > ancho:
                corte = len(palabra)
                while corte > 1 and ancho_texto(palabra[:corte], estilo, tam) > ancho:
                    corte -= 1
                lineas.append(palabra[:corte])
                palabra = palabra[corte:]
            actual = palabra
        lineas.append(actual)
    return lineas


class Lienzo:
    """Páginas con operaciones de dibujo en coordenadas desde arriba (y crece hacia abajo)."""

    def __init__(self):
        self.paginas, self.enlaces = [], []
        self.nueva_pagina()

    def nueva_pagina(self):
        self.ops, self.anots = [], []
        self.paginas.append(self.ops)
        self.enlaces.append(self.anots)
        self.y = MARGEN_V

    def cabe(self, h):
        return self.y + h <= LIMITE

    def rect(self, x, y, w, h, relleno=None, borde=None, grosor=0.6):
        yb = ALTO - y - h
        if relleno:
            self.ops.append(f"{color(relleno)} rg {x:.2f} {yb:.2f} {w:.2f} {h:.2f} re f")
        if borde:
            self.ops.append(f"{color(borde)} RG {grosor} w {x:.2f} {yb:.2f} {w:.2f} {h:.2f} re S")

    def texto(self, x, base, s, estilo="normal", tam=7, col="#000000"):
        """base = distancia desde arriba hasta la línea base."""
        if not s:
            return
        f = FUENTES[estilo][0]
        self.ops.append(f"BT /{f} {tam} Tf {color(col)} rg {x:.2f} {ALTO - base:.2f} Td "
                        f"<{a_cp1252(s).hex()}> Tj ET")

    def texto_alineado(self, x, ancho, base, s, alin, estilo="normal", tam=7, col="#000000"):
        w = ancho_texto(s, estilo, tam)
        if alin == "cen":
            x += (ancho - w) / 2
        elif alin == "der":
            x += ancho - w
        self.texto(x, base, s, estilo, tam, col)
        return x, w

    def enlace(self, x, base, s, url, tam=7, alin="izq", ancho=None):
        """Texto azul subrayado con un enlace clicable (anotación /Link /URI)."""
        x, w = self.texto_alineado(x, ancho or 0, base, s, alin, "normal", tam, ENLACE)
        self.rect(x, base + tam * 0.12, w, 0.4, relleno=ENLACE)
        self.anots.append((x, ALTO - base - tam * 0.25, x + w, ALTO - base + tam * 0.85, url))


# ---------------------------------------------------------------- tablas

def dibujar_tabla(lz, x, ancho, columnas, filas, cab_tam=7, celda_tam=7, pad_cab_v=3.2 * MM,
                  pad_v=1.05 * MM, pad_h=1.2 * MM, repetir=None):
    """columnas: [(cabecera, peso, alineación)]; filas: [[(contenido, estilo_celda)]].
    estilo_celda: None (normal), "pend" (rojo, negrita), "negrita" o "enlaces" (contenido =
    [(texto, url)], una línea por enlace). El texto se parte por palabras y por «\n»."""
    total = sum(c[1] for c in columnas)
    anchos = [ancho * c[1] / total for c in columnas]

    def alto_lineas(n, tam):
        return n * tam * 1.15

    def cabecera():
        lineas = [envolver(c[0], "negrita", cab_tam, w - 2.6 * MM) for c, w in zip(columnas, anchos)]
        h = max(alto_lineas(len(ls), cab_tam) for ls in lineas) + 2 * pad_cab_v
        if not lz.cabe(h + alto_lineas(2, celda_tam) + 2 * pad_v):
            lz.nueva_pagina()
            if repetir:
                repetir()
        cx = x
        for ls, w in zip(lineas, anchos):
            lz.rect(cx, lz.y, w, h, relleno=AZUL, borde=LINEA)
            bloque = alto_lineas(len(ls), cab_tam)
            base = lz.y + (h - bloque) / 2 + cab_tam * 0.93
            for i, linea in enumerate(ls):
                lz.texto_alineado(cx + 1 * MM, w - 2 * MM, base + i * cab_tam * 1.15, linea, "cen",
                                  "negrita", cab_tam, "#FFFFFF")
            cx += w
        lz.y += h
    cabecera()
    for n, fila in enumerate(filas):
        celdas = []
        for (contenido, est), (_, _, alin), w in zip(fila, columnas, anchos):
            tam = celda_tam - 1 if est == "pend" else celda_tam
            estilo = "negrita" if est in ("pend", "negrita") else "normal"
            if est == "enlaces":
                ls = contenido
            else:
                ls = envolver(contenido, estilo, tam, w - 2 * pad_h)
            celdas.append((ls, tam, estilo, alin, est))
        h = max(alto_lineas(len(c[0]), c[1]) for c in celdas) + 2 * pad_v
        h = max(h, alto_lineas(1, celda_tam) + 2 * pad_v)
        if not lz.cabe(h):
            lz.nueva_pagina()
            if repetir:
                repetir()
            cabecera()
        cx = x
        fondo = FILA_IMPAR if n % 2 == 0 else "#FFFFFF"
        for (ls, tam, estilo, alin, est), w in zip(celdas, anchos):
            pend = est == "pend"
            lz.rect(cx, lz.y, w, h, relleno=ROSA if pend else fondo, borde=LINEA)
            bloque = alto_lineas(len(ls), tam)
            base = lz.y + (h - bloque) / 2 + tam * 0.93
            for i, linea in enumerate(ls):
                b = base + i * tam * 1.15
                if est == "enlaces":
                    lz.enlace(cx + pad_h, b, linea[0], linea[1], tam, alin, w - 2 * pad_h)
                else:
                    lz.texto_alineado(cx + pad_h, w - 2 * pad_h, b, linea, alin, estilo, tam,
                                      ROJO if pend else "#000000")
            cx += w
        lz.y += h


def titulo_h2(lz, texto, x=X0, tam=12):
    lz.texto(x, lz.y + tam * 0.93, texto, "negrita", tam, AZUL)
    lz.y += tam * 1.15 + 2 * MM


def parrafo(lz, texto, x=X0, ancho=ANCHO_UTIL, estilo="normal", tam=8, col="#000000", sangria=""):
    sangria_w = ancho_texto(sangria, estilo, tam)
    for i, linea in enumerate(envolver(texto, estilo, tam, ancho - sangria_w)):
        if not lz.cabe(tam * 1.3):
            lz.nueva_pagina()
        if i == 0 and sangria:
            lz.texto(x, lz.y + tam * 0.93, sangria, estilo, tam, col)
        lz.texto(x + sangria_w, lz.y + tam * 0.93, linea, estilo, tam, col)
        lz.y += tam * 1.3


# ---------------------------------------------------------------- página 1: valores para SQX

# (clave, peso, alineación); el texto de la cabecera es el nombre de la casilla en SQX
T1 = [("simbolo", 10, "izq"), ("nombre", 13, "izq"), ("tipo", 7, "cen"), ("pip_tick", 8, "cen"),
      ("point_value", 9, "cen"), ("no_pip_tick", 8, "cen"), ("spread", 15, "cen"),
      ("slippage", 6.5, "cen"), ("min_dist", 6.5, "cen"), ("order_mult", 6.5, "cen"),
      ("order_step", 6.5, "cen")]
T2 = [("simbolo", 8.5, "izq"), ("modelo_comision", 10, "cen"), ("comision", 18, "cen"),
      ("tipo_swap", 11, "cen"), ("swap_largo", 7.5, "cen"), ("swap_corto", 7.5, "cen"),
      ("triple_swap", 9, "cen"), ("rollover", 15.5, "cen"), ("cobro_swap", 13, "cen")]
CABECERAS = {"simbolo": "Símbolo", "point_value": "Point Value $", "spread": "Default Spread",
             "swap_largo": "Swap largo", "swap_corto": "Swap corto"}
AJUSTE = " (ajuste)"


def cabecera_columna(k):
    cab = CABECERAS.get(k) or ETIQUETAS.get(k, k)
    return cab + (AJUSTE if k in tabla.AJUSTES and k != "rollover" else "")


def tabla_sqx(lz, resultados, cols):
    columnas = [(cabecera_columna(k), peso, al) for k, peso, al in cols]
    filas = []
    for res in resultados:
        t = dict(res["textos"], simbolo=res["fila_pdf"]["simbolo"])
        fila = []
        for k, _, _ in cols:
            v = str(t.get(k, ""))
            fila.append((v, "pend" if tabla.es_pendiente(v) else
                         ("negrita" if k == "simbolo" else None)))
        filas.append(fila)
    dibujar_tabla(lz, X0, ANCHO_UTIL, columnas, filas, cab_tam=8.5, celda_tam=9.5,
                  pad_cab_v=2.4 * MM, pad_v=2.2 * MM, pad_h=1.4 * MM)


def caja_estado(lz, res, varios):
    completa = not res["pendientes"]
    texto = res["estado_texto"]
    if varios:
        texto = f"{res['simbolo']}: {texto}"
    if not completa:
        texto += ". No uses esas casillas en SQX hasta completarlas."
    x, w = X0 + ANCHO_UTIL * 0.1, ANCHO_UTIL * 0.8
    ls = envolver(texto, "negrita", 10, w - 4 * MM)
    h = len(ls) * 11.5 + 3 * MM
    lz.rect(x, lz.y, w, h, relleno=VERDE_FONDO if completa else ROSA,
            borde=VERDE if completa else ROJO, grosor=0.75)
    for i, linea in enumerate(ls):
        lz.texto_alineado(x, w, lz.y + 1.5 * MM + 10 * 0.93 + i * 11.5, linea, "cen", "negrita",
                          10, VERDE if completa else ROJO)
    lz.y += h + 1.5 * MM


def pagina_principal(lz, resultados):
    lz.texto_alineado(0, ANCHO, lz.y + 20 * 0.93, tabla.TITULO, "cen", "negrita", 20, AZUL)
    lz.y += 20 * 1.15 + 1.5 * MM
    perfil = resultados[0]["perfil"]
    datos = perfil["datos"]
    sub = (f"{perfil['broker']} {perfil['plataforma']} · cuenta en {perfil['divisa_cuenta']} · datos "
           f"{datos['proveedor']} clonados a «{datos['zona_clon']}» · consulta "
           f"{max(r['consulta_utc'] for r in resultados)} UTC")
    lz.texto_alineado(0, ANCHO, lz.y + 9 * 0.93, sub, "cen", "normal", 9, GRIS)
    lz.y += 9 * 1.15 + 4 * MM
    for res in resultados:
        caja_estado(lz, res, len(resultados) > 1)
    lz.y += 3.5 * MM

    titulo_h2(lz, "1. Configuración principal del instrumento")
    tabla_sqx(lz, resultados, T1)
    lz.y += 1.5 * MM
    parrafo(lz, f"Default Spread: {tabla.ETIQUETA_SPREAD}. La comisión va aparte, en la tabla 2: no "
                "se suma al spread. «(ajuste)» y Rollover (SQX) son ajustes personales del perfil, "
                "no datos del bróker; el rollover no cambia el periodo del spread.", tam=7.5, col=GRIS)
    for res in resultados:
        for linea in res["spread_lineas"]:
            parrafo(lz, linea, tam=7.5, col=ROJO if "PENDIENTE" in linea else GRIS, sangria="• ")
    lz.y += 5 * MM
    titulo_h2(lz, "2. Comisiones, swaps y rollover")
    tabla_sqx(lz, resultados, T2)
    lz.y += 1.5 * MM
    parrafo(lz, "Rollover (SQX): hora a la que SQX aplica el swap sobre los datos clonados. Cobro del "
                "swap (Darwinex): hora a la que el bróker lo cobra en la cuenta real.", tam=7.5,
            col=GRIS)
    lz.y += 5 * MM

    lineas = 1 + sum(len(r["pruebas_sqx"]) + bool(r["pendientes"]) for r in resultados)
    if not lz.cabe(11 * 1.15 + 2 * MM + lineas * 9 * 1.3 * 1.5):
        lz.nueva_pagina()
    titulo_h2(lz, "Comprobaciones pendientes en SQX", tam=11)
    varios = len(resultados) > 1
    for res in resultados:
        pre = f"{res['simbolo']} · " if varios else ""
        if res["pendientes"]:
            parrafo(lz, f"{pre}Faltan datos: {', '.join(res['faltan'])}. Motivos en la página de "
                        "fuentes.", tam=9, col=ROJO, estilo="negrita", sangria="• ")
        for prueba in res["pruebas_sqx"]:
            parrafo(lz, pre + prueba, tam=9, sangria="• ")
    parrafo(lz, "Compara también cada valor con MT5 → Observación del mercado → Especificación. "
                "Esta tabla no se ha validado dentro de StrategyQuant X.", tam=9, sangria="• ")


# ---------------------------------------------------------------- página 2: fuentes y cálculos

RE_URL = re.compile(r"https?://[^\s;)»,]+")
RE_REF = re.compile(r"\b(reference/[\w.-]+\.md)")
ETIQUETAS_URL = [
    (URL_DARWINEX, "Darwinex · datos"), ("https://www.darwinex.com/forex-cfds/", "Darwinex · tabla"),
    (URL_BCE, "BCE · tipos de cambio"), (URL_COSTES, "Darwinex · costes"),
    (URL_HORA_MT, "Darwinex · hora MT5"), (URL_NOTA_PROPIA, "Darwinex · nota de swaps"),
    ("https://widgets.fxbluelabs.com", "Feed de precios"),
    ("https://forexbenchmark.com/", "Forex Benchmark · spreads históricos"), (URL_SQ_PV, "Foro SQ · Point value"),
    ("https://strategyquant.com/doc/", "Documentación SQ"), (URL_REPO, "Reglas de la skill"),
]


def etiqueta_url(url):
    for prefijo, etiqueta in ETIQUETAS_URL:
        if url.startswith(prefijo):
            if etiqueta == "Darwinex · tabla":
                etiqueta += " " + url.rstrip("/").rsplit("/", 1)[-1]
            return etiqueta
    return re.sub(r"^https?://(www\.)?", "", url).split("/")[0]


def enlaces(fuente):
    """[(texto corto, url)] de una fuente: sus URL con la fecha de consulta, sin repetir."""
    vistos, salida = set(), []

    def poner(url, fecha=None):
        url = url.rstrip(".")
        clave = etiqueta_url(url)
        if clave in vistos:
            return
        vistos.add(clave)
        salida.append((clave + (f" · {fecha}" if fecha else ""), url))

    def textos_de(f):
        for k in ("nota", "referencia", "motivo", "regla"):
            if f.get(k):
                yield str(f[k])

    if fuente.get("url"):
        poner(fuente["url"], fuente.get("fecha"))
    for e in fuente.get("entradas", []):
        if e.get("url"):
            poner(e["url"], e.get("fecha"))
    for e in [fuente] + fuente.get("entradas", []):
        for texto in textos_de(e):
            for url in RE_URL.findall(texto):
                poner(url)
            for ref in RE_REF.findall(texto):
                poner(URL_REPO + ref)
    return salida


def sin_url(texto):
    texto = re.sub(r"\s*\(datos de la tabla https?://[^)]+\)", "", texto)
    texto = re.sub(r"\s*\(https?://[^)]+\)", "", texto)
    return RE_URL.sub("", texto).replace(" ;", ";").strip(" ·;")


def como(fuente):
    """Cómo se obtiene el valor, sin las URL (van en la columna Fuente, como enlaces)."""
    t = fuente.get("tipo")
    if t == "pendiente":
        return sin_url(fuente.get("motivo", ""))
    if t in ("dato", "ajuste"):
        return sin_url(fuente.get("nota", ""))
    if t == "observado":
        return (f"Lectura del {fuente['fecha']} a las {fuente['hora_utc']} UTC: "
                f"{fuente.get('nota', '').split(';')[0]} = {fuente['lectura']} "
                f"({fuente['unidad']}) ÷ Pip/Tick Size. Solo informativo")
    if t == "promedio":
        return (f"Darwinex · 30 días · 24 h · sin comisiones, copiado a mano. Consulta "
                f"{fuente['fecha']} {fuente['hora_utc']} UTC; periodo: {tabla.periodo_spread(fuente)}. "
                f"{fuente['lectura']} pips de {fuente['pip_fuente']} → pips de Pip/Tick Size")
    if t == "regla":
        return sin_url(fuente.get("regla", ""))
    if t == "calculo":
        partes = []
        for e in fuente.get("entradas", []):
            p = f"{e.get('nombre')} = {e.get('valor')}"
            if e.get("unidad"):
                p += f" {e['unidad']}"
            if e.get("campo"):
                p += " (casilla)"
            elif e.get("fecha"):
                p += f" ({e['fecha']})"
            partes.append(p)
        return f"{fuente.get('formula')}. Entradas: " + "; ".join(partes)
    return ""


def pagina_fuentes(lz, resultados, momento):
    lz.nueva_pagina()
    lz.texto(X0, lz.y + 14 * 0.93, "Fuentes y cálculos", "negrita", 14, AZUL)
    lz.y += 14 * 1.15 + 2 * MM
    perfil = resultados[0]["perfil"]
    datos = perfil["datos"]
    parrafo(lz, f"Generado con {NOMBRE} {VERSION} el {momento:%Y-%m-%d %H:%M} UTC. Perfil: "
                f"{perfil['nombre']} · {perfil['broker']} {perfil['plataforma']} · cuenta en "
                f"{perfil['divisa_cuenta']} · datos {datos['proveedor']} descargados con "
                f"«{datos['broker_profile_descarga']}» y clonados a «{datos['zona_clon']}». "
                "Los enlaces azules abren la fuente. Origen: dato del bróker, spread medio de Forex "
                "Benchmark (el de Default Spread), lectura instantánea (solo informativa), cálculo "
                "(fórmula y entradas), regla de formato o ajuste personal (decisión del perfil, no "
                "del bróker).", tam=7.5)
    lz.y += 2 * MM
    for res in resultados:
        destino = res["ticker_darwinex"]
        cab = (res["simbolo"] + (f" → Darwinex {destino}" if destino != res["simbolo"] else "")
               + f" ({res['clase']}) · consulta {res['consulta_utc']} UTC")
        if not lz.cabe(40 * MM):
            lz.nueva_pagina()
        titulo_h2(lz, cab, tam=10.5)

        def repetir(cab=cab):
            titulo_h2(lz, f"{cab} (continuación)", tam=10.5)

        filas = []
        for f in res["detalle"]:
            pend = f["tipo"] == "pendiente"
            filas.append([(f["casilla"], "negrita"), (f["valor"], "pend" if pend else None),
                          (ORIGENES.get(f["tipo"], f["origen"]), None), (como(f["fuente"]), None),
                          (enlaces(f["fuente"]), "enlaces")])
        dibujar_tabla(lz, X0, ANCHO_UTIL, [("Casilla", 12, "izq"), ("Valor", 10, "cen"),
                                           ("Origen", 9, "izq"), ("Cómo se obtiene", 49, "izq"),
                                           ("Fuente (enlace)", 20, "izq")],
                      filas, cab_tam=7, celda_tam=6.6, pad_cab_v=1.3 * MM, pad_v=0.75 * MM,
                      repetir=repetir)
        lz.y += 2 * MM
        consultas = " · ".join(
            f"{c['fuente']}: {c['estado']}" + (f" {c['hora_utc'][-5:]}" if c["hora_utc"] else "")
            + (f" ({sin_url(c['detalle'])})" if c["detalle"] and len(c["detalle"]) < 70 else "")
            for c in res["consultas"])
        parrafo(lz, f"Consultas (hora UTC): {consultas}.", tam=6.8)
        for a in res["avisos"]:
            parrafo(lz, a, tam=6.8, col=ROJO, sangria="! ")
        for n in res["tabla"].get("notas", []):
            parrafo(lz, n, tam=6.8, sangria="· ")
        lz.y += 3 * MM
    parrafo(lz, "Herramienta de preparación de datos. No es asesoramiento financiero. Los CFD tienen "
                "un riesgo alto de pérdida.", tam=6.8, col=GRIS)


def pies(lz):
    total = len(lz.paginas)
    for n, ops in enumerate(lz.paginas, 1):
        lz.ops = ops
        base = ALTO - MARGEN_V + 7 * 0.2
        lz.texto_alineado(0, ANCHO, base, tabla.CREDITO, "cen", "cursiva", 7, GRIS)
        if total > 1:
            lz.texto_alineado(0, ANCHO - 15 * MM, base, f"Página {n} de {total}", "der", "normal",
                              6.5, GRIS)


def fecha_pdf(momento):
    return momento.strftime("D:%Y%m%d%H%M%SZ")


def escribir(lz, titulo, momento):
    objetos = []

    def obj(cuerpo):
        objetos.append(cuerpo)
        return len(objetos)

    obj(b"")  # 1 catálogo (se rellena al final)
    obj(b"")  # 2 páginas
    fuentes = {}
    for clave, base in (("F1", "Helvetica"), ("F2", "Helvetica-Bold"), ("F3", "Helvetica-Oblique")):
        fuentes[clave] = obj(f"<< /Type /Font /Subtype /Type1 /BaseFont /{base} "
                             "/Encoding /WinAnsiEncoding >>".encode())
    recursos = "<< /Font << " + " ".join(f"/{k} {v} 0 R" for k, v in fuentes.items()) + " >> >>"
    hijos = []
    for ops, anots in zip(lz.paginas, lz.enlaces):
        contenido = zlib.compress("\n".join(ops).encode("latin-1"))
        c = obj(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(contenido) + contenido
                + b"\nendstream")
        refs = []
        for x1, y1, x2, y2, url in anots:
            uri = url.encode("ascii", errors="ignore").replace(b"\\", b"").replace(b"(", b"%28") \
                .replace(b")", b"%29")
            refs.append(obj(b"<< /Type /Annot /Subtype /Link /Border [0 0 0] /Rect [%.2f %.2f %.2f "
                            b"%.2f] /A << /S /URI /URI (%s) >> >>" % (x1, y1, x2, y2, uri)))
        anotaciones = f" /Annots [{' '.join(f'{r} 0 R' for r in refs)}]" if refs else ""
        hijos.append(obj(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO:.2f} {ALTO:.2f}] "
                         f"/Resources {recursos} /Contents {c} 0 R{anotaciones} >>".encode()))
    objetos[0] = b"<< /Type /Catalog /Pages 2 0 R >>"
    objetos[1] = (f"<< /Type /Pages /Kids [{' '.join(f'{h} 0 R' for h in hijos)}] "
                  f"/Count {len(hijos)} >>").encode()
    info = obj(b"<< /Title <feff" + titulo.encode("utf-16-be").hex().encode()
               + b"> /Author (Kike Argandona) /Creator (" + f"{NOMBRE} {VERSION}".encode()
               + b") /CreationDate (" + fecha_pdf(momento).encode() + b") >>")

    salida = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    posiciones = []
    for i, cuerpo in enumerate(objetos, 1):
        posiciones.append(len(salida))
        salida += b"%d 0 obj\n" % i + cuerpo + b"\nendobj\n"
    xref = len(salida)
    salida += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objetos) + 1)
    for p in posiciones:
        salida += b"%010d 00000 n \n" % p
    salida += (b"trailer\n<< /Size %d /Root 1 0 R /Info %d 0 R >>\nstartxref\n%d\n%%%%EOF\n"
               % (len(objetos) + 1, info, xref))
    return bytes(salida)


def generar(resultados, momento=None):
    """PDF (bytes) con uno o varios resultados de instrumento.preparar()."""
    momento = momento or dt.datetime.now(dt.timezone.utc)
    lz = Lienzo()
    pagina_principal(lz, resultados)
    pagina_fuentes(lz, resultados, momento)
    pies(lz)
    return escribir(lz, tabla.TITULO, momento)


def nombre_archivo(resultados):
    claves = [tabla.clave_segura(r["simbolo"]) for r in resultados]
    base = "_".join(claves) if len(claves) <= 4 else f"{len(claves)}_simbolos"
    fecha = max(r["tabla"]["consulta"] for r in resultados)
    sufijo = "_INCOMPLETA" if any(r["pendientes"] for r in resultados) else ""
    broker = resultados[0]["perfil"]["broker"]
    return f"{base}_{broker}_{fecha}{sufijo}.pdf"
