# Campos de «Edit instrument» (StrategyQuant X build 143)

> **Para las tablas mandan las reglas de [tabla-reglas.md](tabla-reglas.md)**: Commission y Triple swap se rellenan cuando hay evidencia, y Pip/Tick step (No Pip/Tick) es el tick real (en forex coincide con Pip/Tick ÷ 10). Este archivo explica el significado de cada campo en SQ. La entrega es un PDF; no hay ficha CSV.


Orden visual de la captura de referencia (izq.→der., arriba→abajo). La captura sirve para identificar los campos. **Sus valores (p. ej., GBPJPY: Point value 134910, Commission 6.75, swaps 12/−27.6, Rollout 23:29) son ejemplos y no se reutilizan.**

Leyenda de origen: **SQ** = significado en StrategyQuant · **BRÓKER** = condición de Darwinex · **DATOS** = característica del proveedor del histórico (Dukascopy). No mezclar: el bróker fija contrato, comisiones y swaps; el proveedor de datos solo aporta precios y su zona horaria.

## Fuentes base (consultadas el 2026-10-19; volver a consultarlas en cada tabla y registrar la fecha real)

| Id | URL | Qué aporta |
|----|-----|------------|
| SQ-SCREENS | https://strategyquant.com/doc/screens/ | Instruments, Broker Profiles (desde build 141), perfil Darwinex predefinido, conversión horaria automática al descargar con perfil, «All point values default to USD» |
| SQ-IMPORT | https://strategyquant.com/doc/import-history-data-metatrader-4/ | Definición de Pip/Tick size, Pip/Tick step, Default spread (pips). Doc de 2018: su frase «Point value… usually 10» es de la versión antigua y **contradice** SQ-PV |
| SQ-PV | https://strategyquant.com/forum/topic/3820-how-to-set-forexs-piptick-step-and-size/ | Mark Fric (arquitecto de SQ): Point value = valor en $ de un movimiento de 1,0 en el precio con 1 lote (USDJPY ≈ $1000). Pip = 0,01 en pares JPY |
| SQ-SWAP | https://strategyquant.com/codebase/monte-carlo-randomize-swap-of-a-whole-backtest/ | Swap type: points, money, percentages; Triple swap = día del triple; hora en que se cobra el swap |
| SQ-CLI | https://strategyquant.com/doc/cli-command-line/instrument-manage-instruments/ | Nombres internos: ticksize, tickstep, pointvalue, ordersizemultiplier, ordersizestep, datatype, broker |
| DX-FX | https://www.darwinex.com/forex-cfds/forex | Tabla de Darwinex: contrato, pip value, swaps long/short por contrato, comisión **por orden**, horario NY, triple el miércoles (USDCAD jueves) |
| DX-COSTS | https://help.darwinex.com/execution-costs | «Commissions are displayed per order, a trade would be composed of 2 orders» |
| DXZ-ASSETS | https://www.darwinexzero.com/assets | Tabla equivalente para Darwinex Zero |
| DXZ-SWAP | https://darwinexzero.document360.io/docs/trading-commissions-and-swaps | Swap a las 17:00 NY; triple el miércoles; Zero opera con fondos virtuales |
| DX-TIME | https://help.darwinex.com/metatrader-time | Servidor MT4/MT5: GMT+3 en horario de verano de EE. UU. y GMT+2 el resto (cierre de Nueva York) |
| DXZ-TIME | https://darwinexzero.document360.io/docs/time-in-darwinex-metatrader-terminals | Lo mismo para Darwinex Zero |
| SQ-TZ | https://strategyquant.com/blog/preparing-accurate-data-for-algo-trading-broker-data-feed-differences/ | Dukascopy en SQ/QDM llega en UTC; hay que clonarlo al horario del bróker; diferencias EET frente a EST+7 |
| ECB | https://www.ecb.europa.eu/stats/policy_and_exchange_rates/euro_reference_exchange_rates/html/index.en.html | Tipos de referencia del BCE (con fecha) para convertir a USD |

**Perfil predeterminado (`config/perfil.json`, configurable):** Darwinex (broker) con la tabla DX-FX, **MT5**, cuenta en **USD**, datos de **Dukascopy** y horario **(EST+07) New York Trading hours, US DST**. No se pregunta.

## Casilla por casilla

**Broker profile** — SQ: perfil que agrupa zona horaria, instrumentos y sesiones del bróker (SQ-SCREENS). Lo elige el usuario: siempre «POR RELLENAR» salvo que lo haya fijado en `confirmado.md`. Es crítico para el horario: con un perfil de bróker, SQ convierte los datos descargados a la zona del bróker.

Opciones de broker profile vistas en build 143 (filtro de Edit symbol, 2026-10-19): SQ default, [[Darwinex]], [[Dukascopy]], [[FTMO]], [[ICMarkets]], [[Monevis]], [[OANDA]], [[Pepperstone]], [[RoboForex]], [[The5ers]]. Los perfiles entre [[ ]] son predefinidos por SQ. Sus instrumentos no son fuente de la ficha: los valores salen del bróker y de la documentación.

