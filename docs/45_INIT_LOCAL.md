# Inicializacion local

## Objetivo

Preparar archivos minimos para arrancar InfoMatt360 en una estacion de desarrollo
sin sobrescribir configuraciones existentes.

## Comando

Desde la raiz del proyecto:

```powershell
.\scripts\init-local.cmd
```

## Que hace

- Crea `backend\.env` desde `.env.example` si aun no existe.
- Crea `backend\uploads` si aun no existe.
- No sobrescribe `backend\.env` por defecto.

## Sobrescribir `.env`

Solo si se desea regenerar el archivo local desde `.env.example`:

```powershell
.\scripts\init-local.cmd -ForceEnv
```

## Flujo recomendado

```powershell
.\scripts\init-local.cmd
.\scripts\doctor.cmd
.\scripts\seed-demo.cmd
.\scripts\dev-backend.cmd
```
