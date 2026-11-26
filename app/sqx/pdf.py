"""PDF sin dependencias (solo biblioteca estándar) para usar en un servidor sin navegador.

Página 1: la misma estructura que el PDF de la skill (scripts/tabla.py): título, aviso de tabla
incompleta, «1. Configuración principal del instrumento», «2. Comisiones, swaps y rollover», las
mismas columnas, anchos, posiciones y colores, y la firma. Se toman de tabla.py (T1, T2, T1_IZQ…).
Páginas siguientes (anexo): fuentes, fechas, fórmulas, perfil y ajustes personales, que en la skill
quedaban en el JSON y en la respuesta de Claude.

Fuentes tipográficas estándar de PDF (Helvetica ≈ Arial) con codificación WinAnsi (cp1252).
"""
import datetime as dt
import zlib

from . import NOMBRE, VERSION, tabla
from .metricas import HELVETICA, HELVETICA_BOLD

MM = 72 / 25.4
ANCHO, ALTO = 297 * MM, 210 * MM  # A4 apaisado
MARGEN_V = 12 * MM
AZUL, LINEA, FILA_IMPAR = "#2C4D76", "#7A93B2", "#F4F6FA"
ROJO, ROSA, GRIS = "#9C0006", "#FFE7E7", "#7F7F7F"
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
        self.paginas = []
        self.nueva_pagina()

    def nueva_pagina(self):
        self.ops = []
        self.paginas.append(self.ops)
        self.y = MARGEN_V

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


# ---------------------------------------------------------------- tablas

def dibujar_tabla(lz, x, ancho, columnas, filas, cab_tam=7, celda_tam=7, pad_cab_v=3.2 * MM,
                  pad_v=1.05 * MM, pad_h=1.2 * MM, repetir=None):
    """columnas: [(cabecera, peso, alineación)]; filas: [[(texto, estilo_celda)]].
    estilo_celda: None (normal, sin partir), "pend" (rojo, partible) o "partir" (normal, partible)."""
    total = sum(c[1] for c in columnas)
    anchos = [ancho * c[1] / total for c in columnas]

    def alto_lineas(n, tam):
        return n * tam * 1.15

    def cabecera():
        lineas = [envolver(c[0], "negrita", cab_tam, w - 2.6 * MM) for c, w in zip(columnas, anchos)]
        h = max(alto_lineas(len(ls), cab_tam) for ls in lineas) + 2 * pad_cab_v
        if lz.y + h > ALTO - MARGEN_V - 8 * MM:
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
        for (texto, est), (_, _, alin), w in zip(fila, columnas, anchos):
            tam = 6 if est == "pend" else celda_tam
            estilo = "negrita" if est == "pend" else "normal"
            ls = envolver(texto, estilo, tam, w - 2 * pad_h) if est in ("pend", "partir") else [texto]
            celdas.append((ls, tam, estilo, alin, est))
        h = max(alto_lineas(len(c[0]), c[1]) for c in celdas) + 2 * pad_v
        h = max(h, alto_lineas(1, celda_tam) + 2 * pad_v)
        if lz.y + h > ALTO - MARGEN_V - 8 * MM:
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
                lz.texto_alineado(cx + pad_h, w - 2 * pad_h, base + i * tam * 1.15, linea, alin,
                                  estilo, tam, ROJO if pend else "#000000")
            cx += w
        lz.y += h


def tabla_principal(lz, filas_pdf, cols, izq, ancho):
    columnas = [(cab, peso, al) for _, cab, peso, al in cols]
    filas = []
    for d in filas_pdf:
        fila = []
        for k, _, _, _ in cols:
            v = str(d.get(k, ""))
            fila.append((v, "pend" if tabla.es_pendiente(v) else None))
        filas.append(fila)
    dibujar_tabla(lz, ANCHO * izq / 100, ANCHO * ancho / 100, columnas, filas)


def titulo_h2(lz, texto, x=ANCHO * 0.031, tam=12):
    lz.texto(x, lz.y + tam * 0.93, texto, "negrita", tam, AZUL)
    lz.y += tam * 1.15 + 2 * MM


