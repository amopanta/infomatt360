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
```

## Nota de seguridad

La variable SECRET_KEY debe cambiarse obligatoriamente en produccion.

```env
SECRET_KEY=valor_largo_y_seguro
```

## Pendientes

- agregar cambio de contrasena;
- agregar refresh token;
- agregar permisos por proyecto;
- agregar middleware de usuario actual;
- agregar bloqueo por intentos fallidos;
- agregar MFA opcional.
