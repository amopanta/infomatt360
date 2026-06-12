# Backend - Participantes

## Objetivo
Crear el modulo base de participantes como eje central de InfoMatt360.

## Archivos agregados

```text
backend/app/models/participants.py
backend/app/schemas/participants.py
backend/app/services/participant_service.py
backend/app/api/v1/participants.py
backend/alembic/versions/0005_participants_base.py
```

## Capacidades iniciales

- crear participante por proyecto;
- listar participantes por proyecto;
- guardar codigo externo;
- guardar documento;
- guardar nombre completo;
- clasificar tipo de participante;
- guardar metadata flexible en JSON;
- validar acceso al proyecto antes de operar.

## Endpoints

```text
POST /api/v1/participants/
GET /api/v1/participants/project/{project_id}
```

## Rol dentro del sistema

El participante sera el punto de relacion entre:

- formularios;
- registros;
- evidencias;
- actas;
- visitas;
- aprobaciones;
- reportes;
- integraciones;
- historial operativo.

## Pendientes

- control avanzado de duplicados;
- participantes tipo hogar o nucleo familiar;
- relaciones entre participantes;
- historial de cambios;
- busqueda avanzada;
- carga masiva desde Excel;
- importacion desde integraciones externas.
