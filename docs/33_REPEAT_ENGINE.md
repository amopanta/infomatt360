# Repeat Engine Inteligente

## Objetivo
Resolver una falla frecuente en Kobo/ODK: cuando cambia la cantidad de elementos de un repeat, el formulario deja elementos sobrantes o se vuelve dificil de editar.

## Implementado

```text
repeatEngine.ts
RuntimeRepeat.tsx
```

## Regla principal

```text
cantidad esperada = 6 -> 6 items
cantidad esperada = 5 -> conserva primeros 5 y elimina sobrante
cantidad esperada = 8 -> conserva 5 y agrega 3 nuevos
```

## Beneficio

- Edicion mas sencilla en tablet.
- Menos inconsistencias.
- Mejor experiencia que Kobo para grupos agregar.

## Pendiente

- Recalcular dependientes al cambiar cantidad.

## Integracion Runtime

Los componentes `REPEAT` usan `config_json.count_field` para tomar la cantidad
desde otro campo, o `config_json.count` para una cantidad fija. La reconciliacion
se ejecuta como efecto de React, conserva identificadores y valores estables,
elimina sobrantes y ajusta la ventana virtual al reducir la lista.
