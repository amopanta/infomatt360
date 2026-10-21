#!/usr/bin/env bash
# InfoMatt360 - instalación nueva en un servidor Linux con Docker (docs/147).
#
# Igual que Moodle: este script deja el servidor listo y el resto se completa
# en el navegador con el asistente /install (organización, administrador,
# proyecto, correo, almacenamiento y copias de seguridad).
#
# Uso (desde la carpeta del repositorio):
#   ./scripts/infomatt360-install.sh --domain app.midominio.org
#   ./scripts/infomatt360-install.sh --domain app.midominio.org --yes   # sin preguntas
set -euo pipefail

COMPOSE_FILE="docker-compose.production.example.yml"
ENV_FILE=".env.production"
DOMAIN=""
ASSUME_YES="no"
APP_SERVICES="postgres redis pgbouncer backend-1 backend-2 backend-lb worker-bulk worker-scheduler frontend"

while [ $# -gt 0 ]; do
  case "$1" in
    --domain) DOMAIN="${2:-}"; shift 2 ;;
    --yes|-y) ASSUME_YES="yes"; shift ;;
    -h|--help) sed -n '2,12p' "$0"; exit 0 ;;
    *) echo "Opción desconocida: $1" >&2; exit 2 ;;
  esac
done

say() { printf '\n==> %s\n' "$*"; }
fail() { printf '\nERROR: %s\n' "$*" >&2; exit 1; }
compose() { docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

[ -f "$COMPOSE_FILE" ] || fail "Ejecuta el script desde la carpeta del repositorio (no encuentro $COMPOSE_FILE)."

say "1/6 Requisitos del servidor"
command -v docker >/dev/null 2>&1 || fail "Falta Docker. Instálalo: https://docs.docker.com/engine/install/"
docker compose version >/dev/null 2>&1 || fail "Falta el plugin 'docker compose' (v2)."
command -v openssl >/dev/null 2>&1 || fail "Falta openssl (para generar claves)."
command -v curl >/dev/null 2>&1 || fail "Falta curl."
free_gb=$(df -Pk . | awk 'NR==2 {printf "%d", $4/1024/1024}')
[ "${free_gb:-0}" -ge 5 ] || fail "Hay menos de 5 GB libres en disco (${free_gb} GB)."
echo "Docker, compose, openssl y curl presentes; ${free_gb} GB libres."

say "2/6 Configuración (.env.production)"
if [ -f "$ENV_FILE" ]; then
  echo "Ya existe $ENV_FILE: se conserva tal cual (no se sobrescriben claves)."
else
  if [ -z "$DOMAIN" ] && [ "$ASSUME_YES" = "no" ]; then
    read -r -p "Dominio público (ej. app.midominio.org): " DOMAIN
  fi
  [ -n "$DOMAIN" ] || fail "Indica el dominio con --domain."
  cp .env.production.example "$ENV_FILE"
  secret() { openssl rand -hex 32; }
  sed -i \
    -e "s|^SECRET_KEY=.*|SECRET_KEY=$(secret)|" \
    -e "s|^GF_SECURITY_ADMIN_PASSWORD=.*|GF_SECURITY_ADMIN_PASSWORD=$(secret)|" \
    -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(secret)|" \
    -e "s|^FRONTEND_URL=.*|FRONTEND_URL=https://${DOMAIN}|" \
    -e "s|^CORS_ALLOWED_ORIGINS=.*|CORS_ALLOWED_ORIGINS=https://${DOMAIN}|" \
    -e "s|^INSTALLER_ENFORCED=.*|INSTALLER_ENFORCED=true|" \
    "$ENV_FILE"
  chmod 600 "$ENV_FILE"
  echo "Creado $ENV_FILE con claves aleatorias (permisos 600). Revisa SMTP_* si vas a enviar correo."
fi
grep -q '^POSTGRES_PASSWORD=.\+' "$ENV_FILE" || fail "Falta POSTGRES_PASSWORD en $ENV_FILE."
if grep -q 'REPLACE_WITH\|CHANGE_ME' "$ENV_FILE"; then
  echo "Aviso: quedan valores de ejemplo en $ENV_FILE (por ejemplo SMTP). Se pueden completar después."
fi

say "3/6 Construcción de imágenes (puede tardar 10-20 minutos la primera vez)"
compose build backend-1 backend-2 worker-bulk worker-scheduler frontend migrate

say "4/6 Base de datos"
compose up -d postgres redis pgbouncer
compose run --rm migrate

say "5/6 Arranque de la aplicación"
compose up -d $APP_SERVICES
for attempt in $(seq 1 30); do
  if curl -fsS http://127.0.0.1:18000/api/v1/health/ready >/dev/null 2>&1 && curl -fsS http://127.0.0.1:18080/ >/dev/null 2>&1; then
    break
  fi
  [ "$attempt" -eq 30 ] && { compose ps; fail "La aplicación no respondió a tiempo. Revisa: docker compose -f $COMPOSE_FILE logs backend-1"; }
  sleep 5
done
echo "Servidor de la aplicación y web respondiendo."

say "6/6 Listo"
domain_line=$(grep '^FRONTEND_URL=' "$ENV_FILE" | cut -d= -f2-)
cat <<EOF
La web escucha en 127.0.0.1:18080. Publícala con HTTPS en ${domain_line}
(por ejemplo con Caddy: "${domain_line#https://} { reverse_proxy 127.0.0.1:18080 }").

Termina la instalación en el navegador, como en Moodle:
  ${domain_line}/install
El asistente verifica requisitos y versión de la base, y crea la organización,
el administrador, el primer proyecto, el correo, el almacenamiento y las copias.

Monitoreo (Prometheus/Grafana) es opcional: ver docs/61, paso 7.
EOF