# ---------------------------------------------------------------- documento

def pagina_tablas(lz, filas_pdf, incompletas):
    """Réplica de html_doc() de tabla.py."""
    lz.texto_alineado(0, ANCHO, lz.y + 20 * 0.93, tabla.TITULO, "cen", "negrita", 20, AZUL)
    lz.y += 20 * 1.15 + 8 * MM
    if incompletas:
        aviso = ("TABLA INCOMPLETA · Hay datos «PENDIENTE DE VERIFICAR» en: "
                 f"{', '.join(incompletas)}. No uses esas filas en StrategyQuant hasta completarlas.")
        x, w = ANCHO * 0.08, ANCHO * 0.84
        ls = envolver(aviso, "negrita", 10, w - 3 * MM)
        lz.y -= 5 * MM
        h = len(ls) * 10 * 1.15 + 3 * MM
        lz.rect(x, lz.y, w, h, relleno=ROSA, borde=ROJO, grosor=0.75)
        for i, linea in enumerate(ls):
            lz.texto_alineado(x, w, lz.y + 1.5 * MM + 10 * 0.93 + i * 11.5, linea, "cen", "negrita",
                              10, ROJO)
        lz.y += h + 6 * MM
    titulo_h2(lz, "1. Configuración principal del instrumento")
    tabla_principal(lz, filas_pdf, tabla.T1, tabla.T1_IZQ, tabla.T1_ANCHO)
    lz.y += 8 * MM
    titulo_h2(lz, "2. Comisiones, swaps y rollover")
    tabla_principal(lz, filas_pdf, tabla.T2, tabla.T2_IZQ, tabla.T2_ANCHO)


def parrafo(lz, texto, x, ancho, estilo="normal", tam=8, col="#000000", sangria=""):
    sangria_w = ancho_texto(sangria, estilo, tam)
    for i, linea in enumerate(envolver(texto, estilo, tam, ancho - sangria_w)):
        if lz.y + tam * 1.3 > ALTO - MARGEN_V - 8 * MM:
            lz.nueva_pagina()
        if i == 0 and sangria:
            lz.texto(x, lz.y + tam * 0.93, sangria, estilo, tam, col)
        lz.texto(x + sangria_w, lz.y + tam * 0.93, linea, estilo, tam, col)
        lz.y += tam * 1.3


