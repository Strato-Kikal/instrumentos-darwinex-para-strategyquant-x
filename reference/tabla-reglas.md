# Cómo se rellena cada columna de la tabla

Formato: el de las dos tablas que genera `scripts/tabla.py`. Las convenciones de abajo fijan el formato, **nunca los valores**: spreads, swaps y tipos de cambio se consultan de nuevo en cada tabla.

Todas las cifras van en el JSON con **punto decimal**. El sufijo « aprox.» marca un valor convertido a USD con un tipo de cambio (p. ej., «634 aprox.»).

## Reglas prácticas

Cada regla se apoya en una fuente oficial de [verificacion-fuentes.md](verificacion-fuentes.md). Si una fuente oficial actual dice otra cosa, manda la fuente: deja la casilla en PENDIENTE DE VERIFICAR y anótalo.

| Regla | Cómo se aplica | Base |
|---|---|---|
| Punto decimal | En StrategyQuant y en el JSON, siempre punto: `0.01`, nunca `0,01`. | Formato del script |
| Spread medio | Default Spread = Spread medio de 30 días — 24 horas — Darwinex — Forex Benchmark — sin comisiones ([spread-slippage.md](spread-slippage.md)). Lo copia el usuario; sin dato verificable, PENDIENTE con alternativas. El instantáneo es solo informativo. | Criterio de la academia (2026-11-27) |
| Spread en pips | SQ pide el spread en pips de Pip/Tick. MT5 lo muestra en puntos (1 punto = 1 tick). Pips = puntos × No Pip/Tick ÷ Pip/Tick. Si Pip/Tick y No Pip/Tick coinciden, el número no cambia; si el tick es 10 veces menor, se divide entre 10, y así sucesivamente. Ejemplo del foro de SQ: 41 puntos en GBPJPY → 4.1. | Doc data-settings de SQ; foro de SQ |
| Comisión | Por orden de Darwinex × 2, en USD (ver Tabla 2). | help.darwinex.com/execution-costs; foro de SQ |
| Modelo de comisión | «Comisión en porcentaje» cuando la tabla de Darwinex da la comisión como % del valor de la orden; si no, «En función del tamaño». | Tablas de Darwinex |
| Triple swap | El día que indique la nota de la tabla de Darwinex de esa clase (ver Tabla 2). | Tablas de Darwinex |
| Todo en USD | Point Value, comisión y swaps van en USD, la divisa de la cuenta del perfil. Si el activo cotiza en otra divisa, convierte con el BCE (ver «Conversiones a USD»). | Doc data-settings de SQ (swap «money»); perfil |
| Mismo mercado | USATECHIDXUSD (Dukascopy) y NDX (Darwinex) son el mismo mercado, el Nasdaq 100 (ver «Correspondencia de símbolos»). | Tablas de Darwinex |
| Lecturas del momento | Spread medio, swaps y tipos de cambio cambian: se consultan de nuevo en cada tabla. | — |
| Revisión final | Antes de construir estrategias, compara cada símbolo con MT5 → Observación del mercado → botón derecho → Especificación. | — |

Convenciones de la skill (formato, no valores): Pip/Tick forex 0.0001 (JPY 0.01), índices 1, XAUUSD 0.01, XAGUSD 0.001, BTCUSD 1; No Pip/Tick = **tick real** (forex = Pip/Tick ÷ 10; habituales en Darwinex: NDX 0.1, GDAXI 0.1, WS30 1, XAUUSD 0.01, XAGUSD 0.001, BTCUSD 0.01, que se vuelven a comprobar en cada tabla); «aprox.» en valores convertidos; si falta un dato, PENDIENTE DE VERIFICAR.

## Correspondencia de símbolos Dukascopy → Darwinex

El símbolo que pide el usuario puede ser el de Dukascopy. Busca el ticker equivalente en las tablas de Darwinex y confírmalo: mismo subyacente y misma divisa de cotización. Ejemplos ya comprobados: USATECHIDXUSD → NDX, USA30IDXUSD → WS30, USA500IDXUSD → SP500. Si no hay equivalente claro, dilo y no rellenes la tabla con otro mercado.

## Tablas de Darwinex (broker)

| Clase | URL |
|---|---|
| Forex | https://www.darwinex.com/forex-cfds/forex |
| Índices | https://www.darwinex.com/forex-cfds/indices |
| Materias primas y metales | https://www.darwinex.com/forex-cfds/commodities |
| Cripto | https://www.darwinex.com/forex-cfds/crypto |

Léelas sin caché (`maxAge: 0`). El spread de estas tablas es instantáneo: solo sirve como información (`spread_instantaneo`), no para Default Spread ([spread-slippage.md](spread-slippage.md)).

