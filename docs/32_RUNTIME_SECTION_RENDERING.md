# Runtime por Seccion Activa

## Objetivo
Reducir aun mas la carga de formularios grandes. Ahora el Runtime renderiza una pagina activa y, dentro de esa pagina, una sola seccion activa.

## Implementado

```text
RuntimeSectionNavigator
RuntimeRenderer con activeSectionIndex
CSS para navegacion de secciones
```

## Beneficio
Un formulario con muchas secciones y 400+ campos ya no coloca todo el contenido en el DOM. Esto mejora carga, memoria y respuesta en tablets.

## Siguiente paso

```text
Repeats virtualizados
Reconciliacion de cantidad
Recalculador reactivo
```
