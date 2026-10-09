#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# InfoMatt360 Mobile — Asistente de Instalación
# Instalador interactivo tipo Moodle para cualquier VPS/servidor
# InfoMatt Colombia SAS — 2026
# ══════════════════════════════════════════════════════════════════
set -e

# ── Colores ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# ── Variables globales ──
APP_DIR=""
DOMAIN=""
SUBDOMAIN=""
FULL_DOMAIN=""
PORT="3001"
ADMIN_NAME=""
ADMIN_EMAIL=""
ADMIN_PASS=""
USER2_NAME=""
USER2_EMAIL=""
USER2_PASS=""
USER2_ROL=""
USER3_NAME=""
USER3_EMAIL=""
USER3_PASS=""
USER3_ROL=""
ORG_NAME=""
ORG_NIT=""
NODE_VERSION=""
SSL_EMAIL=""
INSTALL_DIR="/opt/infomatt360-mobile"

# ── Funciones de UI ──
banner() {
  clear
  echo -e "${CYAN}"
  echo "  ╔══════════════════════════════════════════════════════════╗"
  echo "  ║                                                        ║"
  echo "  ║     ██╗███╗   ██╗███████╗ ██████╗ ███╗   ███╗         ║"
  echo "  ║     ██║████╗  ██║██╔════╝██╔═══██╗████╗ ████║         ║"
  echo "  ║     ██║██╔██╗ ██║█████╗  ██║   ██║██╔████╔██║         ║"
  echo "  ║     ██║██║╚██╗██║██╔══╝  ██║   ██║██║╚██╔╝██║         ║"
  echo "  ║     ██║██║ ╚████║██║     ╚██████╔╝██║ ╚═╝ ██║         ║"
  echo "  ║     ╚═╝╚═╝  ╚═══╝╚═╝      ╚═════╝ ╚═╝     ╚═╝         ║"
  echo "  ║                                                        ║"
  echo "  ║           InfoMatt360 Mobile v1.0.0                    ║"
  echo "  ║     Asistente de Instalación — InfoMatt Colombia       ║"
  echo "  ║                                                        ║"
  echo "  ╚══════════════════════════════════════════════════════════╝"
  echo -e "${NC}"
}

