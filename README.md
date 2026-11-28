# Instrumentos Darwinex para StrategyQuant X

[![pruebas](https://github.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x/actions/workflows/pruebas.yml/badge.svg)](https://github.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x/actions/workflows/pruebas.yml)

Skill de Claude Code que prepara, en PDF, la tabla de configuración de símbolos para **StrategyQuant X (build 143)** con el bróker **Darwinex**: Pip/Tick, Point Value, tick real, spread medio, comisión, swaps y triple swap. Cada dato lleva su fuente y su fecha, y cada cálculo su fórmula y sus entradas.

> **Spread (desde 2.4.0, 2026-11-28)**: Default Spread = **Spread medio de 30 días — 24 horas — Darwinex — muestreo automático ISQX cada 15 min — sin comisiones** ([reference/spread-slippage.md](reference/spread-slippage.md)). Una tarea programada de GitHub Actions ([spread-medio.yml](.github/workflows/spread-medio.yml)) lee el bid/ask de Darwinex cada 15 minutos y publica la media en la rama [`datos-spread`](https://github.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x/tree/datos-spread). Nadie escribe nada, y cubre forex, índices, metales, petróleo, gas y cripto. Con el mercado cerrado y la media aún pendiente, lleva de forma provisional el último spread antes del cierre (desde 2.5.0). El spread instantáneo de Darwinex se muestra aparte, solo como información.

> **Nuevo: aplicación independiente «Instrumentos SQX»** (en pruebas, carpeta [`app/`](app/README.md)). Hace lo mismo sin Claude Code, sin cuentas de IA ni claves API: una web instalable (PWA) para móvil y ordenador con un pequeño servidor en Python que consulta las fuentes, aplica las reglas de la skill, valida con `tabla.py` y genera el PDF. La skill sigue funcionando igual.

## Cómo se reparte el trabajo

| Quién | Qué hace |
|---|---|
| **Claude** (siguiendo `SKILL.md`) | Consulta las fuentes en vivo (tablas de Darwinex, BCE, documentación de StrategyQuant y, solo como información, el feed de precios), toma el spread medio automático con `tabla.py spread`, decide qué valor va en cada casilla y escribe el JSON del símbolo con sus fuentes. |
| **`scripts/tabla.py`** | Valida datos, fechas, tipos y fuentes; comprueba la coherencia (criterio y unidades del spread medio, comisión ida y vuelta, tick real, point value) y genera el PDF. Solo se conecta a internet en `tabla.py spread`, para descargar el spread medio automático. |
| **Tarea `spread-medio`** (GitHub Actions) | Cada 15 minutos mide el spread de todos los símbolos de Darwinex con el mercado abierto y publica la media de 30 días en la rama `datos-spread`. |
| **El usuario** | Revisa el PDF e introduce los valores en StrategyQuant a mano. La skill no modifica StrategyQuant ni MetaTrader ni opera. |

## Requisitos

- **Claude Code** con:
  - **Acceso web en vivo** para leer páginas sin caché: Firecrawl (`scrape` con `maxAge: 0`) o WebFetch. Sin él, la skill no puede obtener datos y lo dice.
  - **Bash** para ejecutar `python3`, `date -u` y `curl` (feed de precios, solo para el spread instantáneo informativo).
- **Python 3.8 o superior**, solo biblioteca estándar (sin `pip install`). Las pruebas se ejecutan en GitHub Actions con Python 3.8 a 3.13 en macOS, Windows y Linux (ver la insignia de CI).
- **Un navegador Chromium** para imprimir el PDF: Google Chrome, Microsoft Edge, Chromium o Brave. Se busca solo en las rutas habituales de macOS, Windows y Linux. Si no lo encuentra, indica la ruta con `--navegador RUTA` o con la variable `SQD_NAVEGADOR`.

## Instalación

1. Clona el repositorio en la carpeta de skills de Claude Code (para todos tus proyectos):
   ```bash
   git clone https://github.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x.git ~/.claude/skills/instrumentos-darwinex-para-strategyquant-x
   ```
   O dentro de `.claude/skills/` de un proyecto. Para actualizar: `git -C ~/.claude/skills/instrumentos-darwinex-para-strategyquant-x pull`.
2. Comprueba el entorno:
   ```bash
   python3 ~/.claude/skills/instrumentos-darwinex-para-strategyquant-x/scripts/tabla.py navegador   # navegador que se usará
   python3 ~/.claude/skills/instrumentos-darwinex-para-strategyquant-x/scripts/tabla.py perfil      # perfil activo
   ```
3. (Opcional) Ejecuta las pruebas: `cd ~/.claude/skills/instrumentos-darwinex-para-strategyquant-x && python3 -m unittest discover -s tests -v`.

## Uso

En Claude Code:

```
/instrumentos-darwinex-para-strategyquant-x NDX
prepárame la tabla de EURUSD, XAUUSD y USATECHIDXUSD
```

Claude investiga, rellena `~/strategyquant-darwinex-datos/tablas/<SÍMBOLO>.json` y ejecuta:

```bash
python3 -I scripts/tabla.py generar EURUSD XAUUSD NDX
```

El resultado es un único PDF con una fila por símbolo, en `~/strategyquant-darwinex-datos/tablas/`, más el acumulado `Tablas_Darwinex_todas.pdf`. Si alguna tabla guardada no es válida (por ejemplo, del formato antiguo v1), queda fuera del acumulado y el anterior se conserva como `Tablas_Darwinex_todas_anterior_<fecha_hora>.pdf`.

### Órdenes de `tabla.py`

| Orden | Para qué |
|---|---|
| `plantilla <SÍMBOLO> [--forzar]` | Crea el JSON vacío del símbolo. |
| `validar <SÍMBOLO…> [--estricto]` | Valida y dice si la tabla es **COMPLETA**, **INCOMPLETA** o **NO VÁLIDA**. |
| `generar <SÍMBOLO…>` | Valida y crea un PDF con todos los símbolos (no se genera si alguno es NO VÁLIDO). |
| `todas` | Regenera el PDF acumulado con todas las tablas válidas. |
| `migrar <SÍMBOLO…>` | Convierte un JSON del formato antiguo (v1) al v2 y guarda el original como `.json.v1`. |
| `perfil` · `navegador` · `rutas` | Muestran el perfil, el navegador y las carpetas que se usan. |

Opciones: `--perfil RUTA`, `--navegador RUTA`. Variables: `SQD_DATA_DIR` (carpeta de datos), `SQD_PERFIL`, `SQD_NAVEGADOR`.
Códigos de salida: `0` correcto · `1` tabla no válida (o incompleta con `--estricto`) · `2` error de uso o de entorno.

### Ejemplos

`examples/` contiene tablas reales consultadas el 2026-10-27, con el spread medio de Forex Benchmark del 2026-11-27. No las uses en StrategyQuant: spread y swaps cambian.

| Archivo | Muestra |
|---|---|
| `EURUSD.json` | Forex con comisión en EUR convertida a USD con el BCE (`5.59 aprox.`) y spread medio 0.42 |
| `NDX.json` | Índice con tick real 0.1 (tick value ÷ contrato); **INCOMPLETA**: se preparó antes del spread medio automático (con `tabla.py spread NDX` se completa) |
| `XAUUSD.json` | Comisión en porcentaje (0.0025 % por orden → 0.005) y spread medio 48.23 pips de 0.01 |
| `BTCUSD.json` | Tabla **INCOMPLETA**: datos `PENDIENTE DE VERIFICAR` con su motivo |

Para verlos en PDF:

```bash
mkdir -p /tmp/sqd-demo/tablas && cp examples/*.json /tmp/sqd-demo/tablas/
SQD_DATA_DIR=/tmp/sqd-demo python3 scripts/tabla.py generar EURUSD NDX XAUUSD BTCUSD
```

## Perfil y ajustes personales

`config/perfil.json` es el perfil predeterminado (el del autor): Darwinex, MT5, cuenta en USD, datos Dukascopy descargados con «SQ default» y clonados a «(EST+07) New York Trading hours, US DST». Sus **ajustes personales** son slippage 0, min distance 0, order size multiplier 1, order size step 0.01 y rollover 23:59. Son decisiones de configuración del autor, no datos del bróker.

Para usar los tuyos, copia el archivo a `~/strategyquant-darwinex-datos/perfil.json` (o usa `--perfil` / `SQD_PERFIL`) y cambia `ajustes_personales`. El script valida el perfil: order mult. y order step > 0, slippage y min dist. ≥ 0, rollover HH:MM real. El bróker debe ser Darwinex y la cuenta en USD (es lo que cubre la skill).

## Formato del PDF

Título «Configuración de símbolos de StrategyQuant para Darwinex», dos tablas («1. Configuración principal del instrumento» y «2. Comisiones, swaps y rollover»), bajo la primera el origen del spread de cada símbolo («Spread medio de 30 días — 24 horas — Darwinex — muestreo automático ISQX cada 15 min — sin comisiones», fecha de consulta y periodo; el instantáneo, aparte) y la firma «Skill created by Kike Argandona». Si hay datos pendientes, el nombre del archivo termina en `_INCOMPLETA`, aparece un aviso bajo el título y las casillas pendientes salen en rojo.

## Limitaciones

- **Lecturas del momento**: spread medio y swaps cambian; StrategyQuant aplica un valor fijo a todo el histórico.
- **Spread medio automático**: una muestra cada 15 minutos (Forex Benchmark promedia minuto a minuto), con el feed de precios que usa la web de Darwinex, que no está documentado. El muestreo empezó el 2026-11-28: hasta el 2026-12-27 la media cubre menos de 30 días (la ficha lo indica), y cada símbolo necesita 48 muestras (unas 12 horas de mercado) antes de tener valor. GitHub puede retrasar las tareas programadas y las desactiva si el repositorio pasa 60 días sin actividad: si eso pasa, el script avisa de que el periodo se ha quedado atrás.
- **Comisión ida y vuelta**: un administrador de StrategyQuant confirma que la comisión se aplica ida y vuelta, pero no hay página de documentación formal ni prueba en build 143. Ver `reference/verificacion-fuentes.md` para la prueba de una operación que lo cierra.
- **Point Value convertido** (« aprox.»): usa el tipo del BCE de un día; el tipo real cambia a lo largo del histórico.
- **Cripto**: Darwinex no publicaba su tabla de cripto el 2026-10-27; esos datos salen PENDIENTE DE VERIFICAR hasta comprobarlos en MT5.
- **Sistemas probados a mano**: macOS (Darwin 25.6, Python 3.9.6, Google Chrome 156). En Windows y Linux solo se ejecutan las pruebas automáticas de CI; la generación del PDF con un navegador real no se ha comprobado a mano en esos sistemas.
- **Spread instantáneo**: el feed de precios que usa la web de Darwinex (widgets.fxbluelabs.com) no está documentado y puede cambiar sin aviso. Solo da información; nunca va en Default Spread.
- **Disponibilidad de Darwinex**: la propia tabla de Darwinex indica (2026-11-26) que las cuentas de Forex y CFD no están disponibles para nuevos clientes minoristas residentes en España. Comprueba tu caso antes de usar estos datos.
- Solo Darwinex y cuenta en USD. Las guías de interfaz describen la build 143; la 144 añade importación directa desde MT5.
- El validador comprueba formato, fuentes y coherencia interna, **no** que el dato publicado por Darwinex sea correcto. La validación final sigue siendo MT5 → Observación del mercado → Especificación.

## Estructura

```
SKILL.md                 instrucciones para Claude
config/perfil.json       perfil predeterminado y ajustes personales
scripts/tabla.py         validador y generador de PDF
reference/               reglas de cada columna, formato del JSON, spread, horarios, verificación de fuentes
guias/                   descarga y clonado en build 143; control de coherencia
templates/confirmado.md  plantilla para guardar lo confirmado con capturas
examples/                tablas de ejemplo (2026-10-27)
tests/test_tabla.py      pruebas (unittest)
app/                     aplicación independiente «Instrumentos SQX» (PWA + servidor; ver app/README.md)
.github/workflows/       pruebas automáticas en GitHub Actions
LICENSE                  licencia MIT
```

## Autor y licencia

Autor: **Kike Argandona**. Se distribuye bajo la **licencia MIT**: puedes usarlo, copiarlo, modificarlo y redistribuirlo, también con fines comerciales, siempre que mantengas el aviso de copyright y el texto de la licencia. Se entrega «tal cual», sin garantía. Texto completo en [LICENSE](LICENSE).

Copyright (c) 2026 Kike Argandona

## Aviso

Herramienta de preparación de datos. No es asesoramiento financiero. Los CFD tienen un riesgo alto de pérdida.