**Instrument** — SQ: nombre del instrumento. Convención de nombres del usuario guardada en `DATA/confirmado.md`; si no existe, «POR RELLENAR». No copiar el de la captura.

**Data type** — SQ: tipo de datos (en la captura: Forex). «POR RELLENAR» (decide el usuario).

**Description** — SQ: texto libre. Propuesta según la convención de `confirmado.md`; si no hay, «POR RELLENAR».

**Pip/Tick size** — SQ: «qué número es 1 pip»; 0,0001 en la mayoría de pares y 0,01 en pares JPY (SQ-IMPORT, SQ-PV). Contraste con el BRÓKER: pip value de Darwinex = contrato × pip (p. ej., 100000 × 0,01 = 1000 JPY en GBPJPY). Si los dos cuadran, valor verificado.

**Point value in $** — SQ: valor en USD de un movimiento de **1,0** en el precio con **1 lote** (SQ-PV). Cálculo:
- Cotizada en USD (EURUSD): `contrato × 1` → 100000.
- Cotizada en otra divisa C: `contrato ÷ USDC` (USDJPY, USDCHF…) o `contrato × CUSD` (GBPUSD, AUDUSD…), con el tipo de una fuente fechada (ECB: USDC = EURC ÷ EURUSD).
- Entradas: contrato (BRÓKER: DX-FX o captura MT5) y tipo de cambio (ECB con fecha).
- Avisos: SQ guarda un valor fijo y el tipo real cambia a lo largo del histórico, así que es una aproximación. SQ-SCREENS: «All point values default to USD; if using a different account currency, adjust the values manually». La cuenta es en USD (configuración fija), así que no hay ajuste. Error típico: multiplicar por la divisa base (GBPUSD) en vez de convertir la cotizada (JPY). El 134910 de la captura de GBPJPY coincide con 100000 × 1,3491 (GBPUSD), no con 100000 JPY en USD.

**Pip/Tick step** (columna «No Pip/Tick» de la tabla) — SQ: movimiento mínimo del precio, es decir, el **tick real** del instrumento (SQ-IMPORT: «by how much one pip can move», 0.00001 con 5 decimales). Forex en Darwinex: Pip/Tick size ÷ 10 (0.0001 → 0.00001; 0.01 → 0.001), porque cotiza con 5 decimales (3 en JPY). Resto: tick value ÷ contrato con los datos de Darwinex (p. ej., NDX 1 USD ÷ 10 = 0.1; WS30 = 1). **No se aplica ÷ 10 fuera de forex.** Si no hay datos: PENDIENTE DE VERIFICAR y comprobar en MT5 → Especificación.

**Default spread (pips)** — Siempre el spread real y actual observado en la tabla de Darwinex, con su hora UTC. Nunca vacío (ver [spread-slippage.md](spread-slippage.md)).

**Default slippage (pips)** — Ajuste personal del perfil (predeterminado **0**).

**Min distance** — Ajuste personal del perfil (predeterminado **0**).

**Order size multiplier** — Ajuste personal del perfil (predeterminado **1**).

**Order size step** — Ajuste personal del perfil (predeterminado **0.01**).

Estos cuatro y Rollout hour los pone `tabla.py` desde el perfil, identificados como decisión de configuración. No van en el JSON del símbolo.

**Default commissions model** — SQ: selector de 5 opciones (None, Per trade, Percentage based, Size based, Stockpicker). Darwinex cobra un importe fijo por lote y orden en la divisa base (DX-FX) → encaja con **Size based** («commissions in $ per lot and multiplies it by actual trade size», texto de la pantalla). Si Darwinex cobra un % del valor de la orden (metales, materias primas), se usa **Percentage based** («Comisión en porcentaje»). Con otro modelo, el panel cambia: pide una captura del panel antes de dar instrucciones.

**Commission** — Ida y vuelta por lote: comisión por orden de Darwinex × 2 (DX-COSTS: 2 órdenes por operación; SQ la aplica ida y vuelta según un administrador de SQ, ver [verificacion-fuentes.md](verificacion-fuentes.md)). En USD; « aprox.» si se convierte. Si no hay datos: PENDIENTE DE VERIFICAR.

**Swap: Use** — Interruptor. Darwinex cobra swaps (DX-FX, DXZ-SWAP) → ON salvo que el usuario decida excluirlos (entonces «POR RELLENAR» con su decisión).

**Swap type** — SQ: points, money, percentages (SQ-SWAP). Darwinex publica swaps en dinero por contrato y día → **money** es coherente con esa fuente.

**Long / Short** — Con money, la pantalla muestra «$ per day». Cálculo: `swap por contrato (divisa cotizada) convertido a USD` con tipo ECB fechado. Los swaps cambian a diario y SQ aplica un valor constante en todo el histórico: es una instantánea fechada, no la condición del periodo. Signo: el de Darwinex (negativo = cargo).

**Triple swap on** — El día que indica la nota de la tabla de Darwinex de esa clase (forex WEDNESDAY, USDCAD THURSDAY, índices FRIDAY a 2026-10-20; se vuelve a leer en cada tabla). Si no hay nota: PENDIENTE DE VERIFICAR.

**Rollout hour** — Ajuste personal del perfil (predeterminado **23:59**).
