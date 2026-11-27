# Cambios

## Sin publicar: spread medio de Forex Benchmark (criterio de la academia)

- **Default Spread = Spread medio de 30 días — 24 horas — Darwinex — Forex Benchmark — sin comisiones** en la skill y en la app. Antes era la lectura instantánea de Darwinex. Reglas, unidades y cobertura en `reference/spread-slippage.md`; verificación del 2026-11-27 en `reference/verificacion-fuentes.md`.
- **Esquema 3 del JSON**: nueva fuente `promedio` (fuente, bróker, 30 días, 24 horas, comisión excluida, unidad, lectura, `pip_fuente`, fecha y hora de consulta y, opcional, `datos_hasta`). `tabla.py` rechaza cualquier otro criterio y la lectura instantánea como Default Spread. La lectura instantánea pasa a `spread_instantaneo` (opcional, solo informativa).
- `tabla.py migrar` convierte los esquemas 1 y 2: conserva la lectura en `spread_instantaneo` y deja Default Spread PENDIENTE hasta añadir el spread medio.
- **Forex Benchmark no se consulta de forma automática** (sin API; sus condiciones de uso lo impiden): el usuario copia el valor. La app tiene dos campos nuevos (spread medio y fecha final de los datos).
- **Cobertura**: forex entre USD, EUR, JPY, GBP, CAD, AUD, NZD y CHF, y XAUUSD. XAGUSD y exóticos (unidad sin comprobar), índices, petróleo y cripto quedan PENDIENTE con alternativas (MT5 de Darwinex 30 días, promedio de Darwinex, otra fuente de la academia), sin sustituir la fuente.
- **PDF de la skill**: la columna pasa a «Spread medio (pips)» y debajo de la tabla 1 aparecen el criterio, la fecha de consulta, el periodo (distinto de la consulta) y el spread instantáneo aparte. **PDF de la app**: casilla «Default Spread» («X pips · medio 30 días · 24 h»), las mismas líneas bajo la tabla 1, una comprobación nueva en SQX (spread y comisión separados) y el spread instantáneo como fila informativa en la página de fuentes.
- Aviso si el spread medio y el instantáneo se diferencian más de 5 veces (posible error de copia).
- Ejemplos: EURUSD (0.42) y XAUUSD (48.23) con el spread medio real del 2026-11-27; NDX queda INCOMPLETA (Forex Benchmark no publica índices).
- Sin cambios: comisión (por orden × 2), swaps, triple swap, Pip/Tick, Point Value, perfil (rollover 23:59, MT5, USD, Dukascopy, EST+07).
- `SKILL.md`: la descripción del encabezado va entre comillas (el «: » de «Perfil predeterminado: MT5» rompía el YAML estricto).
- Pruebas: skill 68 → 82; app 50 → 58.

## 2.2.0 (2026-11-27): aplicación «Instrumentos SQX»

- Nueva carpeta `app/`: aplicación web instalable (PWA) y servidor en Python (solo biblioteca estándar) que preparan la tabla de un símbolo sin Claude: consultan Darwinex, el feed de spread, el BCE y la página de costes de Darwinex, aplican las reglas de `reference/`, validan con `tabla.validar()` y generan el PDF (página 1 igual que la de la skill + anexo de fuentes, fechas, fórmulas y ajustes). Ver `app/README.md`.
- 50 pruebas nuevas en `app/tests/` y un paso más en GitHub Actions.
- Revisión del PDF de la app (comprobada con GBPUSD y NDX en vivo el 2026-11-26): página 1 para rellenar SQX directamente (Pip/Tick Size y Pip/Tick Step; Tipo de swap «Dinero / Money» en USD por lote y día; comisión «X USD por lote, ida y vuelta» con la fecha del cambio del BCE; spread «X pips · lectura puntual» con la hora; rollover 23:59 como ajuste del perfil con la zona de los datos, separado del cobro de Darwinex a las 17:00 NY = 00:00 servidor MT5; estado «Datos completos · pendiente de validar en SQX» o lista de lo que falta; comprobaciones pendientes en SQX bajo las tablas). Página 2 con fuentes, fórmulas y enlaces clicables; sin la tercera página casi vacía. El PDF de la skill (`tabla.py`) no cambia.
- Icono de la app: el texto pasa de «SQX» a «ISQX» (mismos colores y estilo; letras ajustadas para leerse en tamaños pequeños). El nombre de la app sigue siendo «Instrumentos SQX».
- La skill no cambia: `SKILL.md`, `scripts/tabla.py`, `config/`, `reference/`, `guias/`, `examples/` y `tests/` quedan igual.

