# Marca blanca dinamica (branding)

## Objetivo

Permitir que cada organizacion (ver [71_ORGANIZACIONES_TENANT_LOGICO.md](71_ORGANIZACIONES_TENANT_LOGICO.md))
configure su propio logo, colores y eslogan, aplicados en el frontend sin
necesidad de recompilar ni desplegar una version distinta por cliente.

## Modelo

`OrganizationBranding` (`backend/app/models/organization.py`): una fila por
organizacion (`organization_id` unico), con `logo_url`, `primary_color`,
`accent_color`, `background_color`, `slogan`, `updated_at`. El logo se
referencia por URL (puede apuntar a un archivo ya subido via el modulo de
files); branding no gestiona su propio almacenamiento de imagenes.

## Endpoints

| Metodo | Ruta | Auth | Uso |
| --- | --- | --- | --- |
| `GET` | `/api/v1/public/branding?slug=...` | Ninguna | Precarga antes de iniciar sesion (web y PWA) |
| `PUT` | `/api/v1/organizations/{id}/branding` | `organizations.branding.manage` | Configurar marca |
| `GET` | `/api/v1/organizations/{id}/branding` | `organizations.branding.manage` | Consultar configuracion actual |

## Frontend

`frontend/src/modules/branding/brandingLoader.ts`:

- `applyFallbackBranding()` aplica de inmediato los colores por defecto
  (`theme/brand.ts`) para no bloquear el primer render mientras se resuelve
  la marca real.
- `loadOrganizationBranding()` consulta `/public/branding?slug=<VITE_ORG_SLUG>`,
  aplica los colores como variables CSS (`--brand-primary`, `--brand-accent`,
  `--brand-background`) sobre `document.documentElement`, y cachea el
  resultado en `localStorage` (`infomatt360_branding_cache`).
- Si la peticion falla (sin red, organizacion aun no configurada), usa el
  ultimo branding cacheado en vez de romper el render; si tampoco hay cache,
  se queda con el fallback.
- `useOrganizationBranding()` es el hook que consumen componentes como
  `BrandLogo` para mostrar el logo/nombre de la organizacion activa.

## Configuracion

`VITE_ORG_SLUG` (frontend) determina que organizacion se carga; por defecto
`default`. En un despliegue multi-organizacion real, cada dominio/subdominio
apuntaria a un build con su propio `VITE_ORG_SLUG`.

## Limites conocidos

- El manifest de la PWA (ver [83_PWA_OFFLINE_INSTALABLE.md](83_PWA_OFFLINE_INSTALABLE.md))
  es estatico y no refleja el branding dinamico: queda con la identidad
  generica de la plataforma. Una PWA instalable por organizacion requeriria
  generar el manifest por subdominio, fuera de alcance de este corte.
- No hay validacion de contraste/accesibilidad sobre los colores que
  configura el administrador.
