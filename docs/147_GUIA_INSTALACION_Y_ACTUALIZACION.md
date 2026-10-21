# 147. Guía de instalación y actualización

Fecha: 2026-10-19. Aplica a la versión con las migraciones hasta
`0086_db_sync`.

InfoMatt360 se instala como Moodle, en dos partes:

1. **En el servidor**, un solo script deja todo listo: requisitos, claves,
   imágenes, base de datos y arranque.
2. **En el navegador**, el asistente **/install** termina la configuración:
   organización, administrador, primer proyecto, correo, almacenamiento y
   copias de seguridad.

Para actualizar una instalación existente hay otro script, con copia de
seguridad previa y reversión.

> A diferencia de Moodle, la conexión a la base y las migraciones no se hacen
> desde el navegador: un proceso Python no puede cambiar su base en caliente
> (docs/73). El asistente **verifica** que la base esté en la versión del
> código y, si no, muestra el comando exacto que hay que ejecutar.

## 1. Requisitos del servidor

- Linux con **Docker** y el plugin **docker compose v2**, más `git`,
  `curl` y `openssl`.
- 4 GB de RAM como mínimo (recomendado 8 GB) y 20 GB libres de disco (el
  script exige al menos 5).
- Un dominio apuntando al servidor y un proxy con HTTPS, por ejemplo Caddy o
  nginx con certbot. La aplicación escucha en `127.0.0.1:18080`.

## 2. Instalación nueva (asistente tipo Moodle)

```bash
git clone https://github.com/amopanta/infomatt360.git
cd infomatt360
./scripts/infomatt360-install.sh --domain app.midominio.org
```

El script hace seis pasos:
1. Verifica Docker, compose, openssl, curl y el espacio en disco.
2. Crea `.env.production` (permisos 600) con claves aleatorias: `SECRET_KEY`,
   `POSTGRES_PASSWORD` y Grafana, además del dominio, CORS e
   `INSTALLER_ENFORCED=true`. Si el archivo ya existe, no lo toca.
3. Construye las imágenes; la primera vez tarda de 10 a 20 minutos.
4. Levanta Postgres, Redis y PgBouncer y **aplica las migraciones**.
5. Arranca los backends, los workers y la web, y espera a que respondan.
6. Indica el siguiente paso.

Luego, en el proxy HTTPS (ejemplo con Caddy):

```
app.midominio.org {
    reverse_proxy 127.0.0.1:18080
}
```

Y en el navegador: **https://app.midominio.org/install**. El asistente tiene 7
pasos:

1. **Requisitos:**
   - conexión a la base;
   - carpeta de archivos con escritura;
   - clave secreta distinta de la de ejemplo;
   - motor recomendado;
   - **base de datos actualizada** (versión de migraciones igual a la del
     código).
2. **Organización:** nombre, identificador y URL pública.
3. **Administrador y primer proyecto.**
4. **Correo** (opcional).
5. **Almacenamiento** (opcional): límite de tamaño de archivos.
6. **Copias de seguridad** (opcional): diarias, semanales o cada hora.
7. **Confirmar.** Se crea todo de una vez y el asistente queda cerrado; no
   se puede volver a ejecutar.

Después de instalar, se puede poner `INSTALLER_ENFORCED=false` en
`.env.production`; no es obligatorio, porque el asistente ya no vuelve a
abrirse. Las siguientes cuentas se crean en *Configuración → Usuarios*,
una a una o por Excel (docs/145).

## 3. Actualización del servidor actual

Este es el caso de `infomatt360.tecnomatt.com`.

**Antes:**
1. Unir a `main` los PR del repositorio principal y de la app móvil.
2. Avisar a los gestores de una ventana de unos **10 a 15 minutos**. Las
   tablets y el escritorio siguen capturando sin conexión durante el corte y
   reenvían al volver el servicio.
3. Revisar que haya espacio en disco para la copia (`df -h`).

**Actualizar** (en el servidor, en la carpeta del repositorio):

```bash
./scripts/infomatt360-upgrade.sh
```