## 2.1.0 (2026-11-26)

- **Nuevo nombre**: «Instrumentos Darwinex para StrategyQuant X». El comando pasa a ser `/instrumentos-darwinex-para-strategyquant-x` (antes `/strategyquant-darwinex`) y la carpeta de la skill, `~/.claude/skills/instrumentos-darwinex-para-strategyquant-x`. La carpeta de datos (`~/strategyquant-darwinex-datos`) y las variables `SQD_*` no cambian.
- **Acumulado**: si alguna tabla guardada no es válida (p. ej., formato v1) y queda fuera, el acumulado anterior se guarda como `Tablas_<bróker>_todas_anterior_<fecha_hora>.pdf` antes de sustituirlo. Antes se sobrescribía sin copia y se perdían las tablas excluidas. 2 pruebas nuevas (68 en total).
- **Windows**: la salida de `tabla.py` va siempre en UTF-8. Antes, al leerla otro programa (Claude, Git Bash, las pruebas), salía en cp1252 y los acentos y símbolos (✗, ·) llegaban dañados.
- Las rutas de navegadores de macOS se construyen siempre con «/», también al calcularlas en otro sistema (la prueba fallaba en Windows).
- **Publicación en GitHub**: instalación con `git clone` en el README, GitHub Actions que ejecuta las pruebas con Python 3.8 a 3.13 en Linux, macOS y Windows, e insignia de CI.
- `reference/tabla-reglas.md`: triple swap de metales comprobado (WEDNESDAY, nota de Darwinex del 2026-11-26); XTIUSD y XNGUSD remiten a su nota propia.
- README: nuevas limitaciones (feed de spread no documentado; cuentas de Forex y CFD de Darwinex no disponibles para nuevos clientes minoristas en España, según su web) y sistemas probados a mano frente a CI.
- Prueba real de principio a fin en Claude Code con XAUUSD (2026-11-26): tabla COMPLETA, spread leído del feed porque la tabla web mostraba «--- pips».

## 2.0.3 (2026-10-28)

- PDF: la cabecera «Slippage» ya no se parte («Slippag / e»). La columna pasa de 98 a 125 de ancho relativo, tomados de «Spread» (211 → 184); el ancho total de la tabla no cambia.
- Se retiran las referencias al «PDF de referencia», que no forma parte del proyecto. Pasan a llamarse «convenciones de la skill» en `reference/tabla-reglas.md`, `SKILL.md`, `scripts/tabla.py` (comentarios), `examples/` y `tests/`. Las reglas no cambian.

## 2.0.2 (2026-10-28)

- `reference/tabla-reglas.md`: la sección «Indicaciones de la academia» (texto de terceros) se sustituye por «Reglas prácticas», redactada de nuevo y basada en fuentes oficiales (`reference/verificacion-fuentes.md`). Ya no manda sobre las fuentes oficiales: si discrepan, la casilla queda PENDIENTE DE VERIFICAR. Los días de triple swap salen siempre de la nota de Darwinex.
- `SKILL.md`: retirada la mención a la academia.
- PDF: las líneas de las tablas pasan de negro (`#000`) a azul grisáceo (`#7A93B2`). El resto del formato no cambia.

## 2.0.1 (2026-10-27)

- Licencia **MIT** (`LICENSE`, Copyright (c) 2026 Kike Argandona). El README indica la licencia y el autor.
- Sin cambios de funcionalidad, estructura ni configuración. La firma «Skill created by Kike Argandona» sigue en todos los PDF.

