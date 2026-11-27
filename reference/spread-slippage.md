# Spread y slippage

## Default spread: spread medio de Forex Benchmark (criterio de la academia)

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

### Cómo se obtiene

Forex Benchmark no tiene API pública y sus condiciones de uso no permiten acceder al servicio por un método distinto de su web («access them using a method other than the interface and the instructions»). Por eso **el valor lo copia el usuario** de la web:

1. Abre la página, elige **Darwinex**, **24 hours**, **30 days** y deja **sin marcar** «Add commission to spread».
2. Lee el valor del símbolo en la tabla (2 decimales).
3. En la skill, Claude pide ese valor (o una captura de la tabla con los ajustes visibles). En la app, se escribe en «Spread medio (pips)».

No consultes el endpoint interno de la página ni la «scrapees» seleccionando opciones: sin permiso escrito de Forex Benchmark, solo vale la lectura del usuario.

### Cobertura (lista leída el 2026-11-27)

- **Sí**: pares de forex entre USD, EUR, JPY, GBP, CAD, AUD, NZD y CHF, y **XAUUSD**.
- **Listados, pero con unidad sin comprobar**: XAGUSD y los exóticos (MXN, ZAR, TRY, NOK, SEK, CNH, HUF…). Quedan pendientes hasta comprobarlo. En XAGUSD importa: la skill usa Pip/Tick 0.001 y Forex Benchmark daba 1.63 el 2026-11-27, que solo es razonable en pips de 0.01 (1,6 centavos); si se confirma, habría que multiplicar por 10.
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

Si el medio y el instantáneo se diferencian más de 5 veces, el script avisa (posible error al copiar). Con el mercado cerrado, el instantáneo puede no ser representativo.

## Default slippage: valor fijo

Ajuste personal del perfil (predeterminado **0 pips**). Lo pone el script. Darwinex no publica slippage, así que este 0 es un supuesto de simulación, no un dato del bróker.
