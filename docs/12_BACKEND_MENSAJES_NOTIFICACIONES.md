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
- validar que remitente y destinatario pertenezcan al proyecto;
- listar bandeja de entrada del usuario autenticado;
- listar mensajes enviados;
- consultar conteos de mensajes;
- marcar mensajes como leidos o archivados;
- validar acceso al proyecto antes de operar;
- recibir notificaciones automaticas generadas por cambios de estado en revision.

## Endpoints

```text
POST /api/v1/messages/profiles
GET /api/v1/messages/profiles/{project_id}
POST /api/v1/messages/internal
GET /api/v1/messages/internal/{project_id}
GET /api/v1/messages/internal/{project_id}/inbox
GET /api/v1/messages/internal/{project_id}/sent
GET /api/v1/messages/internal/{project_id}/counts
PATCH /api/v1/messages/internal/{project_id}/{message_id}
```

## Frontend

Pantalla disponible:

```text
/messages
```

Incluye:

- tarjetas de no leidos, recibidos y enviados;
- redaccion de mensaje interno;
- bandeja de recibidos/enviados;
- accion para marcar como leido.

## Pendientes

- envio real SMTP;
- lectura IMAP;
- plantillas de correo;
- adjuntos;
- cola de envio;
- reintentos;
- auditoria de envio;
- preferencias por usuario.
