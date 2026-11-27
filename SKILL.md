---
name: instrumentos-darwinex-para-strategyquant-x
description: "Instrumentos Darwinex para StrategyQuant X. Prepara en PDF la tabla de configuración de uno o varios símbolos para StrategyQuant X (build 143) con Darwinex, con datos reales, fuentes y fecha. Perfil predeterminado: MT5, cuenta en USD, datos Dukascopy clonados a «(EST+07) New York Trading hours, US DST». Úsala cuando alguien diga «prepárame la tabla de <símbolo>», pida la tabla, ficha o datos de un símbolo o activo para StrategyQuant con Darwinex, o quiera calcular point value, pip/tick, tick real, spread medio, comisiones o swaps de un símbolo de Darwinex. También para descargar datos de Dukascopy, clonarlos a «(EST+07) New York Trading hours, US DST» o comprobar la coherencia antes de un custom project."
argument-hint: [símbolo, p. ej. USATECHIDXUSD]
---

# Instrumentos Darwinex para StrategyQuant X: tabla de un símbolo

El usuario pide «prepárame la tabla de <símbolo>» (o de varios). **Tú** consultas las fuentes y preparas los datos en un JSON; **el script** valida datos y fuentes y genera el PDF. El usuario lo pasa a StrategyQuant X a mano. Nunca ejecutes operaciones financieras ni modifiques StrategyQuant, MetaTrader o sus archivos.

Símbolo pedido: $ARGUMENTS

## Qué necesitas
- **Web en vivo**: leer páginas sin caché (Firecrawl `scrape` con `maxAge: 0`, o WebFetch) y, si hace falta, `curl` al feed de precios (spread instantáneo, solo informativo). Sin acceso web no hay datos: dilo y no rellenes nada.
- **Bash** con `python3` (3.8+, solo biblioteca estándar) y `date -u`.
- Un navegador Chromium (Chrome, Edge, Chromium o Brave) para imprimir el PDF. Si el script no lo encuentra, pide la ruta y usa `--navegador`.

## Rutas
- `SK` = carpeta de esta skill (la «Base directory» que aparece al cargarla).
- Herramienta: `python3 -I "SK/scripts/tabla.py" <orden>`: `plantilla`, `validar`, `generar`, `todas`, `migrar`, `perfil`, `navegador`, `rutas`.
- `DATA` = `~/strategyquant-darwinex-datos/` (o `SQD_DATA_DIR`). Tablas en `DATA/tablas/`: `<SÍMBOLO>.json` (datos y fuentes), `<SÍMBOLOS>_Darwinex_<fecha>[_INCOMPLETA].pdf` y el acumulado `Tablas_Darwinex_todas.pdf`. **La entrega es solo PDF.**
- Reglas de cada columna y reglas prácticas: [reference/tabla-reglas.md](reference/tabla-reglas.md). Formato del JSON y de las fuentes: [reference/formato-json.md](reference/formato-json.md). Spread: [reference/spread-slippage.md](reference/spread-slippage.md). Qué está verificado en la documentación oficial y qué no: [reference/verificacion-fuentes.md](reference/verificacion-fuentes.md).

