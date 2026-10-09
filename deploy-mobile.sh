#!/bin/bash
# ══════════════════════════════════════════════════════════
# InfoMatt360 Mobile — Script de despliegue en producción
# Ejecutar en el servidor donde corre infomatt360.tecnomatt.com
# ══════════════════════════════════════════════════════════
set -e

echo "═══════════════════════════════════════════"
echo "  InfoMatt360 Mobile — Despliegue"
echo "═══════════════════════════════════════════"

# 1. Clonar el repo (si no existe)
APP_DIR="/opt/infomatt360-mobile"
if [ -d "$APP_DIR" ]; then
  echo "→ Actualizando código existente..."
  cd "$APP_DIR"
  git pull origin main
else
  echo "→ Clonando repositorio..."
  git clone https://github.com/amopanta/infomatt360.git /tmp/infomatt360-clone
  mkdir -p "$APP_DIR"
  cp -r /tmp/infomatt360-clone/mobile/* "$APP_DIR/"
  cp -r /tmp/infomatt360-clone/mobile/.* "$APP_DIR/" 2>/dev/null || true
  rm -rf /tmp/infomatt360-clone
fi

cd "$APP_DIR"

# 2. Crear .env si no existe
if [ ! -f .env ]; then
  echo "→ Creando archivo .env..."
  cp .env.example .env
  # Generar secretos aleatorios
  JWT_SECRET=$(openssl rand -hex 32)
  JWT_REFRESH=$(openssl rand -hex 32)
  sed -i "s|tu_secreto_super_seguro_aqui|$JWT_SECRET|" .env
  sed -i "s|otro_secreto_seguro_diferente|$JWT_REFRESH|" .env
  sed -i "s|NODE_ENV=development|NODE_ENV=production|" .env
  echo "  ✅ Secretos JWT generados"
fi

# 3. Verificar Docker
if command -v docker &> /dev/null; then
  echo "→ Docker detectado. Construyendo imagen..."

  docker build -t infomatt360-mobile .

  # Parar contenedor anterior si existe
  docker stop infomatt360-mobile 2>/dev/null || true
  docker rm infomatt360-mobile 2>/dev/null || true

  # Crear directorio de datos persistente
  mkdir -p "$APP_DIR/data" "$APP_DIR/uploads"

  # Ejecutar contenedor
  docker run -d \
    --name infomatt360-mobile \
    --restart unless-stopped \
    -p 3001:3000 \
    --env-file .env \
    -v "$APP_DIR/data:/app/data" \
    -v "$APP_DIR/uploads:/app/uploads" \
    infomatt360-mobile

  echo "  ✅ Contenedor Docker corriendo en puerto 3001"

  # Seed datos de prueba dentro del contenedor
  echo "→ Cargando datos de prueba..."
  docker exec infomatt360-mobile node src/utils/seed.js 2>/dev/null || echo "  (seed ya ejecutado)"

else
  echo "→ Docker no disponible. Usando Node.js directo..."

  # Verificar Node.js
  if ! command -v node &> /dev/null; then
    echo "❌ Node.js no instalado. Instala Node.js 18+ primero."
    exit 1
  fi

  echo "→ Instalando dependencias..."
  npm install --production

  mkdir -p data uploads

  echo "→ Cargando datos de prueba..."
  node src/utils/seed.js 2>/dev/null || echo "  (seed ya ejecutado)"

  # Crear servicio systemd
  echo "→ Configurando servicio systemd..."
  cat > /etc/systemd/system/infomatt360-mobile.service << 'SVCEOF'
[Unit]
Description=InfoMatt360 Mobile API
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/infomatt360-mobile
ExecStart=/usr/bin/node src/server.js
Restart=on-failure
RestartSec=5
Environment=NODE_ENV=production
EnvironmentFile=/opt/infomatt360-mobile/.env

[Install]
WantedBy=multi-user.target
SVCEOF

  systemctl daemon-reload
  systemctl enable infomatt360-mobile
  systemctl start infomatt360-mobile
  echo "  ✅ Servicio systemd creado y arrancado"
fi

# 4. Configurar Nginx (si existe)
if command -v nginx &> /dev/null; then
  echo ""
  echo "→ Configurando Nginx..."

  NGINX_CONF="/etc/nginx/sites-available/infomatt360-mobile"
  cat > "$NGINX_CONF" << 'NGINXEOF'
server {
    listen 80;
    server_name mobile.infomatt360.tecnomatt.com;

    location / {
        proxy_pass http://127.0.0.1:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        client_max_body_size 10M;
    }
}
NGINXEOF

  ln -sf "$NGINX_CONF" /etc/nginx/sites-enabled/ 2>/dev/null || true

  # Verificar config
  if nginx -t 2>/dev/null; then
    systemctl reload nginx
    echo "  ✅ Nginx configurado: mobile.infomatt360.tecnomatt.com"

    # SSL con certbot si está disponible
    if command -v certbot &> /dev/null; then
      echo "→ Generando certificado SSL..."
      certbot --nginx -d mobile.infomatt360.tecnomatt.com --non-interactive --agree-tos --email admin@infomatt.co 2>/dev/null || echo "  ⚠️ Configura SSL manualmente o verifica el dominio DNS"
    fi
  else
    echo "  ⚠️ Error en config Nginx. Revisa manualmente."
  fi
fi

# 5. Verificar
echo ""
echo "═══════════════════════════════════════════"
echo "  DESPLIEGUE COMPLETO"
echo "═══════════════════════════════════════════"
echo ""
sleep 2

# Test health
HEALTH=$(curl -s http://localhost:3001/api/health 2>/dev/null)
if echo "$HEALTH" | grep -q "ok"; then
  echo "  ✅ API: http://localhost:3001 — OK"
else
  echo "  ⚠️ API no responde aún. Verifica los logs:"
  echo "     docker logs infomatt360-mobile"
  echo "     journalctl -u infomatt360-mobile"
fi

echo ""
echo "  📱 URL local:  http://localhost:3001"
echo "  🌐 URL externa: https://mobile.infomatt360.tecnomatt.com"
echo ""
echo "  Credenciales de prueba:"
echo "  ├── carlos@infomatt.co / Carlos123!"
echo "  ├── laura@infomatt.co  / Laura123!"
echo "  └── admin@infomatt.co  / Admin123!"
echo ""
echo "  Para instalar en el teléfono:"
echo "  Abre la URL en Chrome → Menú ⋮ → Instalar app"
echo ""
