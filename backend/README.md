# Backend InfoMatt360

Backend principal de InfoMatt360 construido con FastAPI.

## Objetivo
Servir como nucleo API para:

- autenticacion;
- proyectos;
- usuarios;
- roles y permisos;
- formularios;
- participantes;
- registros;
- evidencias;
- sincronizacion;
- integraciones;
- reportes;
- auditoria;
- IA/OCR.

## Estructura inicial

```text
backend/
  app/
    main.py
    core/
      config.py
    api/
      v1/
        router.py
        health.py
  tests/
  requirements.txt
```

## Ejecucion local

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

## Endpoints iniciales

- `GET /health` estado simple del servicio.
- `GET /api/v1/health` estado versionado de API.

## Reglas de desarrollo

- Todo endpoint debe tener descripcion.
- Toda logica critica debe estar comentada.
- Todo modulo debe tener pruebas.
- Todo cambio debe respetar la arquitectura multi proyecto.
