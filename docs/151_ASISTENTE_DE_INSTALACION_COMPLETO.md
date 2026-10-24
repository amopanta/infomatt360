# 151. Asistente de instalación completo (2026-10-24)

Pedido del responsable: que la instalación se haga desde el asistente web,
como en Moodle, incluyendo el usuario administrador, las credenciales de la
base de datos y el correo, sin editar archivos ni correr comandos en el
servidor.

## 1. Pasos del asistente (`/install`)

| # | Paso | Qué pide |
|---|---|---|
| 1 | Código | El código de instalación (ver §2). Sin él no se puede cambiar nada. |
| 2 | Requisitos | Nada: muestra conexión a la base, carpeta de archivos, clave secreta y versión de la base. |
| 3 | Base de datos | **Incluida** (recomendado, no pide nada) o **externa** PostgreSQL: servidor, puerto, nombre, usuario, contraseña y SSL. Botón «Probar conexión». |
| 4 | Organización | Nombre, identificador, dirección pública y primer proyecto. |
| 5 | Administrador | Nombre, documento, correo y contraseña (dos veces; al menos 10 caracteres con letras y números). |
| 6 | Correo | Servidor SMTP, puerto, STARTTLS, usuario, contraseña y remitente. Botón «Enviar correo de prueba». |
| 7 | Almacenamiento | Perfil local y tamaño máximo por archivo. |
| 8 | Copias de seguridad | Frecuencia, opcional. |
| 9 | Confirmar | Resumen. Revisa todos los pasos antes de instalar. |

Si la página se recarga a mitad de camino, se conservan el código y el paso.
Lo escrito se vuelve a pedir desde «Organización». Las contraseñas nunca se
guardan en el navegador.

## 2. Código de instalación y de recuperación

Como en Grafana o Jupyter: evita que otra persona abra `/install` antes que
el responsable y se quede con el sistema.

- **Instalación** (sistema sin instalar):
  - el servidor lo crea al arrancar y lo deja en su registro;
  - el script `infomatt360-install.sh` lo muestra al terminar;
  - no vence.
- **Recuperación** (sistema instalado): sirve para crear un administrador o
  ponerle contraseña nueva a uno existente desde la misma página `/install`
  («Recuperar acceso de administrador»). Vence a los 30 minutos y sirve una
  sola vez.
- **Ambos** se obtienen en el servidor con:

  ```bash
  docker compose -f docker-compose.production.example.yml --env-file .env.production exec backend-1 python -m app.cli.install_code
  ```

  (en un sistema instalado ese comando da uno de recuperación).
- Solo se guarda el hash, con permisos 600. Se admiten 10 intentos por IP cada
  15 minutos.
- La recuperación siempre pide código, aunque el asistente esté desactivado
  (`INSTALLER_ENFORCED=false`).

## 3. Cómo se guardan la base externa y el correo

- **Dónde:** el asistente escribe `runtime.json` en el volumen
  `config_data`, montado en `/app/config` en los dos servidores, los dos
  procesos de fondo y `migrate`. Permisos 600.
- **Qué guarda:** solo `database_url` y `smtp_*`; cualquier otra clave se
  ignora.
- **Prioridad:** al arrancar, esos valores mandan sobre `.env.production`.
- **Base externa:**
  1. se prueba la conexión;
  2. se rechaza si tiene tablas que no son de InfoMatt360;
  3. se crean o actualizan las tablas con Alembic;
  4. se guarda la dirección.
- **Reinicio:** todos los procesos vigilan el archivo
  (`RUNTIME_CONFIG_WATCH=true`). Cuando cambia, terminan y Docker los vuelve a
  levantar ya con la base nueva. El asistente espera hasta que el servidor
  responde.
- **Correo:** se guarda junto con la instalación, al final, para no
  reiniciar los servicios a mitad del asistente.
- **Motor:** la base principal solo admite PostgreSQL. MySQL y SQL Server
  siguen disponibles como destino de copias (Bases de datos externas,
  docs/146).

## 4. Sistemas instalados antes del asistente

Una base que ya tiene usuarios cuenta como instalada aunque no tenga la
marca de instalación. Así se puede activar el asistente en una instalación
anterior, como la de producción, sin bloquearla ni permitir instalar
encima.

## 5. Archivos

- **Servidor:**
  - `app/core/runtime_config.py`
  - `app/services/install_code_service.py`
  - `app/services/install_setup_service.py`
  - `app/api/v1/install.py`
  - `app/cli/install_code.py`
  - `app/cli/create_admin.py` (sigue disponible por consola)
- **Web:** `modules/install/InstallWizardApp.tsx` y `api.ts`.
- **Despliegue:**
  - `docker-compose.production.example.yml`: volumen `config_data` y
    variables `RUNTIME_CONFIG_*`;
  - `scripts/infomatt360-install.sh`: muestra el código.
- **Pruebas:**
  - `tests/test_install_wizard_setup.py`;
  - `tests/test_installation.py`;
  - `tests/test_create_admin_cli.py`.
- **Verificación:** se recorrió el asistente completo en local, contra una
  base vacía (capturas en la conversación de despliegue). El administrador
  creado inicia sesión, y la recuperación web crea otro administrador que
  también inicia sesión.
