# Backend - Migraciones y Autenticacion

## Migraciones

InfoMatt360 usa Alembic para versionar cambios de base de datos.

Comandos principales:

```bash
cd backend
alembic upgrade head
alembic revision --autogenerate -m "descripcion"
```

## Base de datos

En desarrollo puede usarse SQLite. En produccion debe usarse PostgreSQL.

Variable requerida:

```env
DATABASE_URL=postgresql://usuario:clave@host:5432/infomatt360
```

## Autenticacion

Se agrego modulo inicial de autenticacion con:

- hash de contrasena;
- login por correo y contrasena;
- token JWT;
- usuario unico para web, Android y escritorio.

Endpoint inicial:

```text
POST /api/v1/auth/login
GET /api/v1/auth/session
POST /api/v1/auth/logout
POST /api/v1/auth/refresh
GET  /api/v1/auth/mfa/status
POST /api/v1/auth/mfa/setup
POST /api/v1/auth/mfa/confirm
POST /api/v1/auth/mfa/verify
POST /api/v1/auth/mfa/disable
POST /api/v1/auth/password/change
POST /api/v1/auth/password/forgot
POST /api/v1/auth/password/reset
```

La recuperacion usa tokens aleatorios de un solo uso, guarda solamente su hash,
expira a los 30 minutos e invalida las sesiones anteriores al cambiar la clave.
La respuesta de solicitud es deliberadamente igual exista o no la cuenta. El
enlace se entrega por SMTP sin guardar el token en claro.

La proteccion contra abuso registra solamente identificadores HMAC, no correos
ni direcciones en texto claro. El ingreso permite cinco fallos por combinacion
correo/IP en 15 minutos y mantiene un limite global por IP. La recuperacion
permite tres solicitudes por correo/IP cada hora, siempre con respuesta neutral.

El cierre de sesion incrementa la version de autenticacion del usuario, por lo
que revoca inmediatamente todos sus JWT activos, incluso en otros dispositivos.

El refresh token dura siete dias, se almacena solamente como SHA-256 y rota en
cada uso. La reutilizacion de un token ya rotado se trata como posible robo:
revoca la familia, invalida los JWT y genera un evento de auditoria.

MFA usa TOTP compatible con aplicaciones autenticadoras. El secreto se cifra
con una clave derivada de `SECRET_KEY`; los ocho codigos de recuperacion se
muestran una sola vez y se almacenan como HMAC. Los codigos TOTP aceptados no
pueden reutilizarse y los intentos de verificacion tienen limitacion por IP.

```env
FRONTEND_URL=https://app.ejemplo.com
SMTP_HOST=smtp.ejemplo.com
SMTP_PORT=587
SMTP_USERNAME=usuario
SMTP_PASSWORD=secreto
SMTP_FROM_EMAIL=no-reply@ejemplo.com
SMTP_USE_TLS=true
```

## Nota de seguridad

La variable SECRET_KEY debe cambiarse obligatoriamente en produccion.

```env
SECRET_KEY=valor_largo_y_seguro
```

## Pendientes

- evaluar WebAuthn/passkeys como segundo factor adicional.
