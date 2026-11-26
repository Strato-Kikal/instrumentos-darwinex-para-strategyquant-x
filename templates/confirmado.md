# Datos confirmados por el usuario (Instrumentos Darwinex para StrategyQuant X)

Copia esta plantilla a `DATA/confirmado.md` (por defecto `~/strategyquant-darwinex-datos/confirmado.md`). Guarda aquí solo lo que el usuario haya confirmado, con fecha (AAAA-MM-DD), para no volver a pedirlo. El bróker, la plataforma, la divisa, los datos y los ajustes personales están en el perfil (`tabla.py perfil`), no aquí.

## StrategyQuant
- Build: 143
- Broker profile que usa:
- Convención de nombres (símbolo, clon, Instrument, Description):

## Interfaz build 143 confirmada con capturas
Pantallas ya vistas en capturas de la build 143 (2026-10-19). Si tu build muestra otra cosa, corrígelo aquí.
- Edit instrument: 20 casillas. Modelo Size based → muestra solo «Commission». Swap type = money → Long/Short en «$ per day».
- Add Dukascopy data: buscador, Show types, tabla Symbol/Name/Available M1 data range/Available Tick data range, Data type (Tick data/M1 data), Broker profile * (por defecto SQ default), Data postfix, interruptor de confirmación, Close/Save. Sin selector de fechas ni de zona horaria. Falta: ventana de clonado.
- Edit symbol: Data symbol name, Bar type y Timezone (solo lectura), Choose instrument (filtro de broker profile + instrumento + Add new instrument), vista gris del instrumento, Swap con Help. Broker profiles: SQ default, [[Darwinex]], [[Dukascopy]], [[FTMO]], [[ICMarkets]], [[Monevis]], [[OANDA]], [[Pepperstone]], [[RoboForex]], [[The5ers]]. Zona de Darwinex: «(EST+07) New York Trading hours, US DST, DST: Yes».
- Ventana de clonado:

## Comprobaciones hechas en StrategyQuant
- Comisión ida y vuelta (backtest de 1 operación, ver reference/verificacion-fuentes.md):

## Activos preparados
| Activo | Tabla (PDF) | Estado |
|--------|-------------|--------|
