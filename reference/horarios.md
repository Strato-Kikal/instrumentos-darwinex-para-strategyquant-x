# Horarios: origen, destino y verano/invierno

## Hechos verificados (2026-10-19; revalidar en cada tabla)

- **Origen, Dukascopy en SQ**: el histórico descargado llega en **UTC**, sin horario de verano (SQ-TZ). Si un dato parece contradecirlo, quien manda es la captura de la ventana de descarga de build 143.
- **Destino, servidor MT4/MT5 de Darwinex y Darwinex Zero**: **GMT+2** cuando EE. UU. está en horario de invierno y **GMT+3** durante el horario de verano de EE. UU. Es el «cierre de Nueva York» (DX-TIME, DXZ-TIME): las 17:00 de Nueva York son siempre las 00:00 del servidor.
- Horario de Darwinex (DX-FX): apertura el domingo a las 17:05 NY (lunes 00:05 servidor), cierre el viernes a las 16:55 NY (viernes 23:55 servidor). **No hay barras de domingo en hora del servidor.**

## Reglas

1. **Nunca un desplazamiento fijo** (+2 o +3 todo el año). El destino cambia con el calendario de **EE. UU.** (2.º domingo de marzo → 1.er domingo de noviembre desde 2007), no con el europeo (último domingo de marzo → último de octubre).
2. En build 143, la zona de Darwinex aparece como **«(EST+07) New York Trading hours, US DST, DST: Yes»** (campo Timezone de Edit symbol, captura del 2026-10-19). EST+7 = UTC+2 en invierno y UTC+3 con el horario de verano de EE. UU., la misma regla que el servidor de Darwinex (DX-TIME). En la documentación de QDM esa zona se llama `EETUS`. Falta la captura del desplegable de clonado para confirmar que allí aparece con el mismo texto. Cualquier zona «EET» que siga el calendario europeo desfasa 1 h durante 2-3 semanas en primavera y 1 semana en otoño.
3. **No convertir dos veces.** Desde build 141, si se descarga con un **Broker profile** de bróker (por ejemplo, Darwinex), SQ ya convierte los datos a la zona del bróker (SQ-SCREENS). Entonces no se clona con desplazamiento horario. Solo se clona si el símbolo de origen está en UTC (perfil SQ default).
4. Si el periodo histórico incluye años anteriores a 2007, las reglas de EE. UU. eran otras. Avisa y comprueba esas fechas aparte.

## Cómo saber en qué hora están unos datos (sin suponerlo)

Pide al usuario una captura del gráfico o de la tabla de datos del símbolo en SQ con barras M1 o H1 alrededor de:
- **Apertura semanal**: en UTC la primera barra es el domingo hacia las 21:00 (verano EE. UU.) o las 22:00 (invierno). En hora de Darwinex es el lunes a las 00:00-00:05.
- **Cierre del viernes**: en UTC hacia las 20:55-21:00 (verano) o 21:55-22:00 (invierno). En hora de Darwinex, hacia las 23:55.
- **Velas diarias**: con el horario de Darwinex hay 5 por semana, sin vela de domingo.

## Comprobación de verano/invierno (tras clonar)

Elige un año del periodo y revisa la primera barra de la semana en estas tres fechas:
- La semana entre el cambio de EE. UU. y el europeo en marzo, por ejemplo, del 10 al 31 de marzo de 2024: debe seguir abriendo el lunes a las 00:00 del servidor.
- Una semana de pleno verano.
- La semana entre el cambio europeo y el de EE. UU. en otoño, por ejemplo, del 27 de octubre al 3 de noviembre de 2024.

Si en esas semanas la apertura cae a las 23:00 del domingo o a las 01:00 del lunes, el clon siguió el calendario europeo o se aplicó un desplazamiento fijo.

## Coherencia con el instrumento

Rollout hour es un ajuste personal del perfil (predeterminado 23:59). Triple swap on sale de la nota de la tabla de Darwinex (ver tabla-reglas.md).
