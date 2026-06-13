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

- Integrar REPEAT como tipo real de componente Runtime.
- Virtualizar listas largas.
- Recalcular dependientes al cambiar cantidad.
