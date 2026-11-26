# Control de coherencia antes del custom project

Lista para que el usuario la revise en StrategyQuant al introducir la tabla. La skill no pide capturas de sus símbolos ni instrumentos ni los compara: solo marca los puntos que dependen de las fuentes y de la tabla. Generar el PDF no valida la configuración de StrategyQuant.

## Símbolo ↔ instrumento
- [ ] El símbolo (o su clon) apunta al instrumento cuya tabla se ha preparado (captura de la fila del símbolo en Data manager).
- [ ] El nombre de Instrument coincide con el «Nombre recomendado» del PDF.

## Datos ↔ horario
- [ ] En Edit symbol del símbolo que usará el proyecto, Timezone = «(EST+07) New York Trading hours, US DST, DST: Yes» y Bar type = start of bar. Si Timezone dice otra cosa (p. ej., UTC/GMT), los datos no están en hora de Darwinex.
- [ ] Descarga con SQ default (UTC) y un solo clon a (EST+07). Nunca el perfil [[Darwinex]] más un clon.
- [ ] Apertura semanal el lunes a las 00:00-00:05 de Darwinex, sin barras de domingo.
- [ ] Prueba de las semanas de desfase entre EE. UU. y la UE superada (horarios.md).
- [ ] El periodo de datos no empieza antes de 2007, o se ha revisado aparte.

## Instrumento ↔ bróker
- [ ] Default spread = lectura real con hora UTC; slippage, multiplier, step, min distance y Rollout hour = ajustes personales del perfil (`tabla.py perfil`).
- [ ] Pip/Tick size × contrato = pip value publicado por Darwinex.
- [ ] Pip/Tick step = tick real (forex: Pip/Tick size ÷ 10; resto: tick value ÷ contrato). Confirmado en MT5 → Especificación.
- [ ] Point value convertido desde la divisa **cotizada** a USD con un tipo fechado.
- [ ] Commission = comisión por orden × 2 (ida y vuelta), sin duplicarla otra vez; Triple swap on = día de la nota de Darwinex.
- [ ] Swaps: unidad de Swap type igual a la del valor introducido; tipo de cambio fechado.

## Instrumento ↔ custom project
- [ ] El custom project usa el símbolo clonado o convertido, no el de origen en UTC.
- [ ] Si el proyecto sobrescribe el spread o el slippage del instrumento, el usuario lo sabe y lo ha decidido así.
- [ ] Sesión/horario del proyecto coherente con la zona de los datos.

Si algún punto queda en ✗, explica la discrepancia, devuelve la casilla afectada a «PENDIENTE DE VERIFICAR» en el JSON y vuelve a generar el PDF (saldrá como INCOMPLETA).