def anexo(lz, resultados):
    x, w = 15 * MM, ANCHO - 30 * MM
    lz.nueva_pagina()
    lz.texto(x, lz.y + 14 * 0.93, "Anexo: fuentes, fechas, cálculos y ajustes", "negrita", 14, AZUL)
    lz.y += 14 * 1.15 + 3 * MM
    perfil = resultados[0]["perfil"]
    datos = perfil["datos"]
    parrafo(lz, f"Generado con {NOMBRE} {VERSION}. Cada valor de la página 1 sale de una fuente "
                "consultada en el momento indicado, de un cálculo con sus entradas o de una regla de "
                "formato de la skill. Los ajustes personales son decisiones de configuración del "
                "perfil, no datos del bróker.", x, w)
    parrafo(lz, f"Perfil: {perfil['nombre']} · Bróker {perfil['broker']} · {perfil['plataforma']} · "
                f"cuenta en {perfil['divisa_cuenta']} · datos {datos['proveedor']} descargados con "
                f"«{datos['broker_profile_descarga']}» y clonados a «{datos['zona_clon']}».", x, w,
            "negrita")
    lz.y += 2 * MM

    for res in resultados:
        if lz.y > ALTO - 60 * MM:
            lz.nueva_pagina()
        t = res["tabla"]
        destino = res["ticker_darwinex"]
        cab = (f"{res['simbolo']}" + (f" → Darwinex {destino}" if destino != res["simbolo"] else "")
               + f" ({res['clase']}) · {res['estado']}")
        titulo_h2(lz, cab, x, 11)
        parrafo(lz, f"Consulta: {res['consulta_utc']} UTC (fecha de la tabla: {t['consulta']}).", x, w)
        lz.y += 1 * MM

        def repetir_titulo(cab=cab):
            titulo_h2(lz, f"{cab} (continuación)", x, 11)

        filas = []
        for f in res["detalle"]:
            pend = f["tipo"] == "pendiente"
            filas.append([(f["casilla"], "partir"), (f["valor"], "pend" if pend else "partir"),
                          (f["origen"], "partir"), (f["explicacion"], "partir")])
        dibujar_tabla(lz, x, w, [("Casilla", 14, "izq"), ("Valor", 11, "cen"), ("Origen", 11, "izq"),
                                 ("Fuente, fecha y fórmula", 64, "izq")], filas, cab_tam=7,
                      celda_tam=6.5, pad_cab_v=1.6 * MM, pad_v=0.9 * MM, repetir=repetir_titulo)
        lz.y += 3 * MM
        consultas = [[(c["fuente"], "partir"), (c["url"], "partir"), (c["hora_utc"] or "—", None),
                      (c["estado"] + (f" · {c['detalle']}" if c["detalle"] else ""), "partir")]
                     for c in res["consultas"]]
        if consultas:
            dibujar_tabla(lz, x, w, [("Fuente consultada", 18, "izq"), ("Dirección", 37, "izq"),
                                     ("Hora UTC", 11, "cen"), ("Resultado", 34, "izq")], consultas,
                          cab_tam=7, celda_tam=6.5, pad_cab_v=1.6 * MM, pad_v=0.9 * MM,
                          repetir=repetir_titulo)
            lz.y += 3 * MM
        for a in res["avisos"]:
            parrafo(lz, a, x, w, tam=7.5, col=ROJO, sangria="! ")
        for n in t.get("notas", []):
            parrafo(lz, n, x, w, tam=7.5, sangria="· ")
        lz.y += 4 * MM

    if lz.y > ALTO - 45 * MM:
        lz.nueva_pagina()
    titulo_h2(lz, "Antes de usar estos datos", x, 11)
    for texto in (
            "Compara cada valor con MT5 → Observación del mercado → botón derecho → Especificación. "
            "El validador comprueba formato, fuentes y coherencia, no que el dato publicado sea correcto.",
            "Comisión ida y vuelta: Darwinex publica la comisión por orden y un administrador de "
            "StrategyQuant indica que SQ la aplica ida y vuelta. No hay confirmación formal para la "
            "build 143 (reference/verificacion-fuentes.md): pendiente de una prueba de una operación.",
            "Esta aplicación no se ha validado dentro de StrategyQuant X: introduce los valores a mano y "
            "revísalos.",
            "Herramienta de preparación de datos. No es asesoramiento financiero. Los CFD tienen un "
            "riesgo alto de pérdida."):
        parrafo(lz, texto, x, w, tam=7.5, sangria="· ")


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
    for ops in lz.paginas:
        contenido = zlib.compress("\n".join(ops).encode("latin-1"))
        c = obj(b"<< /Length %d /Filter /FlateDecode >>\nstream\n" % len(contenido) + contenido
                + b"\nendstream")
        hijos.append(obj(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {ANCHO:.2f} {ALTO:.2f}] "
                         f"/Resources {recursos} /Contents {c} 0 R >>".encode()))
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
    filas = [r["fila_pdf"] for r in resultados]
    incompletas = [r["tabla"]["simbolo"] for r in resultados if r["pendientes"]]
    pagina_tablas(lz, filas, incompletas)
    anexo(lz, resultados)
    pies(lz)
    return escribir(lz, tabla.TITULO, momento)


def nombre_archivo(resultados):
    claves = [tabla.clave_segura(r["simbolo"]) for r in resultados]
    base = "_".join(claves) if len(claves) <= 4 else f"{len(claves)}_simbolos"
    fecha = max(r["tabla"]["consulta"] for r in resultados)
    sufijo = "_INCOMPLETA" if any(r["pendientes"] for r in resultados) else ""
    broker = resultados[0]["perfil"]["broker"]
    return f"{base}_{broker}_{fecha}{sufijo}.pdf"
