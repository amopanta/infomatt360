# Doctor de entorno local

## Objetivo

Revisar rapidamente si la estacion tiene lo minimo para trabajar con InfoMatt360
sin ejecutar pruebas pesadas ni depender de internet.

## Comando

Desde la raiz del proyecto:

```powershell
.\scripts\doctor.cmd
```

## Revisa

- Estructura critica del proyecto.
- Python del backend dentro de `backend\.venv`.
- Existencia y riesgos visibles de `backend\.env`.
- Node y npm.
- `frontend\node_modules`.
- Cache TypeScript offline usada por el preflight.
- Git disponible.

## Interpretacion

- `FALLO`: falta algo necesario para operar localmente.
- `ADVERTENCIA`: el proyecto puede funcionar localmente, pero hay una accion
  pendiente o una configuracion que debe corregirse antes de produccion.

La advertencia esperada en esta estacion es que `frontend\node_modules` aun no
existe porque `npm install` no ha logrado completar por conectividad con el
registro npm.
