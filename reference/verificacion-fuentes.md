# Verificación con la documentación oficial (2026-10-27)

Contraste de unidades, spread y comisiones con fuentes oficiales, consultadas el 2026-10-27 sin caché. **Verificado** = lo dice una fuente oficial. **Parcial** = lo dice personal de la empresa, pero no la documentación formal. **Pendiente** = sin evidencia suficiente.

| Punto | Estado | Evidencia |
|---|---|---|
| Spread de StrategyQuant en **pips**, y pip = `Pip/Tick size` | Verificado | «Spread: Define the Bid–Ask difference in pips» (strategyquant.com/doc/data-settings/, act. 2026-04). «Default spread of the instrument in pips»; «Pip/Tick size … what number is 1 pip … 0.0001, JPY 0.01» (strategyquant.com/doc/import-history-data-metatrader-4/) |
| `Pip/Tick step` = movimiento mínimo del precio (tick real) | Verificado | «Pip/Tick Step is a value by how much one pip can move … 5-digit data → 0.00001 (0.001 JPY)» (doc import MT4). En el foro, un usuario lo explica como «minimum move in price in my broker» y que un spread de 41 puntos de MT5 en GBPJPY son 4.1 pips en SQ; un administrador da esa explicación por «almost correct» y solo corrige order size multiplier y point value |
| Point value = valor en USD de un movimiento de 1.0 del precio con 1 lote | Parcial | Administrador de SQ (tomas262) en strategyquant.com/forum/topic/deep-explanation-of-instrument-specifications-pip-tick-size-step-value-etc/: «monetary value for a whole number price move … per 1 lot». La doc antigua de importación MT4 dice «usually 10», que corresponde a otra definición: la descartamos |
| Swap «money» en USD por lote y día | Verificado | Fórmula «Money: Swap = Lot Size × Swap Rate × Days» (doc data-settings) |
| Darwinex publica la comisión **por orden** (2 órdenes por operación) | Verificado | «commissions are displayed per order, a trade would be composed of 2 orders: entry order and close order» (help.darwinex.com/execution-costs) |
| StrategyQuant aplica la comisión **ida y vuelta** | Parcial | Administrador de SQ (tomas262), strategyquant.com/forum/topic/commission-setting/: «What you set as commission is calculated as round-turn (for both sides). Set 7 USD size based» para 3.5 USD por orden. **No hay** página formal de documentación que lo diga, ni confirmación específica de la build 143 |
| Comisión en porcentaje ida y vuelta | Parcial | Misma respuesta del foro (habla de la comisión en general) |
| Dukascopy llega en UTC y hay que clonarlo a la hora del bróker | Verificado | strategyquant.com/blog/preparing-accurate-data-for-algo-trading-broker-data-feed-differences/ (consultado 2026-10-19) |

## Decisión aplicada

La skill pone en SQ la comisión por orden × 2. Hay una base suficiente: Darwinex documenta el «por orden» y un administrador de StrategyQuant dice que SQ trata el valor como ida y vuelta. Lo que no queda cerrado es si la **build 143** se comporta así, porque la documentación formal no lo dice.

**PENDIENTE DE VERIFICAR (una sola vez, en StrategyQuant build 143):** haz un backtest con una sola operación de 1 lote y la comisión de un símbolo (p. ej., NDX 5.50). En la lista de operaciones, la comisión cobrada debe ser 5.50 (ida y vuelta). Si sale 11.00, SQ cobra por lado: cambia `FACTOR_IDA_VUELTA` a 1 en `scripts/tabla.py` y avisa en el CHANGELOG.

## Spread medio de Forex Benchmark (2026-11-27)

