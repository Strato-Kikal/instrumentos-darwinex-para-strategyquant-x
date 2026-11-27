# Datos de prueba

Respuestas reales capturadas el 2026-11-26 (~20:15 UTC) para que las pruebas no dependan de la red:
`darwinex.json` (subconjunto del JSON de condiciones de Darwinex), `precios.json` (feed de spread),
`bce.xml` (tipos del BCE) y `costes.html` (fragmento de help.darwinex.com/execution-costs).

El spread medio de Forex Benchmark no se guarda como archivo: los valores reales del 2026-11-27 01:22 UTC
(Darwinex, 24 hours, 30 days, sin comisión) están en `FXB` de `apoyo.py`, porque en la app los escribe el usuario.

Solo se usan en las pruebas automáticas. La aplicación siempre consulta las fuentes en el momento.
