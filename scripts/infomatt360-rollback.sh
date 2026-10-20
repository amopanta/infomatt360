#!/usr/bin/env bash
# InfoMatt360 - volver a la versión anterior con una copia de infomatt360-upgrade.sh (docs/147).
#
# Restaura el código anterior, la base de datos y los archivos subidos tal como
# estaban antes de la actualización. Lo capturado después de la copia se pierde
# en el servidor (las tablets lo conservan en su cola y lo reenvían).
#
# Uso:
#   ./scripts/infomatt360-rollback.sh backups/upgrade-20261020-020000
set -euo pipefail

COMPOSE_FILE="docker-compose.production.example.yml"
ENV_FILE=".env.production"
APP_SERVICES="backend-1 backend-2 backend-lb worker-bulk worker-scheduler frontend"
BACKUP_DIR="${1:-}"

fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
say() { printf '\n==> %s\n' "$*"; }
compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

[ -n "$BACKUP_DIR" ] && [ -f "$BACKUP_DIR/infomatt360.dump" ] && [ -f "$BACKUP_DIR/previous_commit" ] \
  || fail "Indica la carpeta de la copia (ej. backups/upgrade-20261020-020000)."
PREVIOUS_COMMIT=$(cat "$BACKUP_DIR/previous_commit")
read -r -p "Se restaurará la base y los archivos de $BACKUP_DIR y el código $PREVIOUS_COMMIT. Escribe RESTAURAR para continuar: " answer
[ "$answer" = "RESTAURAR" ] || fail "Cancelado."

say "1/4 Código anterior"
git checkout "$PREVIOUS_COMMIT"
compose build backend-1 backend-2 worker-bulk worker-scheduler frontend

say "2/4 Base de datos"
compose stop $APP_SERVICES pgbouncer
compose exec -T postgres pg_restore -U infomatt360 -d infomatt360 --clean --if-exists --no-owner < "$BACKUP_DIR/infomatt360.dump"

say "3/4 Archivos subidos"
if [ -s "$BACKUP_DIR/uploads.tgz" ]; then
  compose run --rm --no-deps -T backend-1 sh -c 'rm -rf /var/lib/infomatt360/uploads/* && tar xzf - -C /var/lib/infomatt360' < "$BACKUP_DIR/uploads.tgz"
fi

say "4/4 Arranque"
compose up -d pgbouncer $APP_SERVICES
echo "Versión anterior restaurada ($PREVIOUS_COMMIT). Verifica en el navegador."
