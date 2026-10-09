#!/bin/bash
# ══════════════════════════════════════════════════════════════════
# InfoMatt360 — Generador de APK con Capacitor
# Genera un APK Android instalable directamente en teléfonos
# ══════════════════════════════════════════════════════════════════
set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
NC='\033[0m'

echo -e "${CYAN}"
echo "  ╔══════════════════════════════════════════════════╗"
echo "  ║    InfoMatt360 — Generador de APK Android       ║"
echo "  ╚══════════════════════════════════════════════════╝"
echo -e "${NC}"

# ── Verificar requisitos ──
echo -e "${WHITE}Verificando requisitos...${NC}"

# Node.js
if ! command -v node &> /dev/null; then
  echo -e "${RED}❌ Node.js no instalado${NC}"
  exit 1
fi
echo -e "  ${GREEN}✅${NC} Node.js $(node -v)"

# Java (necesario para Android SDK / Gradle)
if command -v java &> /dev/null; then
  echo -e "  ${GREEN}✅${NC} Java $(java -version 2>&1 | head -1)"
else
  echo -e "  ${YELLOW}⚠️${NC}  Java no encontrado — instalando OpenJDK 17..."
  if command -v apt &> /dev/null; then
    sudo apt install -y openjdk-17-jdk-headless > /dev/null 2>&1
  elif command -v dnf &> /dev/null; then
    sudo dnf install -y java-17-openjdk-devel > /dev/null 2>&1
  elif command -v brew &> /dev/null; then
    brew install openjdk@17 > /dev/null 2>&1
  fi
  echo -e "  ${GREEN}✅${NC} Java instalado"
fi

# Android SDK
if [ -z "$ANDROID_HOME" ] && [ -z "$ANDROID_SDK_ROOT" ]; then
  # Buscar en ubicaciones comunes
  for sdk_path in "$HOME/Android/Sdk" "$HOME/Library/Android/sdk" "/opt/android-sdk" "/usr/lib/android-sdk"; do
    if [ -d "$sdk_path" ]; then
      export ANDROID_HOME="$sdk_path"
      break
    fi
  done
fi

if [ -n "$ANDROID_HOME" ] && [ -d "$ANDROID_HOME" ]; then
  echo -e "  ${GREEN}✅${NC} Android SDK: $ANDROID_HOME"
else
  echo -e "  ${YELLOW}⚠️${NC}  Android SDK no encontrado"
  echo ""
  echo -e "  ${WHITE}Para generar el APK necesitas el Android SDK.${NC}"
  echo -e "  ${WHITE}Opciones:${NC}"
  echo ""
  echo -e "  ${CYAN}Opción 1 — Android Studio (recomendado):${NC}"
  echo -e "    Descarga: https://developer.android.com/studio"
  echo -e "    Instala y abre Android Studio → SDK Manager → instalar SDK"
  echo ""
  echo -e "  ${CYAN}Opción 2 — Solo Command Line Tools:${NC}"
  echo -e "    Descarga: https://developer.android.com/studio#command-tools"
  echo -e "    mkdir -p \$HOME/Android/Sdk/cmdline-tools"
  echo -e "    unzip commandlinetools-*.zip -d \$HOME/Android/Sdk/cmdline-tools/latest"
  echo -e "    export ANDROID_HOME=\$HOME/Android/Sdk"
  echo -e "    \$ANDROID_HOME/cmdline-tools/latest/bin/sdkmanager 'platforms;android-34' 'build-tools;34.0.0'"
  echo ""
  echo -e "  ${CYAN}Opción 3 — Generar en tu PC con Android Studio:${NC}"
  echo -e "    Copia este proyecto a tu PC con Android Studio instalado"
  echo -e "    y ejecuta este script allí."
  echo ""

  read -p "  ¿Deseas instalar Android SDK automáticamente? [S/n]: " install_sdk
  install_sdk=${install_sdk:-s}

  case "$install_sdk" in
    [sS]|[sS][iI]|[yY])
      echo ""
      echo -e "  ${YELLOW}Instalando Android SDK (esto toma ~5 minutos)...${NC}"

      export ANDROID_HOME="$HOME/Android/Sdk"
      mkdir -p "$ANDROID_HOME/cmdline-tools"

      # Detectar plataforma
      OS=$(uname -s | tr '[:upper:]' '[:lower:]')
      case "$OS" in
        linux) SDK_URL="https://dl.google.com/android/repository/commandlinetools-linux-11076708_latest.zip" ;;
        darwin) SDK_URL="https://dl.google.com/android/repository/commandlinetools-mac-11076708_latest.zip" ;;
        *) echo -e "  ${RED}❌ Sistema no soportado para instalación automática${NC}"; exit 1 ;;
      esac

      cd /tmp
      curl -sL -o cmdline-tools.zip "$SDK_URL"
      unzip -qo cmdline-tools.zip -d "$ANDROID_HOME/cmdline-tools/"
      mv "$ANDROID_HOME/cmdline-tools/cmdline-tools" "$ANDROID_HOME/cmdline-tools/latest" 2>/dev/null || true

      export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

      yes | sdkmanager --licenses > /dev/null 2>&1 || true
      sdkmanager "platforms;android-34" "build-tools;34.0.0" "platform-tools" > /dev/null 2>&1

      echo -e "  ${GREEN}✅${NC} Android SDK instalado en $ANDROID_HOME"
      ;;
    *)
      echo -e "  ${YELLOW}Saltando. Puedes ejecutar este script después de instalar el SDK.${NC}"
      exit 0
      ;;
  esac
