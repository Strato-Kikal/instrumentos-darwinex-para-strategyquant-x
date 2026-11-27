# Formato del JSON de un símbolo (esquema 3)

Un archivo por símbolo en `DATA/tablas/<CLAVE>.json`. La **clave** del archivo solo admite letras, números, punto, guion y guion bajo (máx. 40), sin `/`, `\`, `..` ni espacios, para que ningún nombre salga de la carpeta de datos. El campo `simbolo` es lo que se muestra en el PDF y admite texto libre (p. ej., `DAX / GDAXI` en `DAX_GDAXI.json`).

Ejemplos reales en `examples/` (datos del 2026-10-27; spread medio de Forex Benchmark del 2026-11-27): `EURUSD.json` (forex con conversión), `XAUUSD.json` (comisión en porcentaje, spread medio en pips de 0.01), `NDX.json` (índice con tick real; sin spread medio en Forex Benchmark: incompleta) y `BTCUSD.json` (tabla incompleta).

El esquema 3 (2026-11-27) cambia el spread: Default Spread es el spread medio de Forex Benchmark (`promedio`) y la lectura instantánea pasa a `spread_instantaneo`. `tabla.py migrar` convierte los JSON de los esquemas 1 y 2: la lectura instantánea se conserva en `spread_instantaneo` y Default Spread queda PENDIENTE hasta añadir el spread medio.

## Campos

| Campo | Tipo | Regla de validación |
|---|---|---|
| `esquema` | número | `3` |
| `simbolo` | texto | obligatorio, ≤ 40 caracteres |
| `consulta`, `creada` | texto `AAAA-MM-DD` | fecha que exista, no futura |
| `nombre` | texto | aviso si no termina en el `sufijo_nombre` del perfil |
| `tipo` | texto | `Forex`, `Index`, `Forex / CFD`, `Crypto / CFD` |
| `pip_tick`, `no_pip_tick` | número en texto | > 0, sin « aprox.» |
| `point_value` | número en texto | > 0, admite « aprox.» |
| `spread` | número en texto | Default Spread: spread medio de Forex Benchmark, ≥ 0, en pips de `pip_tick`, sin « aprox.» |
| `spread_instantaneo` | número en texto | opcional e informativo: ≥ 0, en pips de `pip_tick`; nunca cuenta como Default Spread ni como pendiente |
| `modelo_comision` | texto | `En función del tamaño` o `Comisión en porcentaje` |
| `comision` | número en texto | ≥ 0, admite « aprox.» |
| `swap_largo`, `swap_corto` | número en texto | cualquier signo, admite « aprox.» |
| `triple_swap` | texto | `MONDAY` … `SUNDAY` |
| `fuentes` | objeto | una fuente por campo (abajo) |
| `notas` | lista de textos | opcional |

Los números van **entre comillas** y con punto decimal (`"0.00001"`), para no perder decimales. Cualquier campo de datos puede valer `"PENDIENTE DE VERIFICAR"`.

Los ajustes personales (`slippage`, `min_dist`, `order_mult`, `order_step`, `rollover`) **no van en el JSON**: salen del perfil. Si aparecen con otro valor, la tabla no es válida.

## Fuentes

Cada campo de datos necesita su fuente en `fuentes.<campo>`, con uno de estos tipos:

| `tipo` | Para | Claves obligatorias |
|---|---|---|
| `dato` | valor leído en una fuente | `url`, `fecha` |
| `promedio` | **solo `spread`** (Default Spread) | `fuente` = `Forex Benchmark`, `broker` = `Darwinex`, `periodo_dias` = `30`, `franja` = `24 horas`, `comision` = `excluida`, `unidad` = `pips`, `url` (la página Historic spreads), `fecha` y `hora_utc` (consulta), `lectura` (valor de Forex Benchmark), `pip_fuente` (pip con el que lo da); `datos_hasta` opcional (fecha final del periodo, distinta de la consulta) |
| `observado` | **solo `spread_instantaneo`** | `url`, `fecha`, `hora_utc` (HH:MM), `unidad` (`pips`, `puntos` o `precio`), `lectura` (valor tal como lo da la fuente); `punto` opcional si la unidad es `puntos` |
| `calculo` | valor calculado | `formula`, `entradas` (lista; cada entrada con `nombre`, `valor` y `url` + `fecha`, o `campo` si sale de otra casilla) |
| `regla` | convención (tipo, pip forex, nombre) | `regla`, `referencia` |
| `pendiente` | falta evidencia | `motivo` |

Claves opcionales en cualquier fuente: `nota`, `texto_v1` (texto original de una migración). Las fechas de las fuentes no pueden ser posteriores a `consulta`.

## Comprobaciones de coherencia

- **Spread medio**: los parámetros deben ser exactamente los del criterio; el símbolo debe estar en la cobertura comprobada de Forex Benchmark (si no, la tabla no es válida: deja Default Spread PENDIENTE), `pip_fuente` debe ser el comprobado para ese símbolo y `spread = lectura × pip_fuente ÷ Pip/Tick`. `datos_hasta` no puede ser posterior a la consulta; si termina más de 7 días antes, aviso.
- **Spread instantáneo**: la `lectura` convertida debe dar `spread_instantaneo`: `pips` → igual; `precio` → lectura ÷ Pip/Tick; `puntos` → lectura × punto ÷ Pip/Tick (si no se indica `punto`, se supone el No Pip/Tick y se avisa). Si el medio y el instantáneo se diferencian más de 5 veces, aviso (posible error de copia).
- **Comisión**: debe ser `calculo` con la entrada `comision_por_orden`. Sin conversión de divisa, `comision = comision_por_orden × 2`.
- **Point Value**: con una entrada `contrato` y sin « aprox.», debe ser igual al contrato.
- **Tick real**: con entradas `tick_value` y `contrato`, `no_pip_tick = tick_value ÷ contrato`.
- **Avisos**: forex con un tick distinto de Pip/Tick ÷ 10; «÷ 10» fuera de forex; tick mayor que el pip; relación pip/tick que no sea potencia de 10; consulta de hace más de 7 días; spread instantáneo leído otro día.

## Estados

- **NO VÁLIDA**: hay ✗. `generar` no crea el PDF.
- **INCOMPLETA**: válida, pero con datos `PENDIENTE DE VERIFICAR`. El PDF se genera con `_INCOMPLETA` en el nombre, un aviso bajo el título y las casillas en rojo.
- **COMPLETA**: todos los valores y sus fuentes pasan las comprobaciones. Esto no sustituye la revisión final en MT5 → Especificación.

## Ejemplo de fuentes

```json
"spread": {"tipo": "promedio", "fuente": "Forex Benchmark", "broker": "Darwinex", "periodo_dias": "30",
           "franja": "24 horas", "comision": "excluida", "unidad": "pips",
           "url": "https://forexbenchmark.com/brokers/historic_spreads/", "fecha": "2026-11-27",
           "hora_utc": "01:22", "lectura": "0.42", "pip_fuente": "0.0001"},
"spread_instantaneo": {"tipo": "observado", "url": "https://widgets.fxbluelabs.com/webwidgets/getPriceData.aspx?id=Darwinex&f=bid,ask&s=NDX",
           "fecha": "2026-10-27", "hora_utc": "08:18", "unidad": "precio", "lectura": "1.1"},
"comision": {"tipo": "calculo", "formula": "comision_por_orden × 2 (ida y vuelta)",
             "entradas": [{"nombre": "comision_por_orden", "valor": "2.75", "url": "https://www.darwinex.com/forex-cfds/indices", "fecha": "2026-10-27"},
                          {"nombre": "órdenes por operación", "valor": "2", "url": "https://help.darwinex.com/execution-costs", "fecha": "2026-10-27"}]},
"swap_largo": {"tipo": "pendiente", "motivo": "la tabla de cripto de Darwinex no está publicada"}
```
