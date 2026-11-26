# Guía: símbolo, descarga y clonación (build 143)

Pasos solo con lo documentado por StrategyQuant. Lo marcado con **[captura]** no está documentado para build 143: antes de dar esa instrucción, pide al usuario la captura indicada y guarda en `DATA/confirmado.md › Interfaz build 143` (copia de `templates/confirmado.md`) lo que muestre, para no volver a pedirla.

## Camino horario del perfil (predeterminado)

Descargar de Dukascopy con Broker profile **SQ default** (UTC) y **clonar** a **«(EST+07) New York Trading hours, US DST»** (`datos` del perfil). No se pregunta. Nunca descargues con el perfil [[Darwinex]] y clones además, porque la hora se convertiría dos veces.

## 1. Símbolo: ventana «Edit symbol» (confirmada con captura el 2026-10-19)

Bloques:
- **Data settings**:
  - **Data symbol name** (editable).
  - **Bar type** (solo lectura; p. ej., «Timestamp represents start of bar time (MetaTrader, Dukascopy, forex data)»).
  - **Timezone** (solo lectura; p. ej., «(EST+07) New York Trading hours, US DST, DST: Yes»).
- **Choose instrument**:
  - **Instrument \*** = filtro de broker profile + desplegable de instrumento + enlace **Add new instrument**.
  - Opciones del filtro: All broker profiles, SQ default, [[Darwinex]], [[Dukascopy]], [[FTMO]], [[ICMarkets]], [[Monevis]], [[OANDA]], [[Pepperstone]], [[RoboForex]], [[The5ers]]. Los nombres entre [[ ]] son perfiles predefinidos de SQ.
- **Vista del instrumento**: las casillas de Edit instrument en gris (solo lectura). El bloque Swap tiene botón **Help**. El bloque de comisiones no aparece aquí.
- **Close** / **Save**.

Pasos:
1. El símbolo se crea al descargar (paso 2). Después, en Edit symbol del clon, comprueba que Timezone sea «(EST+07) New York Trading hours, US DST, DST: Yes».
2. En Choose instrument, filtra por el broker profile del instrumento preparado y elige el instrumento de la tabla (PDF). Si no existe, **Add new instrument** abre «Edit instrument», que se rellena con la tabla.
3. Las casillas grises se revisan, no se editan aquí. Si alguna no coincide con la tabla, hay que corregirla en el instrumento (Edit instrument), no en el símbolo.

## 2. Descarga Dukascopy: ventana «Add Dukascopy data» (confirmada con captura el 2026-10-19)

Controles, de arriba abajo: buscador · **Show types** (desplegable, «All») · tabla con casilla, **Symbol**, **Name**, **Available M1 data range**, **Available Tick data range**, agrupada por tipo (p. ej., «Forex - Majors») · **Data type** (Tick data / M1 data) · **Broker profile \*** (desplegable, por defecto «SQ default») · **Data postfix** (texto: «This postfix will be optionally added to the data names created») · interruptor de confirmación del aviso de Dukascopy · **Close** / **Save**.

1. Escribe el activo en el buscador y marca **solo** su casilla en la tabla. No marques la casilla del grupo, que selecciona todo el grupo.
2. Anota el rango disponible que muestra la tabla (p. ej., EURUSD: M1 y Tick desde 2003.05.05). Si empieza antes de 2007, avisa: EE. UU. tenía otras fechas de horario de verano (ver horarios.md).
3. **Data type**: M1 data para la mayoría de estrategias; Tick data solo si la estrategia lo requiere (SQ-TZ). Esta casilla es el tipo de **descarga** y no tiene nada que ver con «Data type» de Edit instrument (Forex).
4. **Broker profile**: **SQ default** (datos en UTC; se clonan después).
5. **Data postfix**: el sufijo de la convención de `confirmado.md` (p. ej., uno que identifique el perfil o la zona). Vacío solo si la convención lo dice.
6. Activa el interruptor de confirmación y pulsa **Save**.
7. Esta ventana **no tiene selector de fechas ni de zona horaria**. No des instrucciones sobre eso aquí; si el usuario quiere limitar el periodo, pide captura de dónde lo hace en build 143.
8. Espera a que termine (la pestaña Log muestra el progreso por año, según SQ-SCREENS).

## 3. Clonación horaria

1. **[captura: opción de clonar en build 143 y su desplegable de zona horaria]**. QuantDataManager documenta el clonado a otra zona («Clone to a different timezone») con la zona `EETUS` (UTC+2 con horario de verano de EE. UU.). Comprueba en la captura que build 143 ofrece esa misma opción y cómo se llama.
2. Origen: el símbolo Dukascopy en UTC. Destino: la zona de Darwinex (ver [../reference/horarios.md](../reference/horarios.md)). **Nunca** «EET» a secas ni un desplazamiento fijo.
3. Nombre del clon según la convención de `confirmado.md`, que deje claro la zona (p. ej., sufijo de la convención).
4. Instrumento del clon: el instrumento de Darwinex preparado con la tabla (PDF).

## 4. Comprobar la hora

Sigue «Cómo saber en qué hora están unos datos» y «Comprobación de verano/invierno» en [../reference/horarios.md](../reference/horarios.md) con capturas del usuario. Hasta entonces, la zona de los datos no está verificada.