fi

export PATH="$ANDROID_HOME/cmdline-tools/latest/bin:$ANDROID_HOME/platform-tools:$PATH"

# ── Configurar URL del servidor ──
echo ""
echo -e "${WHITE}Configuración del servidor API:${NC}"
echo ""
echo -e "  La app necesita conectarse a tu servidor InfoMatt360."
echo -e "  ${CYAN}Ejemplo:${NC} https://mobile.infomatt360.tecnomatt.com"
echo ""
read -p "  URL del servidor API: " SERVER_URL

if [ -z "$SERVER_URL" ]; then
  echo -e "  ${YELLOW}⚠️${NC}  Sin URL — la app usará modo demo/offline"
  SERVER_URL=""
fi

# ── Instalar dependencias de Capacitor ──
echo ""
echo -e "${WHITE}Instalando Capacitor...${NC}"

cd "$(dirname "$0")"

# Instalar dependencias de Capacitor
npm install @capacitor/core @capacitor/cli --save --loglevel=error 2>/dev/null
npm install @capacitor/android @capacitor/app @capacitor/haptics @capacitor/keyboard @capacitor/status-bar @capacitor/splash-screen @capacitor/filesystem @capacitor/camera @capacitor/geolocation @capacitor/network --save --loglevel=error 2>/dev/null

echo -e "  ${GREEN}✅${NC} Capacitor instalado"

# ── Actualizar index.html con la URL del servidor ──
if [ -n "$SERVER_URL" ]; then
  echo -e "  ${GREEN}✅${NC} URL del servidor: $SERVER_URL"
  # Insertar la URL del servidor en el HTML
  if grep -q "API_BASE_URL" public/index.html; then
    sed -i "s|API_BASE_URL:.*|API_BASE_URL: '${SERVER_URL}/api/v1',|" public/index.html
  fi
fi

# ── Inicializar proyecto Android ──
echo ""
echo -e "${WHITE}Generando proyecto Android...${NC}"

npx cap add android 2>/dev/null || true
npx cap sync android 2>/dev/null

echo -e "  ${GREEN}✅${NC} Proyecto Android generado"

# ── Personalizar Android ──
# Colores de la marca InfoMatt
COLORS_FILE="android/app/src/main/res/values/colors.xml"
if [ -f "$COLORS_FILE" ]; then
  cat > "$COLORS_FILE" << 'COLORSEOF'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <color name="colorPrimary">#0066CC</color>
    <color name="colorPrimaryDark">#0A2540</color>
    <color name="colorAccent">#00C2FF</color>
    <color name="splash_bg">#0A2540</color>
</resources>
COLORSEOF
  echo -e "  ${GREEN}✅${NC} Colores de marca aplicados"
fi

# Strings
STRINGS_FILE="android/app/src/main/res/values/strings.xml"
if [ -f "$STRINGS_FILE" ]; then
  cat > "$STRINGS_FILE" << 'STRINGSEOF'
<?xml version="1.0" encoding="utf-8"?>
<resources>
    <string name="app_name">InfoMatt360</string>
    <string name="title_activity_main">InfoMatt360</string>
    <string name="package_name">co.infomatt.infomatt360</string>
    <string name="custom_url_scheme">co.infomatt.infomatt360</string>
</resources>
STRINGSEOF
fi

# ── Compilar APK ──
echo ""
echo -e "${WHITE}Compilando APK (esto toma 2-5 minutos)...${NC}"

cd android

# Dar permisos al gradlew
chmod +x gradlew 2>/dev/null || true

# Build debug APK
./gradlew assembleDebug 2>&1 | tail -5

APK_PATH="app/build/outputs/apk/debug/app-debug.apk"

if [ -f "$APK_PATH" ]; then
  # Copiar a ubicación accesible
  cp "$APK_PATH" "../InfoMatt360.apk"
  cd ..
  APK_SIZE=$(du -h "InfoMatt360.apk" | cut -f1)

  echo ""
  echo -e "${GREEN}"
  echo "  ╔══════════════════════════════════════════════════╗"
  echo "  ║         APK GENERADO EXITOSAMENTE               ║"
  echo "  ╚══════════════════════════════════════════════════╝"
  echo -e "${NC}"
  echo -e "  ${WHITE}Archivo:${NC}  $(pwd)/InfoMatt360.apk"
  echo -e "  ${WHITE}Tamaño:${NC}   ${APK_SIZE}"
  echo ""
  echo -e "  ${WHITE}Para instalar en el teléfono:${NC}"
  echo -e "    1. Envía el archivo ${CYAN}InfoMatt360.apk${NC} al teléfono"
  echo -e "       (por WhatsApp, email, USB, o enlace de descarga)"
  echo -e "    2. Abre el archivo en el teléfono"
  echo -e "    3. Permite 'Instalar desde fuentes desconocidas'"
  echo -e "    4. Instalar"
  echo ""
  echo -e "  ${WHITE}Para generar APK de producción (firmado):${NC}"
  echo -e "    cd android && ./gradlew assembleRelease"
  echo ""
else
  cd ..
  echo -e "  ${RED}❌ Error al compilar el APK${NC}"
  echo -e "  Revisa los errores arriba o ejecuta manualmente:"
  echo -e "    cd $(pwd)/android && ./gradlew assembleDebug --stacktrace"
fi