step_header() {
  local step=$1
  local total=$2
  local title=$3
  echo ""
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "${WHITE}${BOLD}  Paso ${step} de ${total}: ${title}${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

info() { echo -e "  ${CYAN}ℹ${NC}  $1"; }
ok() { echo -e "  ${GREEN}✅${NC} $1"; }
warn() { echo -e "  ${YELLOW}⚠️${NC}  $1"; }
fail() { echo -e "  ${RED}❌${NC} $1"; }

ask() {
  local prompt=$1
  local default=$2
  local var_name=$3
  if [ -n "$default" ]; then
    echo -ne "  ${WHITE}${prompt}${NC} ${CYAN}[${default}]${NC}: "
    read -r input
    eval "$var_name=\"${input:-$default}\""
  else
    echo -ne "  ${WHITE}${prompt}${NC}: "
    read -r input
    eval "$var_name=\"$input\""
  fi
}

ask_password() {
  local prompt=$1
  local var_name=$2
  while true; do
    echo -ne "  ${WHITE}${prompt}${NC}: "
    read -rs pass1
    echo ""
    if [ ${#pass1} -lt 8 ]; then
      warn "La contraseña debe tener al menos 8 caracteres"
      continue
    fi
    echo -ne "  ${WHITE}Confirmar contraseña${NC}: "
    read -rs pass2
    echo ""
    if [ "$pass1" != "$pass2" ]; then
      warn "Las contraseñas no coinciden. Intenta de nuevo."
      continue
    fi
    eval "$var_name=\"$pass1\""
    break
  done
}

ask_yes_no() {
  local prompt=$1
  local default=$2
  local var_name=$3
  local hint="[S/n]"
  [ "$default" = "n" ] && hint="[s/N]"
  echo -ne "  ${WHITE}${prompt}${NC} ${CYAN}${hint}${NC}: "
  read -r answer
  answer=${answer:-$default}
  case "$answer" in
    [sS][iI]|[sS]|[yY]|[yY][eE][sS]) eval "$var_name=true" ;;
    *) eval "$var_name=false" ;;
  esac
}

select_option() {
  local prompt=$1
  shift
  local options=("$@")
  echo -e "  ${WHITE}${prompt}${NC}"
  for i in "${!options[@]}"; do
    echo -e "    ${CYAN}$((i+1))${NC}) ${options[$i]}"
  done
  echo -ne "  ${WHITE}Selecciona una opción${NC}: "
  read -r choice
  return $((choice - 1))
}

progress() {
  local msg=$1
  echo -ne "  ${YELLOW}⏳${NC} ${msg}..."
}

progress_done() {
  echo -e " ${GREEN}✅${NC}"
}

# ══════════════════════════════════════════════════════════════════
# PASO 0: Verificación de requisitos
# ══════════════════════════════════════════════════════════════════
check_requirements() {
  step_header "0" "7" "Verificación de Requisitos"

  local errors=0

  # Root check
  if [ "$EUID" -ne 0 ]; then
    fail "Este instalador debe ejecutarse como root (sudo)"
    exit 1
  fi
  ok "Ejecutando como root"

  # OS
  if [ -f /etc/os-release ]; then
    . /etc/os-release
    info "Sistema operativo: ${PRETTY_NAME}"
  fi

  # Node.js
  if command -v node &> /dev/null; then
    NODE_VERSION=$(node -v)
    local major=$(echo "$NODE_VERSION" | sed 's/v//' | cut -d'.' -f1)
    if [ "$major" -ge 18 ]; then
      ok "Node.js ${NODE_VERSION} instalado"
    else
      warn "Node.js ${NODE_VERSION} detectado — se requiere v18+"
      ask_yes_no "¿Instalar Node.js 20 LTS?" "s" INSTALL_NODE
      if [ "$INSTALL_NODE" = "true" ]; then
        install_node
      else
        fail "Node.js 18+ es requerido"
        exit 1
      fi
    fi
  else
    warn "Node.js no está instalado"
    ask_yes_no "¿Instalar Node.js 20 LTS automáticamente?" "s" INSTALL_NODE
    if [ "$INSTALL_NODE" = "true" ]; then
      install_node
    else
      fail "Node.js 18+ es requerido para continuar"
      exit 1
    fi
  fi

  # Nginx
  if command -v nginx &> /dev/null; then
    ok "Nginx instalado"
  else
    warn "Nginx no está instalado"
    ask_yes_no "¿Instalar Nginx automáticamente?" "s" INSTALL_NGINX
    if [ "$INSTALL_NGINX" = "true" ]; then
      progress "Instalando Nginx"
      apt-get update -qq && apt-get install -y -qq nginx > /dev/null 2>&1
      systemctl enable nginx > /dev/null 2>&1
      systemctl start nginx > /dev/null 2>&1
      progress_done
    fi
  fi

  # Certbot
  if command -v certbot &> /dev/null; then
    ok "Certbot instalado (para SSL)"
  else
    warn "Certbot no está instalado — se instalará para certificados SSL"
  fi

  # Git
  if command -v git &> /dev/null; then
    ok "Git instalado"
  else
    progress "Instalando Git"
    apt-get install -y -qq git > /dev/null 2>&1
    progress_done
  fi

  # Disk space
  local free_space=$(df -BM / | tail -1 | awk '{print $4}' | tr -d 'M')
  if [ "$free_space" -gt 500 ]; then
    ok "Espacio en disco: ${free_space}MB disponible"
  else
    warn "Espacio en disco bajo: ${free_space}MB — se recomiendan 500MB+"
  fi

  # RAM
  local total_ram=$(free -m | awk '/^Mem:/{print $2}')
  info "RAM total: ${total_ram}MB"

  echo ""
  echo -e "  ${GREEN}${BOLD}Requisitos verificados correctamente${NC}"
  echo ""
  echo -ne "  Presiona ${CYAN}Enter${NC} para continuar..."
  read -r
}

install_node() {
  progress "Instalando Node.js 20 LTS"
  if command -v curl &> /dev/null; then
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
  else
    apt-get install -y -qq curl > /dev/null 2>&1
    curl -fsSL https://deb.nodesource.com/setup_20.x | bash - > /dev/null 2>&1
  fi
  apt-get install -y -qq nodejs > /dev/null 2>&1
  NODE_VERSION=$(node -v)
  progress_done
  ok "Node.js ${NODE_VERSION} instalado"
}

# ══════════════════════════════════════════════════════════════════
# PASO 1: Configuración del Dominio
# ══════════════════════════════════════════════════════════════════
configure_domain() {
  step_header "1" "7" "Configuración del Dominio"

  info "InfoMatt360 Mobile necesita un dominio para funcionar con HTTPS."
  info "HTTPS es requerido para la instalación como app en teléfonos."
  echo ""

  echo -e "  ${WHITE}Ejemplo:${NC}"
  echo -e "    Si tu dominio es ${CYAN}miempresa.com${NC}"
  echo -e "    La app quedará en ${CYAN}mobile.miempresa.com${NC}"
  echo ""
  echo -e "    Otro ejemplo: dominio ${CYAN}infomatt360.tecnomatt.com${NC}"
  echo -e "    La app quedará en ${CYAN}mobile.infomatt360.tecnomatt.com${NC}"
  echo ""

  ask "Dominio principal (ej: miempresa.com)" "" DOMAIN
  while [ -z "$DOMAIN" ]; do
    warn "El dominio es obligatorio"
    ask "Dominio principal" "" DOMAIN
  done

  ask "Subdominio para la app móvil" "mobile" SUBDOMAIN

  FULL_DOMAIN="${SUBDOMAIN}.${DOMAIN}"

  echo ""
  ok "La aplicación estará disponible en: ${CYAN}https://${FULL_DOMAIN}${NC}"
  echo ""

  # Verificar DNS
  info "Verificando DNS..."
  local server_ip=$(curl -s ifconfig.me 2>/dev/null || curl -s icanhazip.com 2>/dev/null || echo "desconocida")
  info "IP de este servidor: ${CYAN}${server_ip}${NC}"

  local dns_ip=$(dig +short "${FULL_DOMAIN}" 2>/dev/null || echo "")
  if [ "$dns_ip" = "$server_ip" ]; then
    ok "DNS configurado correctamente — ${FULL_DOMAIN} → ${server_ip}"
  elif [ -n "$dns_ip" ]; then
    warn "DNS apunta a ${dns_ip}, pero este servidor es ${server_ip}"
    info "Asegúrate de que el registro A apunte a ${server_ip}"
  else
    warn "No se encontró registro DNS para ${FULL_DOMAIN}"
    echo ""
    echo -e "  ${YELLOW}${BOLD}Acción requerida:${NC}"
    echo -e "  Ve al panel DNS de tu proveedor y crea un registro:"
    echo -e "    ${CYAN}Tipo:${NC}   A"
    echo -e "    ${CYAN}Nombre:${NC} ${SUBDOMAIN}"
    echo -e "    ${CYAN}Valor:${NC}  ${server_ip}"
    echo ""
    info "Puedes continuar la instalación y configurar el DNS después."
  fi

  ask "Puerto interno de la API" "3001" PORT

  echo ""
  echo -ne "  Presiona ${CYAN}Enter${NC} para continuar..."
  read -r
}

# ══════════════════════════════════════════════════════════════════
# PASO 2: Configuración de la Organización
# ══════════════════════════════════════════════════════════════════
configure_organization() {
  step_header "2" "7" "Datos de la Organización"

  info "Estos datos identifican tu organización dentro de InfoMatt360"
  echo ""

  ask "Nombre de la organización" "Mi Empresa SAS" ORG_NAME
  ask "NIT (opcional)" "" ORG_NIT
  ask "Dirección (opcional)" "" ORG_ADDR
  ask "Teléfono (opcional)" "" ORG_PHONE
  ask "Email de la organización" "" ORG_EMAIL

  echo ""
  ok "Organización: ${ORG_NAME}"
  echo ""
  echo -ne "  Presiona ${CYAN}Enter${NC} para continuar..."
  read -r
}

# ══════════════════════════════════════════════════════════════════
# PASO 3: Crear Usuario Administrador
# ══════════════════════════════════════════════════════════════════
configure_admin() {
  step_header "3" "7" "Usuario Administrador"

  info "El administrador tiene acceso total al sistema:"
  info "gestión de usuarios, estadísticas, exportación de datos."
  echo ""

  ask "Nombre completo del administrador" "" ADMIN_NAME
  while [ -z "$ADMIN_NAME" ]; do
    warn "El nombre es obligatorio"
    ask "Nombre completo del administrador" "" ADMIN_NAME
  done

  ask "Email del administrador" "" ADMIN_EMAIL
  while [ -z "$ADMIN_EMAIL" ]; do
    warn "El email es obligatorio"
    ask "Email del administrador" "" ADMIN_EMAIL
  done

  ask_password "Contraseña del administrador (mín. 8 caracteres)" ADMIN_PASS

  echo ""
  ok "Admin: ${ADMIN_NAME} (${ADMIN_EMAIL})"

  # Usuarios adicionales
  echo ""
  ask_yes_no "¿Deseas crear usuarios adicionales ahora?" "s" CREATE_EXTRA_USERS

  if [ "$CREATE_EXTRA_USERS" = "true" ]; then
    echo ""
    echo -e "  ${WHITE}${BOLD}Usuario 2:${NC}"
    ask "Nombre completo" "" USER2_NAME
    ask "Email" "" USER2_EMAIL
    ask_password "Contraseña" USER2_PASS
    echo -e "  ${WHITE}Rol:${NC}"
    echo -e "    ${CYAN}1${NC}) Supervisor — ve estadísticas y gestiona encuestadores"
    echo -e "    ${CYAN}2${NC}) Encuestador — recolecta datos en campo"
    echo -ne "  ${WHITE}Selecciona${NC}: "
    read -r role_choice
    [ "$role_choice" = "1" ] && USER2_ROL="supervisor" || USER2_ROL="encuestador"
    ok "Usuario 2: ${USER2_NAME} (${USER2_ROL})"

    ask_yes_no "¿Crear un tercer usuario?" "n" CREATE_USER3
    if [ "$CREATE_USER3" = "true" ]; then
      echo ""
      echo -e "  ${WHITE}${BOLD}Usuario 3:${NC}"
      ask "Nombre completo" "" USER3_NAME
      ask "Email" "" USER3_EMAIL
      ask_password "Contraseña" USER3_PASS
      echo -e "  ${WHITE}Rol:${NC}"
      echo -e "    ${CYAN}1${NC}) Supervisor"
      echo -e "    ${CYAN}2${NC}) Encuestador"
      echo -ne "  ${WHITE}Selecciona${NC}: "
      read -r role_choice
      [ "$role_choice" = "1" ] && USER3_ROL="supervisor" || USER3_ROL="encuestador"
      ok "Usuario 3: ${USER3_NAME} (${USER3_ROL})"
    fi
  fi

  echo ""
  echo -ne "  Presiona ${CYAN}Enter${NC} para continuar..."
  read -r
}

# ══════════════════════════════════════════════════════════════════
# PASO 4: Cargar datos de ejemplo
# ══════════════════════════════════════════════════════════════════
configure_sample_data() {
  step_header "4" "7" "Datos de Ejemplo"

  info "InfoMatt360 puede cargar datos de ejemplo para que pruebes"
  info "el sistema inmediatamente: participantes, formularios y registros."
  echo ""

  ask_yes_no "¿Cargar datos de ejemplo? (recomendado para primera vez)" "s" LOAD_SAMPLE

  echo ""
  echo -ne "  Presiona ${CYAN}Enter${NC} para continuar..."
  read -r
}

# ══════════════════════════════════════════════════════════════════
# PASO 5: Resumen antes de instalar
# ══════════════════════════════════════════════════════════════════
show_summary() {
  step_header "5" "7" "Resumen de la Instalación"

  echo -e "  ${WHITE}${BOLD}Revisa la configuración antes de instalar:${NC}"
  echo ""
  echo -e "  ${CYAN}Dominio:${NC}        https://${FULL_DOMAIN}"
  echo -e "  ${CYAN}Puerto API:${NC}     ${PORT}"
  echo -e "  ${CYAN}Directorio:${NC}     ${INSTALL_DIR}"
  echo ""
  echo -e "  ${CYAN}Organización:${NC}   ${ORG_NAME}"
  [ -n "$ORG_NIT" ] && echo -e "  ${CYAN}NIT:${NC}            ${ORG_NIT}"
  echo ""
  echo -e "  ${CYAN}Administrador:${NC}  ${ADMIN_NAME} <${ADMIN_EMAIL}>"
  [ -n "$USER2_NAME" ] && echo -e "  ${CYAN}Usuario 2:${NC}      ${USER2_NAME} <${USER2_EMAIL}> (${USER2_ROL})"
  [ -n "$USER3_NAME" ] && echo -e "  ${CYAN}Usuario 3:${NC}      ${USER3_NAME} <${USER3_EMAIL}> (${USER3_ROL})"
  echo ""
  echo -e "  ${CYAN}Datos ejemplo:${NC}  $([ "$LOAD_SAMPLE" = "true" ] && echo "Sí" || echo "No")"
  echo ""
  echo -e "  ${CYAN}Base de datos:${NC}  SQLite (archivo local)"
  echo -e "  ${CYAN}Ubicación BD:${NC}   ${INSTALL_DIR}/data/infomatt360.db"
  echo ""

  ask_yes_no "¿Todo correcto? ¿Iniciar la instalación?" "s" CONFIRM
  if [ "$CONFIRM" != "true" ]; then
    echo ""
    warn "Instalación cancelada"
    exit 0
  fi
}

# ══════════════════════════════════════════════════════════════════
# PASO 6: Instalación
# ══════════════════════════════════════════════════════════════════
run_installation() {
  step_header "6" "7" "Instalando InfoMatt360"

  # 6.1 — Descargar código
  if [ -d "$INSTALL_DIR" ]; then
    info "Directorio existente encontrado, actualizando..."
    cd "$INSTALL_DIR"
    if [ -d .git ]; then
      git pull origin main 2>/dev/null || true
    fi
  else
    progress "Descargando InfoMatt360"
    git clone https://github.com/amopanta/infomatt360.git /tmp/infomatt360-clone 2>/dev/null
    mkdir -p "$INSTALL_DIR"
    cp -r /tmp/infomatt360-clone/mobile/* "$INSTALL_DIR/"
    cp -r /tmp/infomatt360-clone/mobile/.* "$INSTALL_DIR/" 2>/dev/null || true
    rm -rf /tmp/infomatt360-clone
    progress_done
  fi

  cd "$INSTALL_DIR"

  # 6.2 — Crear .env
  progress "Configurando variables de entorno"
  JWT_SECRET=$(openssl rand -hex 32)
  JWT_REFRESH=$(openssl rand -hex 32)
  cat > .env << ENVEOF
# ─── InfoMatt360 Mobile — Generado por el instalador ───
# Fecha: $(date '+%Y-%m-%d %H:%M:%S')

PORT=${PORT}
NODE_ENV=production

# JWT Secrets (generados automáticamente — NO compartir)
JWT_SECRET=${JWT_SECRET}
JWT_REFRESH_SECRET=${JWT_REFRESH}
JWT_EXPIRES_IN=24h
JWT_REFRESH_EXPIRES_IN=7d

# Base de datos
DB_PATH=./data/infomatt360.db

# Uploads
UPLOAD_DIR=./uploads
MAX_FILE_SIZE=10485760

# Dominio
DOMAIN=${FULL_DOMAIN}
ENVEOF
  progress_done

  # 6.3 — Instalar dependencias
  progress "Instalando dependencias de Node.js"

  # Check Node version for better-sqlite3 compatibility
  local node_major=$(node -v | sed 's/v//' | cut -d'.' -f1)
  if [ "$node_major" -lt 22 ]; then
    npm install better-sqlite3@11.6.0 --save --loglevel=error 2>/dev/null
  fi
  npm install --omit=dev --loglevel=error 2>/dev/null
  progress_done

  # 6.4 — Crear directorios
  mkdir -p data uploads

  # 6.5 — Inicializar base de datos con los usuarios personalizados
  progress "Creando base de datos y usuarios"

  # Primero inicializar estructura de la BD
  node -e "require('./src/models/database').initDatabase()" 2>/dev/null

  # Crear script de setup personalizado
  cat > /tmp/infomatt360-setup.js << 'SETUPJS'
const { db } = require('./src/models/database');
const bcrypt = require('bcryptjs');
const { v4: uuid } = require('uuid');

const args = JSON.parse(process.argv[2]);
const salt = bcrypt.genSaltSync(10);

// Crear organización
const orgId = uuid();
db.prepare(`INSERT OR IGNORE INTO organizaciones (id, nombre, nit, direccion, telefono, email) VALUES (?,?,?,?,?,?)`).run(
  orgId, args.org_name, args.org_nit || null, args.org_addr || null, args.org_phone || null, args.org_email || null
);

// Crear admin
const adminId = uuid();
db.prepare(`INSERT OR IGNORE INTO usuarios (id, organizacion_id, nombre, email, password_hash, rol) VALUES (?,?,?,?,?,?)`).run(
  adminId, orgId, args.admin_name, args.admin_email, bcrypt.hashSync(args.admin_pass, salt), 'admin'
);

console.log('  Admin creado: ' + args.admin_email);

// Usuarios adicionales
if (args.user2_name) {
  db.prepare(`INSERT OR IGNORE INTO usuarios (id, organizacion_id, nombre, email, password_hash, rol) VALUES (?,?,?,?,?,?)`).run(
    uuid(), orgId, args.user2_name, args.user2_email, bcrypt.hashSync(args.user2_pass, salt), args.user2_rol
  );
  console.log('  Usuario 2 creado: ' + args.user2_email + ' (' + args.user2_rol + ')');
}

if (args.user3_name) {
  db.prepare(`INSERT OR IGNORE INTO usuarios (id, organizacion_id, nombre, email, password_hash, rol) VALUES (?,?,?,?,?,?)`).run(
    uuid(), orgId, args.user3_name, args.user3_email, bcrypt.hashSync(args.user3_pass, salt), args.user3_rol
  );
  console.log('  Usuario 3 creado: ' + args.user3_email + ' (' + args.user3_rol + ')');
}

// Crear proyecto por defecto
const projId = uuid();
db.prepare(`INSERT OR IGNORE INTO proyectos (id, organizacion_id, nombre, descripcion, fecha_inicio, estado) VALUES (?,?,?,?,?,?)`).run(
  projId, orgId, 'Proyecto Inicial', 'Proyecto creado durante la instalación', new Date().toISOString().split('T')[0], 'activo'
);

// Asignar todos los usuarios al proyecto
const users = db.prepare('SELECT id FROM usuarios WHERE organizacion_id = ?').all(orgId);
for (const u of users) {
  db.prepare('INSERT OR IGNORE INTO usuario_proyecto (usuario_id, proyecto_id) VALUES (?,?)').run(u.id, projId);
}

console.log('  Proyecto inicial creado');
console.log('  Base de datos: ' + require('path').resolve(process.env.DB_PATH || './data/infomatt360.db'));
SETUPJS

  # Escapar caracteres especiales en las contraseñas para JSON
  SETUP_ARGS=$(node -e "console.log(JSON.stringify({
    org_name: $(printf '%s' "$ORG_NAME" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    org_nit: $(printf '%s' "$ORG_NIT" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    org_addr: $(printf '%s' "$ORG_ADDR" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    org_phone: $(printf '%s' "$ORG_PHONE" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    org_email: $(printf '%s' "$ORG_EMAIL" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    admin_name: $(printf '%s' "$ADMIN_NAME" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    admin_email: $(printf '%s' "$ADMIN_EMAIL" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    admin_pass: $(printf '%s' "$ADMIN_PASS" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user2_name: $(printf '%s' "$USER2_NAME" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user2_email: $(printf '%s' "$USER2_EMAIL" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user2_pass: $(printf '%s' "$USER2_PASS" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user2_rol: $(printf '%s' "$USER2_ROL" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user3_name: $(printf '%s' "$USER3_NAME" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user3_email: $(printf '%s' "$USER3_EMAIL" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user3_pass: $(printf '%s' "$USER3_PASS" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))"),
    user3_rol: $(printf '%s' "$USER3_ROL" | node -e "process.stdout.write(JSON.stringify(require('fs').readFileSync('/dev/stdin','utf8')))")
  }))")

  cd "$INSTALL_DIR"
  node /tmp/infomatt360-setup.js "$SETUP_ARGS"
  rm -f /tmp/infomatt360-setup.js
  progress_done

  # 6.6 — Cargar datos de ejemplo
  if [ "$LOAD_SAMPLE" = "true" ]; then
    progress "Cargando datos de ejemplo"
    node src/utils/seed.js 2>/dev/null || echo "  (seed ya ejecutado previamente)"
    progress_done
  fi

  # 6.7 — Crear servicio systemd
  progress "Configurando servicio del sistema"
  cat > /etc/systemd/system/infomatt360-mobile.service << SVCEOF
[Unit]
Description=InfoMatt360 Mobile API
After=network.target

[Service]
Type=simple
WorkingDirectory=${INSTALL_DIR}
ExecStart=$(which node) src/server.js
Restart=on-failure
RestartSec=5
Environment=NODE_ENV=production
EnvironmentFile=${INSTALL_DIR}/.env

[Install]
WantedBy=multi-user.target
SVCEOF

  systemctl daemon-reload
  systemctl enable infomatt360-mobile > /dev/null 2>&1
  systemctl start infomatt360-mobile
  sleep 2
  progress_done

  # Verificar que arrancó
  if curl -s "http://localhost:${PORT}/api/health" | grep -q "ok"; then
    ok "API corriendo en puerto ${PORT}"
  else
    warn "La API aún está iniciando... esperando 5 segundos más"
    sleep 5
    if curl -s "http://localhost:${PORT}/api/health" | grep -q "ok"; then
      ok "API corriendo en puerto ${PORT}"
    else
      fail "La API no respondió. Revisa: journalctl -u infomatt360-mobile"
    fi
  fi

  # 6.8 — Configurar Nginx
  progress "Configurando servidor web (Nginx)"

  cat > "/etc/nginx/sites-available/infomatt360-mobile" << NGINXEOF
server {
    listen 80;
    server_name ${FULL_DOMAIN};

    # Seguridad
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        client_max_body_size 10M;
    }
}
NGINXEOF

  ln -sf /etc/nginx/sites-available/infomatt360-mobile /etc/nginx/sites-enabled/

  if nginx -t 2>/dev/null; then
    # Intentar reload, si falla intentar restart
    nginx -s reload 2>/dev/null || systemctl restart nginx 2>/dev/null || true
    progress_done
    ok "Nginx configurado para ${FULL_DOMAIN}"
  else
    progress_done
    warn "Error en la configuración de Nginx — revisa manualmente"
  fi

  # 6.9 — SSL con Certbot
  echo ""
  ask_yes_no "¿Generar certificado SSL ahora? (el DNS debe estar configurado)" "s" SETUP_SSL

  if [ "$SETUP_SSL" = "true" ]; then
    if ! command -v certbot &> /dev/null; then
      progress "Instalando Certbot"
      apt-get install -y -qq certbot python3-certbot-nginx > /dev/null 2>&1
      progress_done
    fi

    ask "Email para el certificado SSL" "${ADMIN_EMAIL}" SSL_EMAIL

    progress "Generando certificado SSL"
    if certbot --nginx -d "${FULL_DOMAIN}" --non-interactive --agree-tos --email "${SSL_EMAIL}" 2>/dev/null; then
      progress_done
      ok "Certificado SSL instalado correctamente"
    else
      progress_done
      warn "No se pudo generar el certificado SSL"
      info "Verifica que el DNS de ${FULL_DOMAIN} apunte a este servidor"
      info "Puedes intentar después con:"
      echo -e "    ${CYAN}certbot --nginx -d ${FULL_DOMAIN}${NC}"
    fi
  fi
}

# ══════════════════════════════════════════════════════════════════
# PASO 7: Resumen Final
# ══════════════════════════════════════════════════════════════════
show_final() {
  step_header "7" "7" "¡Instalación Completa!"

  local server_ip=$(curl -s ifconfig.me 2>/dev/null || echo "IP-del-servidor")

  echo -e "${GREEN}"
  echo "  ╔══════════════════════════════════════════════════════════╗"
  echo "  ║          INFOMATT360 INSTALADO EXITOSAMENTE            ║"
  echo "  ╚══════════════════════════════════════════════════════════╝"
  echo -e "${NC}"

  echo -e "  ${WHITE}${BOLD}🌐 URLs de acceso:${NC}"
  echo -e "    Local:    ${CYAN}http://localhost:${PORT}${NC}"
  echo -e "    Externa:  ${CYAN}https://${FULL_DOMAIN}${NC}"
  echo ""

  echo -e "  ${WHITE}${BOLD}🗄️  Base de datos:${NC}"
  echo -e "    Tipo:      SQLite"
  echo -e "    Archivo:   ${CYAN}${INSTALL_DIR}/data/infomatt360.db${NC}"
  echo -e "    Backups:   Copiar el archivo .db a otra ubicación"
  echo ""

  echo -e "  ${WHITE}${BOLD}🔑 Credenciales:${NC}"
  echo -e "    ${GREEN}Admin:${NC}        ${ADMIN_EMAIL}"
  [ -n "$USER2_NAME" ] && echo -e "    ${YELLOW}${USER2_ROL^}:${NC}  ${USER2_EMAIL}"
  [ -n "$USER3_NAME" ] && echo -e "    ${YELLOW}${USER3_ROL^}:${NC}  ${USER3_EMAIL}"
  echo ""

  echo -e "  ${WHITE}${BOLD}📱 Instalar en teléfono:${NC}"
  echo -e "    1. Abre ${CYAN}https://${FULL_DOMAIN}${NC} en Chrome del teléfono"
  echo -e "    2. Menú ⋮ → \"Instalar aplicación\" o \"Añadir a pantalla\""
  echo -e "    3. La app aparecerá como ícono en tu teléfono"
  echo ""

  echo -e "  ${WHITE}${BOLD}🔧 Comandos útiles:${NC}"
  echo -e "    Ver estado:     ${CYAN}systemctl status infomatt360-mobile${NC}"
  echo -e "    Ver logs:       ${CYAN}journalctl -u infomatt360-mobile -f${NC}"
  echo -e "    Reiniciar:      ${CYAN}systemctl restart infomatt360-mobile${NC}"
  echo -e "    Backup BD:      ${CYAN}cp ${INSTALL_DIR}/data/infomatt360.db ~/backup-\$(date +%Y%m%d).db${NC}"
  echo ""

  echo -e "  ${WHITE}${BOLD}📂 Archivos:${NC}"
  echo -e "    Aplicación:     ${INSTALL_DIR}/"
  echo -e "    Configuración:  ${INSTALL_DIR}/.env"
  echo -e "    Base de datos:  ${INSTALL_DIR}/data/infomatt360.db"
  echo -e "    Uploads:        ${INSTALL_DIR}/uploads/"
  echo -e "    Nginx:          /etc/nginx/sites-available/infomatt360-mobile"
  echo -e "    Servicio:       /etc/systemd/system/infomatt360-mobile.service"
  echo ""

  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo -e "  ${WHITE}InfoMatt Colombia SAS — soporte: info@infomatt.co${NC}"
  echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
  echo ""
}

# ══════════════════════════════════════════════════════════════════
# MAIN — Ejecutar el asistente
# ══════════════════════════════════════════════════════════════════
main() {
  banner
  echo ""
  echo -e "  ${WHITE}Bienvenido al asistente de instalación de InfoMatt360 Mobile.${NC}"
  echo -e "  ${WHITE}Este asistente te guiará paso a paso para configurar el sistema.${NC}"
  echo ""
  echo -ne "  Presiona ${CYAN}Enter${NC} para comenzar..."
  read -r

  check_requirements   # Paso 0
  configure_domain     # Paso 1
  configure_organization # Paso 2
  configure_admin      # Paso 3
  configure_sample_data # Paso 4
  show_summary         # Paso 5
  run_installation     # Paso 6
  show_final           # Paso 7
}

main "$@"