## Reglas fijas
- **Solo preguntas el símbolo** (si no lo ha escrito) y, si Forex Benchmark lo cubre, **su spread medio** (o una captura de la tabla): ver «Spread medio» abajo.
- **No pidas, revises ni compares los símbolos o instrumentos que el usuario ya tiene en StrategyQuant**, salvo que lo pida (p. ej., un custom project).
- **Perfil** (`tabla.py perfil`): bróker, plataforma, divisa, datos y **ajustes personales** (slippage, min dist., order mult., order step, rollover). Son decisiones de configuración del usuario, no datos del bróker: los pone el script y no van en el JSON. Predeterminado: Darwinex · MT5 · USD · Dukascopy (SQ default) clonado a «(EST+07) New York Trading hours, US DST» · 0 · 0 · 1 · 0.01 · 23:59.
- **Sin inventar nada.** Cada valor sale de una fuente oficial o fiable consultada hoy (Darwinex, StrategyQuant, BCE) o de un cálculo con sus entradas y fuentes. Las convenciones de tabla-reglas.md fijan el formato, no los valores: no reutilices valores de tablas anteriores ni de `examples/`.
- **Tick real**: `No Pip/Tick` es el tick mínimo del instrumento. `Pip/Tick ÷ 10` solo en forex (Darwinex cotiza con 5 decimales, 3 en JPY). En el resto: tick value ÷ contrato.
- **Comisión**: Darwinex la publica **por orden**; StrategyQuant la aplica **ida y vuelta**. Comisión en SQ = comisión por orden × 2, registrada como cálculo con la entrada `comision_por_orden`. Nunca la dupliques dos veces ni copies la de por orden.
- **Triple swap**: el día que indique la nota de la tabla de Darwinex de esa clase.
- **Spread medio** (criterio de la academia): Default Spread = **Spread medio de 30 días — 24 horas — Darwinex — Forex Benchmark — sin comisiones**, fuente `promedio`. Lo copia el usuario de https://forexbenchmark.com/brokers/historic_spreads/ (Darwinex · 24 hours · 30 days · «Add commission to spread» sin marcar): sus condiciones de uso no permiten consultarlo de otra forma, así que no uses su endpoint interno. Solo cubre forex entre USD, EUR, JPY, GBP, CAD, AUD, NZD y CHF, y XAUUSD; el resto queda PENDIENTE con las alternativas de spread-slippage.md, **sin sustituir la fuente**. El spread instantáneo nunca va en Default Spread: si lo anotas, va en `spread_instantaneo`. El rollover (23:59) no tiene que ver con el periodo del spread.
- Si falta evidencia o las fuentes discrepan: `PENDIENTE DE VERIFICAR` con una fuente `{"tipo": "pendiente", "motivo": …}`. La tabla queda **INCOMPLETA** y el PDF lo indica. Nunca un valor supuesto.

## Paso 1: investigar
1. Identifica el ticker de Darwinex equivalente (mismo subyacente y divisa) y su tabla (forex, índices, materias primas, cripto): tabla-reglas.md.
2. Lee esa tabla **sin caché**: contrato, pip o tick value, swaps, comisión por orden y nota del triple swap. Anota fecha y hora UTC (`date -u`).
3. Spread medio: sigue spread-slippage.md. Si el símbolo está cubierto, pide al usuario el valor de Forex Benchmark y, si la conoce, la fecha final del periodo; anota la hora UTC en que te lo da. Si no está cubierto, Default Spread queda PENDIENTE con las alternativas. Opcional: el spread instantáneo («Current spread» o feed), solo como información.
4. Si hay que convertir a USD, usa el tipo del BCE de su último día publicado, con su fecha.

## Paso 2: rellenar, validar y generar
1. `tabla.py plantilla <SÍMBOLO>` crea `DATA/tablas/<SÍMBOLO>.json` (si existe, actualízalo con los datos de hoy o usa `--forzar`). Si es de formato antiguo, `tabla.py migrar <SÍMBOLO>` y completa lo que indique.
2. Rellena cada campo y su fuente según formato-json.md: `dato` (url + fecha), `promedio` (solo Default Spread: criterio de Forex Benchmark, fecha, hora_utc, lectura y pip_fuente), `observado` (solo `spread_instantaneo`), `calculo` (fórmula + entradas con valor y fuente), `regla` (regla + referencia) o `pendiente` (motivo). Punto decimal; « aprox.» solo en valores convertidos de divisa.
3. `tabla.py generar <SÍMBOLO> [<SÍMBOLO2> …]`: valida y crea **un único PDF** con todos los símbolos en el orden pedido, las dos tablas y la firma «Skill created by Kike Argandona». Actualiza el acumulado. Si hay ✗, corrígelos: el PDF no se genera con errores. No cambies el formato del PDF.

## Entrega (breve)
1. Las dos tablas en Markdown, con las mismas columnas que el PDF, y el estado: **COMPLETA** o **INCOMPLETA** (con la lista de pendientes).
2. Rutas completas del PDF y del acumulado.
3. Una línea por dato convertido o calculado que convenga saber (p. ej., «Point Value 634 aprox. = 100000 JPY ÷ USDJPY del BCE»), por discrepancia o pendiente; el spread como «Spread medio de 30 días — 24 horas — Darwinex — Forex Benchmark — sin comisiones», con la fecha de consulta y el periodo, y un recordatorio de que los swaps son lecturas del momento.
4. De dónde sale cada dato (las fuentes quedan en el JSON, no en el PDF).

Guías opcionales, solo si las piden: [descarga-y-clonacion.md](guias/descarga-y-clonacion.md) (Dukascopy y clon a EST+07) y [coherencia.md](guias/coherencia.md) (antes del custom project). No inventes pantallas de build 143: donde la guía marca [captura], pide esa captura.
