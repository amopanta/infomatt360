# Organizaciones (tenant logico)

## Objetivo

Agrupar proyectos bajo un mismo cliente/marca sin usar un schema fisico de
base de datos por tenant. El aislamiento es logico: se filtra por
`organization_id` a traves de `project_id`, reutilizando el 100% del modelo
de datos y permisos ya existente por proyecto.

## Modelo

- `Organization` (`backend/app/models/organization.py`): `id`, `name`, `slug`
  (unico, usado en URLs y en branding publico), `status`, `created_at`.
- `Project.organization_id`: columna agregada (migracion `0040_organizations.py`),
  nullable para no romper proyectos existentes y con backfill a una
  organizacion `default`.
- No hay tabla de relacion usuario-organizacion: la organizacion de un
  usuario se resuelve transitivamente via `project_id -> Project.organization_id`.

## JWT con contexto de organizacion

`create_access_token()` (`backend/app/core/security.py`) acepta un parametro
opcional `organization_id`, que si se provee se agrega al payload como
`"org"`. `get_current_user` (`backend/app/api/deps.py`) lee ese campo y lo
expone como `user.active_organization_id`. El campo es opcional en el
payload: tokens emitidos antes de este cambio siguen siendo validos.

## Endpoints

| Metodo | Ruta | Permiso |
| --- | --- | --- |
| `POST` | `/api/v1/organizations/` | `organizations.manage` |
| `GET` | `/api/v1/organizations/` | `organizations.manage` |
| `PUT` | `/api/v1/organizations/{id}/branding` | `organizations.branding.manage` u `organizations.manage` |
| `GET` | `/api/v1/organizations/{id}/branding` | `organizations.branding.manage` u `organizations.manage` |

## Limites conocidos

- No hay pantalla de administracion de organizaciones en el frontend todavia
  (solo API); se gestiona por Swagger o script hasta que se priorice esa UI.
- El slug de organizacion es global (unico en toda la base), no por cliente.