## 2.0.0 (2026-10-27)

### Comportamiento unificado (solo PDF)
- Se retiran `scripts/sqd.py` y `templates/instrumento.csv`: la entrega es solo PDF. Se corrigen todas las referencias al CSV en `reference/` y `guias/`.
- **Comisión y triple swap** se rellenan cuando hay evidencia (ya no quedan vacíos para rellenar a mano).
- **Tick real**: `No Pip/Tick` es el tick mínimo de cada instrumento. `÷ 10` solo en forex; en el resto, tick value ÷ contrato. El validador avisa si se aplica `÷ 10` fuera de forex.
- **Comisión ida y vuelta**: comisión por orden de Darwinex × 2, comprobada por el script. La evidencia está en `reference/verificacion-fuentes.md`; la prueba en build 143 sigue pendiente.
- `PENDIENTE DE VERIFICAR` en cualquier dato, con su motivo. La tabla queda **INCOMPLETA**: el PDF lleva `_INCOMPLETA` en el nombre, un aviso bajo el título y las casillas en rojo.

### Validación (`tabla.py validar`)
- Pip/Tick, No Pip/Tick y Point Value > 0; spread y comisión ≥ 0; los swaps admiten cualquier signo.
- Fechas y horas reales (rechaza 2026-02-30, 25:00, fechas futuras y fuentes posteriores a la consulta).
- Tipos de datos (números entre comillas, listas, objetos) y JSON vacío, dañado o con la raíz equivocada, con mensajes que indican línea y columna.
- **Fuentes estructuradas (esquema 2)**: `dato` (url + fecha), `observado` (spread: + hora UTC, unidad y lectura), `calculo` (fórmula + entradas con sus fuentes), `regla`, `pendiente`. Formato en `reference/formato-json.md`.
- Coherencia: conversión del spread, comisión × 2, point value = contrato, tick = tick value ÷ contrato.
- Estados **COMPLETA / INCOMPLETA / NO VÁLIDA**: tener texto en todas las casillas ya no basta para que una tabla cuente como completa.
- Orden `migrar` para pasar los JSON v1 al v2. Guarda una copia `.json.v1` y señala lo que falta completar.

### PDF portable
- Detecta Chrome, Edge, Chromium o Brave en macOS, Windows y Linux. Opción `--navegador` / `SQD_NAVEGADOR` (en macOS admite el paquete `.app`).
- Mensaje con ejemplos si no hay navegador. Repite con `--headless` en navegadores antiguos y usa `--no-sandbox` en Linux como root.
- Comprueba que el PDF es válido (cabecera, `%%EOF`, al menos una página) antes de sustituir el archivo; si falla, no deja un PDF roto.
- Los símbolos usados en nombres de archivo solo admiten `A-Z 0-9 . _ -`, sin `..`, y la ruta final se comprueba dentro de la carpeta de datos. El texto mostrado en el PDF (p. ej., `DAX / GDAXI`) se separa de la clave del archivo (`DAX_GDAXI.json`).

### Perfil configurable
- `config/perfil.json`: Darwinex · MT5 · USD · Dukascopy (SQ default) clonado a «(EST+07) New York Trading hours, US DST», con los **ajustes personales** del autor (slippage 0, min dist. 0, order mult. 1, order step 0.01, rollover 23:59). Se puede sustituir con `DATA/perfil.json`, `SQD_PERFIL` o `--perfil`.
- Las dos tablas y la firma «Skill created by Kike Argandona» se mantienen.

### Entrega
- README (instalación, requisitos, uso, ejemplos, limitaciones), ejemplos reales en `examples/`, 66 pruebas en `tests/` y `.gitignore`.
- `templates/confirmado.md` sin datos personales.
- Licencia: pendiente de decisión del autor (resuelto en 2.0.1: MIT).

### Migración desde 1.x
Los JSON antiguos de `~/strategyquant-darwinex-datos/tablas/` no son válidos en v2 y quedan fuera del PDF acumulado hasta que se migren: `tabla.py migrar <SÍMBOLO>` y completar las entradas de los cálculos que indique.
