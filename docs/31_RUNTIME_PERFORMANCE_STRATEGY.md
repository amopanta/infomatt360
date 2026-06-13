# Estrategia de Performance Runtime

## Objetivo
Evitar bloqueos en formularios grandes de 400+ campos como los que hoy se paralizan en Kobo/ODK.

## Decision tecnica
El Runtime no renderiza todo el formulario al mismo tiempo. Renderiza solo la pagina activa.

## Implementado

```text
RuntimeStepper
useRuntimeDraft
Render por pagina activa
Borrador local automatico
```

## Beneficios

- Menos carga inicial.
- Menos nodos HTML en pantalla.
- Menos riesgo de bloqueo en tablet.
- Recuperacion de datos si el usuario cierra o pierde conexion.

## Siguientes mejoras

```text
render por seccion activa
virtualizacion de repeats
motor reactivo de calculos
cache de pulldata
reconciliacion de repeats
sincronizacion incremental
```

## Criterio de exito
Un formulario de certificacion de 400+ campos debe abrir por paginas, permitir navegacion rapida y guardar borrador local sin perder datos.