## Tabla 1: configuración principal

| Columna | Regla |
|---|---|
| Símbolo | El que pide el usuario, tal cual (texto del PDF). El archivo usa una clave segura: ver [formato-json.md](formato-json.md). |
| Nombre recomendado | `<ticker Darwinex>` + `sufijo_nombre` del perfil (por defecto `_Darwinex`, p. ej., NDX_Darwinex). |
| Tipo | Forex (pares de divisas) · Index (índices) · Forex / CFD (metales y materias primas) · Crypto / CFD. |
| Pip/Tick | Forex: 0.0001; 0.01 si cotiza en JPY. Index: 1. Metales y materias primas: el tick real (oro 0.01, plata 0.001). Crypto: 1. |
| Point Value $ | Valor en USD de un movimiento de 1,0 en el precio con 1 lote = contrato × 1 en la divisa cotizada, convertido a USD (« aprox.» si se convierte). Definición SQ: strategyquant.com/forum/topic/3820. |
| No Pip/Tick | Siempre el **tick real** (movimiento mínimo del precio). Forex: Pip/Tick ÷ 10, porque Darwinex cotiza con 5 decimales y 3 en JPY (darwinexzero.document360.io/docs/calculate-pip-and-tick-value). Resto: Tick value ÷ (contrato × 1 unidad de precio), con los datos de la tabla de Darwinex. **Nunca ÷ 10 fuera de forex.** Si la tabla no da el tick value: PENDIENTE DE VERIFICAR (MT5 → Especificación). |
| Spread medio (pips) | Default Spread: Spread medio de 30 días — 24 horas — Darwinex — Forex Benchmark — sin comisiones, en pips de Pip/Tick (`lectura × pip_fuente ÷ Pip/Tick`; en forex y XAUUSD el número no cambia). Con fecha y hora de consulta y, si se conoce, fecha final del periodo. El script comprueba el criterio y la conversión. Sin cobertura: PENDIENTE con alternativas. |
| Slippage · Min dist. · Order mult. · Order step | Ajustes personales del perfil (predeterminado 0 · 0 · 1 · 0.01). Los pone el script; no son datos del bróker. |

## Tabla 2: comisiones, swaps y rollover

| Columna | Regla |
|---|---|
| Modelo de comisión | «En función del tamaño» si Darwinex cobra un importe fijo por contrato y orden (forex, índices). «Comisión en porcentaje» si cobra un % del valor de la orden (metales, materias primas, cripto). |
| Comisión a poner en SQ | Ida y vuelta: Darwinex publica la comisión **por orden** y una operación son 2 órdenes (help.darwinex.com/execution-costs); SQ trata el valor como ida y vuelta (verificacion-fuentes.md). Importe fijo: comisión por orden × 2, en USD (« aprox.» si se convierte). Porcentaje: % por orden × 2 (0.0025 % → 0.005). Siempre como cálculo con la entrada `comision_por_orden`; se duplica una sola vez. |
| Swap largo / Swap corto | USD por lote y día, del swap por contrato de Darwinex (« aprox.» si se convierte). Instantánea del día de consulta. |
| Triple swap | Lo que diga la nota de la tabla de Darwinex de esa clase. Comprobado el 2026-10-20: forex WEDNESDAY (USDCAD THURSDAY); índices FRIDAY («in triple size on Fridays»). Comprobado el 2026-11-26: metales WEDNESDAY («in triple size on Wednesdays»); XTIUSD y XNGUSD tienen su propia nota (help.darwinex.com/swaps-xtiusd-xngusd). Cripto: léelo en su tabla. |
| Rollover | Ajuste personal del perfil (predeterminado 23:59). |

## Conversiones a USD

Tipo de referencia del BCE con su fecha (ecb.europa.eu, euro_reference_exchange_rates). Cruces: USDX = EURX ÷ EURUSD; XUSD = EURUSD ÷ EURX. Cita el tipo y la fecha en la fuente.

## Sin inventar

- Cada casilla lleva su fuente estructurada (formato-json.md): dato con URL y fecha; spread medio con el criterio de Forex Benchmark, fecha, hora UTC, lectura y pip; cálculo con fórmula, entradas y sus fuentes; regla con su referencia.
- Si un dato no aparece en ninguna fuente fiable, «PENDIENTE DE VERIFICAR» con una fuente `pendiente` y su motivo. La tabla queda INCOMPLETA y el PDF lo indica. Ejemplo: `examples/BTCUSD.json`.
- Si dos fuentes discrepan, anótalo en «notas» y deja la casilla en «PENDIENTE DE VERIFICAR».
