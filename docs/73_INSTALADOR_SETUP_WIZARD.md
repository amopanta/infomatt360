# Instalador de primer arranque (Setup Wizard)

## Objetivo

Permitir que un despliegue nuevo de InfoMatt360 cree su primera
organizacion, proyecto y usuario administrador desde el navegador, sin
requerir un script de seed manual.

## Estado por defecto: inerte

El instalador solo bloquea el sistema cuando `installer_enforced=true` en la
configuracion (`backend/app/core/config.py`, por defecto `False`). Con el
flag desactivado, `GET /api/v1/install/status` siempre reporta
`installed: true` y el middleware no interfiere con ningun despliegue
existente. Este es el estado actual de la demo e instalaciones ya
configuradas por seed.

## Modelo

`InstallationState` (`backend/app/models/installation.py`): tabla singleton
(una sola fila). Su ausencia se interpreta como "instalado" cuando
`installer_enforced` esta desactivado.

## Flujo

1. `GET /api/v1/install/status` -> `{ installed, installer_enforced }`.
2. Si `installed=false`, el frontend muestra el wizard en `/install`
   (`frontend/src/modules/install/InstallWizardApp.tsx`): pide nombre y slug
   de organizacion, nombre de proyecto, y datos del usuario administrador.
3. `POST /api/v1/install/bootstrap` (sin autenticacion, por diseno: se usa
   antes de que exista ningun usuario) crea en una sola transaccion:
   - La `Organization` y su primer `Project`.
   - Un `Role` "Administrador" con `ALL_PERMISSIONS` del catalogo.
   - El `User` administrador con su asignacion al proyecto.
   - Marca `InstallationState.is_installed=true`.
4. Reintentar `bootstrap` despues de instalado devuelve `409 Conflict`
   ("El sistema ya esta instalado") — la operacion es de una sola vez.

## Activar el instalador

Para forzar el flujo completo (por ejemplo, para probarlo o en un
despliegue nuevo sin seed): `installer_enforced=true` en `.env` del backend,
y no ejecutar `seed_demo.py` antes del primer arranque.

## Limites conocidos

- No hay wizard para agregar organizaciones adicionales a un sistema ya
  instalado (usar `POST /api/v1/organizations/` directamente).
- El estado "instalado" es global al backend, no por organizacion.
