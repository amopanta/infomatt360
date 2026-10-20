#!/usr/bin/env bash
# InfoMatt360 - actualización de un servidor en producción (docs/147).
#
# Hace, en orden: copia de seguridad (base y archivos) -> descarga la versión
# -> construye las imágenes con el servicio aún en línea -> corte breve:
# migraciones y reinicio -> verificación. Si algo falla, indica cómo volver
# atrás con infomatt360-rollback.sh y la copia recién tomada.
#
# Uso (desde la carpeta del repositorio):
#   ./scripts/infomatt360-upgrade.sh                # actualiza a origin/main
#   ./scripts/infomatt360-upgrade.sh --ref v2026.10 # a una etiqueta o rama
set -euo pipefail

COMPOSE_FILE="docker-compose.production.example.yml"
ENV_FILE=".env.production"
REF="main"
APP_SERVICES="backend-1 backend-2 backend-lb worker-bulk worker-scheduler frontend"

while [ $# -gt 0 ]; do
  case "$1" in
    --ref) REF="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

[ -f "$COMPOSE_FILE" ] && [ -f "$ENV_FILE" ] || fail "Ejecuta el script en la carpeta del repositorio, con $ENV_FILE presente."
[ -z "$(git status --porcelain --untracked-files=no)" ] || fail "Hay cambios locales sin guardar en el servidor (git status). Resuélvelos antes de actualizar."

STAMP=$(date +%Y%m%d-%H%M%S)
BACKUP_DIR="backups/upgrade-$STAMP"
PREVIOUS_COMMIT=$(git rev-parse HEAD)
mkdir -p "$BACKUP_DIR"
echo "$PREVIOUS_COMMIT" > "$BACKUP_DIR/previous_commit"

say "1/6 Copia de seguridad en $BACKUP_DIR"
compose exec -T postgres pg_dump -U infomatt360 -d infomatt360 --format=custom > "$BACKUP_DIR/infomatt360.dump"
[ -s "$BACKUP_DIR/infomatt360.dump" ] || fail "La copia de la base quedó vacía; no se continúa."
compose exec -T backend-1 tar czf - -C /var/lib/infomatt360 uploads > "$BACKUP_DIR/uploads.tgz" || echo "Aviso: no se pudieron copiar los archivos subidos."
cp "$ENV_FILE" "$BACKUP_DIR/env.production" && chmod 600 "$BACKUP_DIR/env.production"
ls -lh "$BACKUP_DIR"

say "2/6 Descarga de la versión ($REF)"
git fetch --tags origin
git checkout "$REF"
git pull --ff-only origin "$REF" 2>/dev/null || true
NEW_COMMIT=$(git rev-parse HEAD)
echo "De $PREVIOUS_COMMIT a $NEW_COMMIT"
[ "$PREVIOUS_COMMIT" != "$NEW_COMMIT" ] || echo "Aviso: ya estaba en esta versión; se reconstruye igual."

say "3/6 Construcción de imágenes (el servicio sigue en línea)"
compose build backend-1 backend-2 worker-bulk worker-scheduler frontend migrate

rollback_hint() {
  printf '\nPara volver a la versión anterior:\n  ./scripts/infomatt360-rollback.sh %s\n' "$BACKUP_DIR" >&2
}
trap 'rollback_hint' ERR

say "4/6 Corte breve: migraciones y reinicio"
compose stop $APP_SERVICES
compose run --rm migrate
compose up -d --remove-orphans $APP_SERVICES

say "5/6 Verificación"
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18000/api/v1/health/ready >/dev/null 2>&1 && curl -fsS http://127.0.0.1:18080/ >/dev/null 2>&1; then
    break
  fi
  if [ "$attempt" -eq 30 ]; then
    compose ps
    fail "La nueva versión no respondió a tiempo. Revisa: docker compose -f $COMPOSE_FILE logs --tail 100 backend-1"
  fi
  sleep 5
done
compose run --rm --no-deps migrate python -m alembic current

say "6/6 Listo: versión $NEW_COMMIT en línea"
trap - ERR
cat <<EOF
Copia de seguridad previa: $BACKUP_DIR (guárdala unos días).
Prueba rápida sugerida (docs/147, sección 4): iniciar sesión, capturar, devolver
un registro, abrir el planeador, la grilla de usuarios y la base espejo.
EOF
