# Spread y slippage

## Default spread: spread medio automático de Darwinex

**Spread medio de 30 días — 24 horas — Darwinex — muestreo automático ISQX cada 15 min — sin comisiones.**

| Parámetro | Valor |
|---|---|
| Fuente | Muestreo ISQX del feed de precios de Darwinex: `medias.json` de la rama `datos-spread` (https://raw.githubusercontent.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x/datos-spread/medias.json) |
| Bróker | Darwinex (bid/ask del feed que usa su propia web, `widgets.fxbluelabs.com`) |
| Periodo estadístico | Últimos 30 días naturales |
| Franja horaria | 24 horas: todas las horas con el mercado abierto |
| Muestras | Una cada 15 minutos (tarea programada de GitHub Actions `spread-medio.yml`) |
| Comisiones | Excluidas: es solo ask − bid |
| Unidad | Pips del Pip/Tick Size de la tabla (forex 0.0001, JPY 0.01, índices y cripto 1, metales y materias primas el tick real) |
| Destino | Casilla Default Spread del instrumento en StrategyQuant X |

El rollover del perfil (23:59) es otra cosa: no cambia el periodo ni la franja del spread, ni al revés.

### Cómo se obtiene (nadie escribe nada)

Cada 15 minutos, la tarea programada:
1. lee la lista de símbolos y su horario en los datos de Darwinex;
2. lee el bid/ask de todos (forex, índices, metales, petróleo, gas y cripto);
3. guarda `(ask − bid) ÷ Pip/Tick Size` solo si el mercado está abierto según el horario de Darwinex **y** la cotización ha cambiado desde la muestra anterior (así no cuentan fines de semana, festivos ni pausas);
4. publica en `medias.json` la media, el número de muestras, el periodo (`desde`, `hasta`) y el mínimo y el máximo de cada símbolo.

- **En la skill**: `python3 -I "SK/scripts/tabla.py" spread <SÍMBOLO>` descarga `medias.json` y muestra el `spread` y su fuente listos para pegar en el JSON. Si sale PENDIENTE, no hay muestras suficientes todavía.
- **En la app**: se consulta sola al pulsar «Obtener datos».

**Mínimo**: 48 muestras (unas 12 horas de mercado abierto). Con menos, Default Spread queda PENDIENTE y se rellena solo más adelante.

**Arranque**: el muestreo empezó el 2026-11-28. Hasta que acumule 30 días, la media cubre los días que lleva; la ficha lo dice («el muestreo empezó hace N días») y el script avisa. A partir del 2026-12-27 la media ya es de 30 días completos.

**Si la tarea se detiene** (por ejemplo, GitHub desactiva las tareas programadas de un repositorio sin actividad), `hasta` deja de avanzar y el script avisa cuando el periodo termina más de 4 días antes de la consulta.

### Diferencias con Forex Benchmark (criterio anterior)

- Forex Benchmark promedia minuto a minuto; aquí, una muestra cada 15 minutos (unas 2 000 por símbolo en 30 días). La media converge, pero no es idéntica.
- Forex Benchmark solo cubre forex y metales; el muestreo cubre todos los símbolos de forex, índices, materias primas y cripto de Darwinex.
- Sus condiciones de uso no permiten consultarlo de forma automática, y por eso se dejó de usar como fuente principal el 2026-11-28.

Se sigue aceptando una fuente `promedio` de Forex Benchmark (tablas anteriores), con su criterio exacto (ver más abajo), pero ya no hace falta.

### Fuente en el JSON

```json
"spread": {"tipo": "promedio", "fuente": "Muestreo ISQX del feed de precios de Darwinex",
           "broker": "Darwinex", "periodo_dias": "30", "franja": "24 horas", "comision": "excluida",
           "unidad": "pips",
           "url": "https://raw.githubusercontent.com/Strato-Kikal/instrumentos-darwinex-para-strategyquant-x/datos-spread/medias.json",
           "fecha": "2026-12-28", "hora_utc": "10:05", "lectura": "0.4234", "pip_fuente": "0.0001",
           "muestras": "1980", "desde": "2026-11-29", "hasta": "2026-12-28", "intervalo_min": "15"}
```

(Valores de ejemplo.) `tabla.py spread` lo genera tal cual. Validación: criterio exacto, al menos 48 muestras, periodo de 30 días como máximo, `pip_fuente` igual al Pip/Tick Size de la tabla y `spread` = `lectura` redondeada a 2 decimales (con menos de 0.1, a dos cifras significativas).

## Forex Benchmark (criterio anterior, aceptado por compatibilidad)


**Spread medio de 30 días — 24 horas — Darwinex — Forex Benchmark — sin comisiones.**

| Parámetro | Valor |
|---|---|
| Fuente | Forex Benchmark · Historic spreads: https://forexbenchmark.com/brokers/historic_spreads/ |
| Bróker | Darwinex |
| Periodo estadístico | 30 days |
| Franja horaria | 24 hours |
| Comisiones | Excluidas: «Add commission to spread» **sin marcar** |
| Unidad | Pips (ver «Unidades» abajo) |
| Destino | Casilla Default Spread del instrumento en StrategyQuant X, en pips de Pip/Tick Size |

El rollover del perfil (23:59) es otra cosa: no cambia el periodo ni la franja del spread, ni al revés.

### Cómo se obtenía

Forex Benchmark no tiene API pública y sus condiciones de uso no permiten acceder al servicio por un método distinto de su web («access them using a method other than the interface and the instructions»). Por eso **el valor lo copia el usuario** de la web:

1. Abre la página, elige **Darwinex**, **24 hours**, **30 days** y deja **sin marcar** «Add commission to spread».
2. Lee el valor del símbolo en la tabla (2 decimales).
3. En la skill, Claude pide ese valor (o una captura de la tabla con los ajustes visibles). En la app, se escribe en «Spread medio (pips)».

No consultes el endpoint interno de la página ni la «scrapees» seleccionando opciones: sin permiso escrito de Forex Benchmark, solo vale la lectura del usuario.

### Cobertura (lista leída el 2026-11-27)

- **Sí**: pares de forex entre USD, EUR, JPY, GBP, CAD, AUD, NZD y CHF, y **XAUUSD**.
- **XAGUSD**: comprobado el 2026-11-28. Darwinex daba bid 43.496 / ask 43.515 (0.019 USD) y Forex Benchmark 1.63: solo cuadra en pips de 0.01 (0.0163 USD); con 0.001 serían 0.0016 USD, menos que el spread real. Con el Pip/Tick 0.001 de la skill, Default Spread = 1.63 × 0.01 ÷ 0.001 = 16.3.
- **Listados, pero con unidad sin comprobar**: los exóticos (MXN, ZAR, TRY, NOK, SEK, CNH, HUF…).
- **No**: índices (NDX, GDAXI, NI225…), petróleo (XTIUSD), gas, cripto (BTCUSD…).

Sin dato verificable, Default Spread queda **PENDIENTE DE VERIFICAR** y la tabla **INCOMPLETA**. El motivo indica las alternativas, **sin aplicarlas**:
1. medir el spread medio de 30 días y 24 horas en MT5 conectado a Darwinex;
2. el promedio que publica Darwinex (`spreadAverage` en sus datos), avisando de que no indica su periodo ni su unidad (el 2026-11-26 daba entre un 10 % y un 50 % menos que Forex Benchmark: EURUSD 0.38 frente a 0.42, USDJPY 0.47 frente a 0.98);
3. otra fuente que indique la academia.

Nunca uses el spread de otro bróker ni el spread instantáneo como sustituto.

### Unidades (comprobado el 2026-11-27)

Forex Benchmark da el spread en **pips**: «0.1 is added for every $1 of commission» (en un par de 10 USD por pip, 1 USD = 0,1 pip). Contraste con bid/ask de Darwinex (2026-11-26) y con la consulta a Forex Benchmark (2026-11-27 01:22 UTC):

| Símbolo | Forex Benchmark | Instantáneo de Darwinex | Pip de Forex Benchmark |
|---|---|---|---|
| EURUSD | 0.42 | 0.5 pips | 0.0001 |
| USDJPY | 0.98 | 0.9 pips | 0.01 |
| USDCAD | 0.94 | 0.9 pips | 0.0001 |
| GBPJPY | 2.60 | 2.1 pips | 0.01 |
| XAUUSD | 48.23 | 0.41 USD = 41 pips | 0.01 (con 0.1 serían 4,8 USD: imposible) |

Con el Pip/Tick Size de la skill (forex 0.0001, JPY 0.01, XAUUSD 0.01), el valor pasa tal cual: `Default Spread = lectura × pip de Forex Benchmark ÷ Pip/Tick Size`. El script lo comprueba con `pip_fuente`.

**Comisiones**: con la casilla sin marcar, el valor no incluye comisión. La comisión va en su propia casilla (por orden × 2): no se suma al spread ni se cuenta dos veces. Forex Benchmark atribuye a Darwinex 5,00 USD por lote ida y vuelta, lo mismo que 2,5 por orden × 2.

### Fechas

- **Consulta** (`fecha`, `hora_utc`): cuándo se leyó el valor.
- **Periodo** (`datos_hasta`, opcional): fecha final de los 30 días, si se conoce (eje del gráfico de Forex Benchmark). La tabla no la muestra; si falta, el PDF dice «últimos 30 días (Forex Benchmark no indica la fecha final)». No la deduzcas ni la confundas con la consulta.
- La media parece calcularse sobre los días de mercado (unos 21) de esos 30 días naturales; Forex Benchmark no lo documenta.

### Fuente en el JSON

```json
"spread": {"tipo": "promedio", "fuente": "Forex Benchmark", "broker": "Darwinex", "periodo_dias": "30",
           "franja": "24 horas", "comision": "excluida", "unidad": "pips",
           "url": "https://forexbenchmark.com/brokers/historic_spreads/", "fecha": "2026-11-27",
           "hora_utc": "01:22", "lectura": "0.42", "pip_fuente": "0.0001"}
```

`datos_hasta` es opcional. Si cualquier parámetro no coincide con el criterio, la tabla no es válida.

**Aviso**: Forex Benchmark avisaba el 2026-11-27 de que estaba recalculando sus datos históricos («some of the functions may not work properly»). Si cambia su metodología, revisa esta página.

## Spread instantáneo: solo informativo

Puede anotarse en `spread_instantaneo` (opcional) para comparar, **nunca en Default Spread**:

- Columna «Current spread» de https://www.darwinex.com/forex-cfds/forex (sin caché) o el feed que usa esa tabla: `curl -s "https://widgets.fxbluelabs.com/webwidgets/getPriceData.aspx?id=Darwinex&f=bid,ask&s=EURUSD"`. Spread = ask − bid, pasado a pips con Pip/Tick Size.
- O una captura de MT5 → Observación de mercado (columna Spread, en puntos): `pips = puntos × punto de MT5 ÷ Pip/Tick Size`.
- Fuente `observado`: `url`, `fecha`, `hora_utc`, `unidad` (`pips`, `puntos` o `precio`), `lectura` y, si es en puntos, `punto`.

Si el medio y el instantáneo se diferencian más de 5 veces, el script avisa (el instantáneo es una sola lectura). Con el mercado cerrado, el instantáneo puede no ser representativo.

## Default slippage: valor fijo

Ajuste personal del perfil (predeterminado **0 pips**). Lo pone el script. Darwinex no publica slippage, así que este 0 es un supuesto de simulación, no un dato del bróker.
