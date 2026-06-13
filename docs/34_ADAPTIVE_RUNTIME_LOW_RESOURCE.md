# Runtime Adaptativo para Bajos Recursos

## Objetivo
Garantizar fluidez en tablets o equipos modestos y aprovechar mejor dispositivos potentes.

## Implementado

```text
deviceProfile.ts
useVirtualWindow.ts
RuntimeRepeat virtualizado
```

## Modos

```text
low      -> ventana repeat 5
balanced -> ventana repeat 12
fast     -> ventana repeat 25
```

## Criterio
El Runtime detecta memoria y nucleos disponibles. En equipos de bajo recurso reduce elementos visibles; en equipos mejores aumenta la ventana.

## Beneficio

- Menor uso de memoria.
- Menos bloqueos.
- Mejor experiencia en tablets.
- Mayor velocidad en equipos potentes.

## Siguiente paso

Integrar REPEAT como componente real desde Runtime JSON y luego conectar el recalculador reactivo.
