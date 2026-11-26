# Cambios

## Sin publicar: aplicación «Instrumentos SQX» (rama `app-independiente`)

- Nueva carpeta `app/`: aplicación web instalable (PWA) y servidor en Python (solo biblioteca estándar) que preparan la tabla de un símbolo sin Claude: consultan Darwinex, el feed de spread, el BCE y la página de costes de Darwinex, aplican las reglas de `reference/`, validan con `tabla.validar()` y generan el PDF (página 1 igual que la de la skill + anexo de fuentes, fechas, fórmulas y ajustes). Ver `app/README.md`.
- 46 pruebas nuevas en `app/tests/` y un paso más en GitHub Actions.
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
