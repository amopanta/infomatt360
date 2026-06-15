# Form Compiler v1

## Estado
Implementacion inicial agregada al backend.

## Objetivo
Convertir Template JSON del Builder en Runtime Package optimizado.

## Endpoint

```text
POST /api/v1/compiler/compile
```

## Entrada minima

```json
{
  "id": "tpl-cert-001",
  "name": "CERT-001",
  "fields": [
    { "name": "cantidad", "label": "Cantidad", "type": "number" },
    { "name": "precio", "label": "Precio", "type": "number" },
    { "name": "subtotal", "label": "Subtotal", "type": "calculate", "config": { "calculate": "${cantidad} * ${precio}" } }
  ]
}
```

## Salida

```text
manifest
schema
dependency_graph
expression_map
pulldata_map
performance_profile
version
```

## Capacidades implementadas

- contratos Pydantic de Runtime Package;
- extraccion de campos;
- extraccion de expresiones;
- extraccion de dependencias usando ${campo};
- generacion de dependency_graph;
- deteccion de ciclos;
- perfil basico de complejidad;
- API de compilacion.

## Criterio de certificacion parcial
Este bloque mueve CERT-001-B de diseno a implementacion inicial. Todavia falta probar contra el formulario completo CERT-001.