| Paso | Qué hace | ¿Corta el servicio? |
|---|---|---|
| 1 | Copia de la base (`pg_dump`), de los archivos subidos y de `.env.production` en `backups/upgrade-<fecha>/` | No |
| 2 | Descarga la versión (`main`, o la que indique `--ref`) | No |
| 3 | Construye las imágenes nuevas | No |
| 4 | Detiene la aplicación, **aplica las migraciones** (`run --rm migrate`) y la arranca | **Sí, de 5 a 10 minutos** |
| 5 | Verifica `/api/v1/health/ready` y la web, y muestra la versión de la base | No |

Si un paso falla, el script se detiene y muestra cómo volver atrás.

**Primera actualización desde la versión anterior:**
- Agregar `POSTGRES_PASSWORD` a `.env.production` si no está (con la
  contraseña actual de Postgres). Ahora es obligatoria.
- Se pueden borrar `MOBILE_JWT_SECRET` y las referencias a
  `mobile-infomatt360…`: ese servicio se retiró y la app oficial es la de
  Expo.
- Revisar que `PERMISSIONS_POLICY` diga
  `geolocation=(self), microphone=(self), camera=(self)`. Con `()`, el
  navegador bloquea el GPS, la cámara y el micrófono en la captura web y el
  escritorio.
- Se aplican las migraciones `0080` a `0086` en una sola corrida.

## 4. Prueba después de actualizar (15 a 25 minutos)

1. Iniciar sesión con un administrador y con un gestor.
2. *Llenar formularios*: capturar una respuesta con GPS y foto desde el
   navegador. Debe pedir permiso de ubicación y cámara.
3. *Registros*: devolver esa respuesta con una observación; el gestor la ve
   como «Devuelto».
4. *Revisión y reportes → Planeador mensual*: abre el tablero y descarga el
   Excel.
5. *Configuración → Usuarios*: ver la grilla y crear un usuario de prueba con
   cargo y municipio.
6. *Avanzado → Base espejo*: la pantalla carga (no hace falta ejecutar un
   plan).
7. Tablet: sincronizar y ver que los pendientes bajen a cero.
8. `/install` debe decir que el sistema ya está instalado.

## 5. Volver atrás

```bash
./scripts/infomatt360-rollback.sh backups/upgrade-<fecha>
```

El script pide escribir `RESTAURAR` y luego:
1. vuelve al código anterior;
2. restaura la base (`pg_restore`) y los archivos subidos;
3. arranca de nuevo.

Lo que se haya guardado en el servidor después de la copia se pierde ahí. Las
tablets conservan su cola y lo reenvían. Tarda de 10 a 15 minutos.

## 6. Operación

- Migraciones manuales:
  `docker compose -f docker-compose.production.example.yml --env-file .env.production run --rm migrate`.
  Este servicio va directo a Postgres, no por PgBouncer.
- Versión de la base: el mismo comando terminando en
  `migrate python -m alembic current`.
- Registros: `docker compose -f docker-compose.production.example.yml logs --tail 100 backend-1`.
- Monitoreo (Prometheus y Grafana) es opcional: ver docs/61, paso 7.

## 7. Qué cambió en el despliegue con este documento

- **`docker-compose.production.example.yml`:**
  - se quitaron los servicios `mobile` y `mobile-lb`, que apuntaban a la
    carpeta `mobile/` retirada y hacían fallar `up --build`;
  - se agregó el servicio `migrate`, en el perfil `tools`.
- **`deploy/nginx.mobile.conf`:** se eliminó.
- **`deploy/nginx.frontend.conf` y `PERMISSIONS_POLICY`:** GPS, cámara y
  micrófono permitidos para el propio sitio (antes bloqueados).
- **`.env.production.example`:**
  - se agregan `POSTGRES_PASSWORD` e `INSTALLER_ENFORCED`;
  - se quitan las variables del módulo móvil retirado.
- **Scripts de Linux:** `infomatt360-install.sh`, `infomatt360-upgrade.sh` e
  `infomatt360-rollback.sh`. `.gitattributes` obliga a que lleguen con fin
  de línea LF.
- **Asistente:** comprobación de la versión de la base.

## 8. Límites

- Los scripts se validaron en sintaxis (`bash -n`), pero **no se han
  ejecutado en un servidor real**: este equipo no tiene Docker. La primera
  ejecución en el servidor debe hacerse con alguien observando, en la
  ventana acordada.
- El proxy HTTPS y el dominio se configuran fuera de InfoMatt360.
- La app móvil instalable (EAS) y el instalador del escritorio se publican
  aparte; no forman parte de esta actualización del servidor.