| Punto | Estado | Evidencia |
|---|---|---|
| Forex Benchmark publica el spread medio histórico de Darwinex con 30 días, 24 horas y sin comisión | Verificado | Página Historic spreads: Darwinex en la lista de brókeres; opciones «24 hours», «30 days» y «Add commission to spread» (desmarcada por defecto). Consulta del 2026-11-27 01:22 UTC (autorizada por el usuario, una sola vez): EURUSD 0.42, USDJPY 0.98, USDCAD 0.94, GBPJPY 2.60, GBPUSD 0.90, AUDUSD 0.70, XAUUSD 48.23, XAGUSD 1.63 |
| Unidad: pips (forex 0.0001 / JPY 0.01; XAUUSD 0.01) | Verificado | «0.1 is added for every $1 of commission» y contraste con bid/ask de Darwinex (ver spread-slippage.md) |
| Unidad de XAGUSD | Verificado (2026-11-28) | Darwinex bid 43.496 / ask 43.515 = 0.019 USD; Forex Benchmark 1.63 solo cuadra en pips de 0.01 (0.0163 USD). Con el Pip/Tick 0.001 de la skill: × 10 |
| Unidad de los exóticos | Pendiente | Sin lectura de Darwinex con la que contrastarla |
| Cobertura | Verificado | Solo forex, XAUUSD y XAGUSD; ni índices, ni petróleo, ni cripto |
| Fecha final del periodo | Pendiente | La tabla no la muestra; el valor parece la media de unos 21 días de mercado |
| Comisión que Forex Benchmark atribuye a Darwinex: 5,00 USD por lote ida y vuelta | Verificado | Página Broker information. Coincide con la regla de la skill (2,5 por orden × 2) |
| Consulta automática | No permitida sin permiso | Sin API pública; los términos de uso prohíben «access them using a method other than the interface and the instructions». Por eso, desde el 2026-11-28, la fuente principal es el muestreo automático propio (abajo) |
| Qué cuenta de Darwinex miden (MT4 o MT5, servidor) | Pendiente | Forex Benchmark no lo indica |

## Spread medio automático (muestreo ISQX, 2026-11-28)

| Punto | Estado | Evidencia |
|---|---|---|
| El feed `widgets.fxbluelabs.com` (id=Darwinex) es el que usa la web de Darwinex y da bid/ask de todos sus símbolos | Verificado | Respuesta del 2026-11-28 con los 59 símbolos de forex, índices, materias primas y cripto de Darwinex (USDZAR, que Darwinex no lista, sale `noData`) |
| Horario de cada símbolo | Verificado | Campos `timezone`, `opentime` y `closetime` del JSON de Darwinex (p. ej., forex 17:05–16:55 Nueva York; GDAXI 01:30–20:55 Londres; NI225 09:31–15:59 Nueva York) |
| Pips con el Pip/Tick Size de la tabla | Verificado | Misma regla que la tabla (`pip_regla` en app/sqx/instrumento.py). Prueba con cotizaciones reales del 2026-11-27: EURUSD 0.5, XAUUSD 41, XAGUSD 19 (pip 0.001), NDX 0.9, XTIUSD 4 |
| Muestra cada 15 minutos | Según GitHub | Las tareas programadas de GitHub Actions pueden retrasarse en horas de mucha carga; el número real de muestras queda en `muestras` |
| La media converge con la de Forex Benchmark | Pendiente | Forex Benchmark promedia minuto a minuto. Comparar cuando haya 30 días de muestras (a partir del 2026-12-27) |

**Comprobación pendiente en StrategyQuant build 143:** con una operación de 1 lote, el coste del spread debe ser Default Spread × valor del pip, y la comisión debe cobrarse una sola vez, aparte del spread.

## Otros puntos pendientes

- La captura de la ventana de clonado de build 143 (nombre exacto de la zona EST+07 en el desplegable): ver guias/descarga-y-clonacion.md.
- La build 144 ya importa directamente desde MT5 el tick size, el point value y el spread (strategyquant.com/doc/metatrader5-data-import/, act. 2026-04-30). La skill sigue orientada a la build 143.
