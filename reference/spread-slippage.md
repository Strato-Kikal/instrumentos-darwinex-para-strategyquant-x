# Spread y slippage

## Default spread: siempre real y actual

La casilla lleva el spread real observado en el momento de preparar la tabla, **en pips** (pip = Pip/Tick size; SQ: «Define the Bid–Ask difference in pips»). Solo queda en PENDIENTE DE VERIFICAR si fallan todas las vías de abajo; entonces la tabla es INCOMPLETA.

1. Lee la tabla https://www.darwinex.com/forex-cfds/forex **sin caché** (scrape con `maxAge: 0`) y toma la columna «Current spread» del símbolo. Ya viene en pips.
   - Si la columna sale como «--- pips» (el scrape no ejecuta el refresco en vivo), consulta el mismo feed que usa la tabla (comprobado en su código el 2026-10-20): `curl -s "https://widgets.fxbluelabs.com/webwidgets/getPriceData.aspx?id=Darwinex&f=bid,ask&s=EURJPY,WS30,XAUUSD"` (tickers de Darwinex, separados por comas). Spread = ask − bid. La web lo muestra así: forex × 10000 (× 100 si es JPY); índices y metales en unidades de precio. Pásalo a pips con el Pip/Tick size de la tabla y anota la hora UTC.
   - La tabla de metales (commodities) a veces se queda en «Loading...»: pide `formats: ["rawHtml"]` y lee las filas de `commodities-content`.
2. Anota la hora UTC de la consulta (`date -u`).
3. Valor = ese spread en pips, con sus decimales tal cual. Fuente (formato-json.md): `{"tipo": "observado", "url": …, "fecha": "AAAA-MM-DD", "hora_utc": "HH:MM", "unidad": "pips" | "precio" | "puntos", "lectura": <valor leído>}`. El script comprueba que la lectura convertida dé el valor.
4. Si la web no responde o el símbolo no está en la tabla, pide al usuario una captura de MT5 → Observación de mercado con la columna **Spread** visible, que viene en puntos.
   - Conversión a pips: `pips = puntos × punto de MT5 ÷ Pip/Tick size`. El punto de MT5 (Especificación → dígitos) suele coincidir con el tick real: en forex de 5 dígitos, puntos ÷ 10; en NDX, 17 puntos de 0.1 → 1.7.
   - Fuente: `observado` con `"url": "captura MT5"`, `"unidad": "puntos"`, la `lectura` y el `punto` de MT5 (Especificación).
   - Si tampoco hay captura: PENDIENTE DE VERIFICAR y la tabla queda INCOMPLETA.
5. En la entrega, recuerda en una línea que el spread de Darwinex es variable y que el valor es una lectura de ese instante. Por ejemplo, EURUSD marcaba 2,2 pips el 2026-10-19 a las 15:46 UTC y 0,3 pips a las 22:39 UTC.

## Default slippage: valor fijo

Ajuste personal del perfil (predeterminado **0 pips**). Lo pone el script. Darwinex no publica slippage, así que este 0 es un supuesto de simulación, no un dato del bróker.
