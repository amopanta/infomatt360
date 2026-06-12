# Backend - Mensajes y Notificaciones

## Objetivo
Crear la base para perfiles de correo por proyecto y bandeja interna.

## Archivos agregados

```text
backend/app/models/messages.py
backend/app/schemas/messages.py
backend/app/services/message_service.py
backend/app/api/v1/messages.py
backend/alembic/versions/0009_messages.py
```

## Capacidades iniciales

- crear perfil de correo por proyecto;
- listar perfiles de correo;
- crear mensaje interno;
- listar mensajes internos del usuario autenticado;
- validar acceso al proyecto antes de operar.

## Endpoints

```text
POST /api/v1/messages/profiles
GET /api/v1/messages/profiles/{project_id}
POST /api/v1/messages/internal
GET /api/v1/messages/internal/{project_id}
```

## Pendientes

- envio real SMTP;
- lectura IMAP;
- notificaciones por flujo;
- plantillas de correo;
- adjuntos;
- cola de envio;
- reintentos;
- auditoria de envio;
- preferencias por usuario.
