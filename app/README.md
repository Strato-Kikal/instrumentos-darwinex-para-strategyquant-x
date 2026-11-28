# Instrumentos SQX

Aplicación web instalable (PWA) que prepara los datos de un instrumento de **Darwinex** para **StrategyQuant X (build 143)** y los entrega en PDF. Funciona en el móvil y en el ordenador, sin Claude Code, sin cuentas de IA y sin claves API.

Se basa en la skill «Instrumentos Darwinex para StrategyQuant X» de este repositorio, que **no se modifica**: la app importa `scripts/tabla.py` (perfil, reglas de validación, columnas y formato del PDF) y aplica las reglas de `reference/`.

> Estado: versión 2.5.0 (Default Spread = spread medio automático de Darwinex, sin escribir nada; con el mercado cerrado y la media pendiente, el último spread antes del cierre), para usar en local (ordenador, y móvil por la misma Wi-Fi). No está publicada en ningún alojamiento.

## Descargar

Descarga: [instrumentos-sqx-2.5.0.zip](https://github.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x/releases/download/v2.5.0/instrumentos-sqx-2.5.0.zip) (todas las versiones en [Releases](https://github.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x/releases)).

Descomprímelo, abre una terminal en la carpeta y ejecuta `python3 app/servidor.py` (detalles en «Ejecutarla en local»).

## Qué hace

1. Escribes un símbolo (`EURUSD`, `NDX`, `XAUUSD`… o el equivalente de Dukascopy `USATECHIDXUSD`) y pulsas **Obtener datos**. No hay que escribir nada más.
2. El servidor de la app consulta en ese momento:
   - **Darwinex**: el JSON que alimenta sus tablas de condiciones (contrato, tick, tick value, swaps, comisión, divisa, día de triple swap).
   - **Spread medio**: `medias.json` de la rama `datos-spread`, que publica sola cada 15 minutos la tarea de GitHub Actions `spread-medio.yml` (bid/ask de Darwinex con el mercado abierto, media de 30 días).
   - **Spread instantáneo** (solo informativo): el feed de precios que usa la propia web de Darwinex (widgets.fxbluelabs.com). Nunca va en Default Spread.
   - **BCE**: tipos de referencia, solo si hay que convertir a USD.
   - **help.darwinex.com/execution-costs**: comprueba que la comisión se sigue publicando por orden.
3. Aplica las reglas de la skill, registra cada valor con su fuente y lo valida con `tabla.validar()`. Lo que no tiene evidencia queda **PENDIENTE DE VERIFICAR**.
4. Muestra los valores (con su origen: dato del bróker, spread medio de 30 días, lectura instantánea informativa, cálculo, regla o ajuste personal) y el botón **Descargar PDF**.

**Default Spread** = **Spread medio de 30 días — 24 horas — Darwinex — muestreo automático ISQX cada 15 min — sin comisiones** (reglas en [reference/spread-slippage.md](../reference/spread-slippage.md)). Cubre forex, índices, metales, petróleo, gas y cripto. Cada símbolo necesita 48 muestras (unas 12 horas de mercado abierto) antes de tener valor; mientras tanto queda **PENDIENTE DE VERIFICAR** y se rellena solo. Si el mercado está cerrado, en vez de quedar pendiente lleva, de forma provisional, el **último spread antes del cierre** («X pips · último spread · mercado cerrado»), válido hasta que el mercado reabra. El muestreo empezó el 2026-11-28: hasta el 2026-12-27 la media cubre menos de 30 días y la ficha lo indica. Antes (2.3.0) el valor se copiaba a mano de Forex Benchmark, cuyas condiciones de uso no permiten consultarlo de forma automática.

El PDF (A4 apaisado) está pensado para rellenar StrategyQuant X directamente:

- **Página 1**: estado («Datos completos · pendiente de validar en SQX» o «Datos incompletos · faltan: …»), tabla «1. Configuración principal del instrumento» y tabla «2. Comisiones, swaps y rollover» con los nombres de las casillas de SQX (Pip/Tick Size, Pip/Tick Step, Tipo de swap…) y sus unidades: Default Spread como «X pips · medio 30 días · 24 h» y, debajo de la tabla, «Spread medio de 30 días — 24 horas — Darwinex — muestreo automático ISQX cada 15 min — sin comisiones» con la fecha de consulta, el periodo de los datos (desde, hasta y muestras) y, aparte, el spread instantáneo (solo informativo); comisión como «X USD por lote, ida y vuelta», swaps en USD por lote y día. Separa el rollover de SQX (ajuste del perfil, con la zona horaria de los datos clonados) de la hora a la que Darwinex cobra el swap (17:00 Nueva York = 00:00 del servidor MT5). Debajo, las comprobaciones que faltan dentro de SQX (spread y comisión separados, comisión de 1 lote, operación que cruce el rollover, triple swap).
- **Página 2**: fuentes y cálculos de cada casilla (origen, fórmula con sus entradas y fechas) con enlaces clicables cortos, horas de consulta, perfil y avisos. Si hay varios símbolos o mucho texto, se añaden páginas.

Alcance, igual que la skill: Darwinex, cuenta en USD, forex, índices, materias primas/metales y cripto. Acciones, ETF y futuros dan un mensaje de «fuera de alcance».

## Arquitectura elegida y por qué

**PWA + servidor pequeño en Python (solo biblioteca estándar).**

Comprobado el 2026-11-26 desde un navegador:

| Fuente | ¿La puede leer el navegador directamente? |
|---|---|
| Darwinex (`/graphics/spreads`) | **No.** Con una cabecera `Origin` de otra web responde `403 Invalid CORS request`. Además, la página de condiciones muestra a los visitantes de España un aviso de bloqueo (CNMV); el JSON sí respondió desde España sin `Origin`. |
| BCE (XML diario) | **No.** No envía cabeceras CORS. |
| Feed de spread (fxbluelabs) | Sí (`Access-Control-Allow-Origin: *`). |
| Spread medio (`raw.githubusercontent.com`, rama `datos-spread`) | Sí, pero se consulta desde el servidor como el resto. |
| Forex Benchmark | No se consulta: no tiene API y sus condiciones de uso no permiten acceder por otro medio que su web (comprobado el 2026-11-27). |
| help.darwinex.com | Sin CORS para lectura desde otra web. |

Una app solo de navegador no puede obtener los datos del bróker, así que hace falta un servidor que haga las consultas. Ese servidor, de paso, sirve la interfaz y genera el PDF. Ventajas:

- Reutiliza `tabla.py` de la skill en lugar de reescribir las reglas en otro lenguaje.
- Sin dependencias: Python 3.8+ y nada más (no necesita `pip`, ni Chrome en el servidor: el PDF se escribe directamente).
- Una sola URL sirve para móvil y ordenador; la PWA permite «instalarla» con icono propio.

Alternativas descartadas: app nativa (tiendas, cuentas de desarrollador, más mantenimiento); solo navegador (bloqueada por CORS); generar el PDF con Chrome en el servidor (exige instalar Chrome en el alojamiento y más memoria).

## Ejecutarla en local

Requisitos: Python 3.8 o superior y conexión a Internet.

```bash
cd instrumentos-darwinex-para-strategyquant-x
python3 app/servidor.py
```

Abre `http://127.0.0.1:8000` en el navegador del ordenador.

Para usarla también desde el **móvil en la misma Wi-Fi**:

```bash
python3 app/servidor.py --red
```

El servidor muestra la dirección (por ejemplo, `http://192.168.1.20:8000`). macOS puede pedir permiso para aceptar conexiones entrantes. Para pararlo: `Ctrl+C`.

Opciones: `--puerto 9000`, `--host`. Variables: `PORT` (alojamientos), `SQD_PERFIL` (perfil JSON de la skill; por defecto `~/strategyquant-darwinex-datos/perfil.json` si existe, si no `config/perfil.json`).

También puedes abrir directamente un símbolo: `http://127.0.0.1:8000/?simbolo=NDX`.

## Abrirla o instalarla en cada dispositivo

La instalación como app (icono «Instrumentos SQX», ventana propia) **requiere HTTPS**, salvo en el propio ordenador con `127.0.0.1`/`localhost`. Con `http://192.168.x.x` desde el móvil la app funciona en el navegador, pero no se instala como PWA (solo como acceso directo).

| Dispositivo | Abrir | Instalar (con HTTPS) |
|---|---|---|
| **Ordenador: Chrome o Edge** (Windows, macOS, Linux) | Abrir la URL | Icono de instalar en la barra de direcciones, o menú ⋮ → «Instalar Instrumentos SQX». Funciona ya con `http://127.0.0.1:8000`. |
| **Mac: Safari** (macOS 14 o posterior) | Abrir la URL | Archivo → «Añadir al Dock». |
| **Ordenador: Firefox** | Abrir la URL | Firefox de escritorio no instala PWA; se usa como página web. |
| **Android: Chrome** | Abrir la URL | Menú ⋮ → «Instalar aplicación» o «Añadir a pantalla de inicio». |
| **iPhone / iPad: Safari** | Abrir la URL | Botón Compartir → «Añadir a pantalla de inicio». |

La etiqueta del icono es «Instrumentos SQX». En pantallas pequeñas el sistema puede recortarla.

La app necesita conexión: sin Internet, la interfaz abre (si está instalada) y avisa de que no puede consultar las fuentes. Los datos nunca se guardan en caché.

## Alojamiento (si más adelante se publica)

No se ha contratado ni publicado nada. Requisitos:

- Python 3.8+ y un proceso que quede escuchando (`python3 app/servidor.py`, puerto en `PORT`).
- Salida HTTPS hacia `www.darwinex.com`, `help.darwinex.com`, `widgets.fxbluelabs.com` y `www.ecb.europa.eu`. Algunos planes gratuitos solo permiten salir a una lista de dominios: compruébalo antes.
- HTTPS delante (lo suelen dar los propios alojamientos) para que se pueda instalar como PWA.
- Memoria y CPU mínimas: cada consulta descarga ~0,5 MB de Darwinex (se guarda 60 s) y genera un PDF de ~12 KB.

Opciones y costes orientativos (comprueba las condiciones actuales antes de elegir; no las he verificado hoy):

- **Tu propio ordenador o una Raspberry Pi** en casa: sin coste, pero solo accesible en tu red salvo que configures un túnel o el router.
- **Plan gratuito de un PaaS** (Render, Koyeb, Fly.io, Google Cloud Run…): suelen dormir la app tras unos minutos sin uso (primera consulta lenta) y algunos piden tarjeta.
- **VPS pequeño**: del orden de 4-6 € al mes.

Antes de publicarla para otros usuarios:
- El endpoint de Darwinex y el feed de spread **no están documentados** como API pública: pueden cambiar sin aviso. Revisa los términos de uso de Darwinex. La app limita a 20 consultas por minuto e IP.
- Darwinex indica que no ofrece CFD a nuevos clientes minoristas residentes en España.

## Qué hacía Claude y qué hace ahora el código

| Tarea | En la skill | En la app |
|---|---|---|
| Identificar el ticker y la clase | Claude | `sqx/instrumento.py` (`buscar`, equivalencias de Dukascopy comprobadas) |
| Leer las tablas de Darwinex | Claude con Firecrawl/WebFetch | `sqx/fuentes.py` (JSON de Darwinex) |
| Spread medio (Default Spread) | `tabla.py spread` (muestreo automático) | `sqx/fuentes.py` + `tabla.spread_desde_medias` (muestreo automático, `sqx/muestreo.py`) |
| Spread instantáneo (informativo) | Claude (tabla o `curl` al feed) | `sqx/fuentes.py` (feed de precios) |
| Convertir a USD con el BCE | Claude | `sqx/instrumento.py` (`usd_por`) |
| Aplicar reglas (pip, tick real, comisión × 2, triple swap…) | Claude con `reference/` | `sqx/instrumento.py` |
| Registrar fuentes (esquema 3) | Claude | `sqx/instrumento.py` |
| Validar | `tabla.py` | `tabla.py` (el mismo código) |
| PDF | `tabla.py` + Chrome | `sqx/pdf.py` (página 1 para SQX + página de fuentes) |
| Resumen de fuentes para el usuario | Respuesta de Claude | Pantalla de resultados y página 2 del PDF |

Decisiones conservadoras (para no inventar valores):
- **Triple swap**: se usa el código `tripleSwapDay` de Darwinex solo si coincide con la nota publicada de su clase (forex miércoles, USDCAD jueves, índices viernes, metales miércoles; notas leídas el 2026-11-26). XTIUSD y XNGUSD tienen nota propia y quedan pendientes. Cripto no tiene nota: pendiente.
- **Swaps de cripto**: Darwinex no explica su unidad en la tabla: pendientes.
- **Pip/Tick Step**: si `tick value ÷ contrato` no coincide con el `tickSize` de Darwinex, queda pendiente (hoy ocurre con NI225).
- **Comisión**: solo se calcula si la página de costes de Darwinex sigue diciendo «displayed per order… 2 orders».
- Las referencias que no se consultan en cada uso (definición de Point value en el foro de StrategyQuant) llevan su fecha real de verificación (2026-10-27), no la de hoy.

## Pruebas

```bash
python3 -m unittest discover -s app/tests -v   # app (58 pruebas, sin red)
python3 -m unittest discover -s tests -v       # skill (82 pruebas)
```

Las pruebas de la app usan respuestas reales guardadas el 2026-11-26 (`app/tests/datos/`), solo como material de prueba, y un `medias.json` con valores sintéticos (`apoyo.py`). Cubren: EURUSD, USDJPY, USDCAD, GBPJPY, NDX, GDAXI, NI225, XAUUSD, XTIUSD, BTCUSD y USATECHIDXUSD; símbolos desconocidos, fuera de alcance y mal escritos; datos incompletos o contradictorios de Darwinex; spread medio automático (criterio, periodo corto, pocas muestras, símbolo sin datos, archivo caído o dañado) y el muestreo (horarios de Nueva York y Londres, fines de semana, cotizaciones repetidas, ventana de 30 días, cambio de pip, ronda completa en disco); caída de Darwinex, del feed de precios, del BCE y de la página de costes; respuestas dañadas; errores de conexión; PDF; servidor, rutas y límite de consultas.

## Estructura

```
app/
  servidor.py          servidor HTTP (interfaz + API)
  sqx/fuentes.py       consulta de fuentes en vivo
  sqx/instrumento.py   transformación de datos y reglas (antes las aplicaba Claude)
  sqx/muestreo.py      spread medio automático (lo ejecuta muestreo_spread.py cada 15 min en GitHub)
  muestreo_spread.py   una ronda del muestreo (tarea .github/workflows/spread-medio.yml)
  sqx/pdf.py           PDF sin dependencias (página 1 para SQX + fuentes y cálculos)
  sqx/metricas.py      anchos de Helvetica para el PDF
  web/                 PWA: index.html, app.js, estilos.css, manifest, service worker, iconos
  tests/               pruebas y datos de prueba
```

## Autor y licencia

Basada en la skill de **Kike Argandona**. Licencia **MIT** (ver [LICENSE](../LICENSE)). Copyright (c) 2026 Kike Argandona.

Herramienta de preparación de datos. No es asesoramiento financiero. Los CFD tienen un riesgo alto de pérdida. La app no se ha validado dentro de StrategyQuant X: introduce los valores a mano y compáralos con MT5 → Especificación.
