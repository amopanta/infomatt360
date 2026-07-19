import { fileURLToPath, URL } from 'node:url';
import { defineConfig } from 'vite';
import { VitePWA } from 'vite-plugin-pwa';

const root = fileURLToPath(new URL('.', import.meta.url));

export default defineConfig({
  root,
  // Rutas absolutas (comportamiento por defecto de Vite): necesarias para
  // que las rutas profundas de la SPA (ej. /runtime/xyz) sigan resolviendo
  // los assets correctamente en una recarga completa o un enlace directo,
  // cuando el servidor web devuelve el mismo index.html para cualquier ruta
  // (fallback de SPA). El shell de escritorio (desktop/) ya NO carga esto
  // via file://; sirve el build empaquetado con un servidor HTTP local
  // minimo (ver desktop/src/staticServer.js) para poder usar las mismas
  // rutas absolutas sin el problema de resolucion de file://.
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    rollupOptions: {
      // Entrada multi-pagina (docs/96 item #9, docs/114): tableau-wdc es un
      // Web Data Connector estatico, no parte de la SPA -- Tableau lo carga
      // por URL directa, no via el shell de React.
      input: {
        main: fileURLToPath(new URL('index.html', import.meta.url)),
        'tableau-wdc': fileURLToPath(new URL('tableau-wdc/index.html', import.meta.url)),
      },
    },
  },
  plugins: [
    VitePWA({
      registerType: 'autoUpdate',
      // El manifest es un archivo estatico: no puede reflejar la marca
      // blanca dinamica de cada organizacion (esa se inyecta en runtime via
      // /api/v1/public/branding, ver brandingLoader.ts). Queda con la
      // identidad generica de la plataforma; una PWA instalable por
      // organizacion necesitaria un manifest generado por subdominio, fuera
      // de alcance de este corte.
      manifest: {
        name: 'InfoMatt360',
        short_name: 'InfoMatt360',
        description: 'Plataforma operativa territorial InfoMatt360',
        lang: 'es',
        start_url: './',
        display: 'standalone',
        background_color: '#0a2540',
        theme_color: '#0a2540',
        icons: [
          { src: 'icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: 'icons/icon-512.png', sizes: '512x512', type: 'image/png' },
        ],
      },
      workbox: {
        // tableau-wdc no es parte de la app instalable (lo carga Tableau
        // por URL directa, no un usuario navegando la SPA) -- se excluye del
        // precache de la PWA.
        globIgnores: ['tableau-wdc/**'],
        // El app shell (JS/CSS/HTML) se precachea para que la app cargue
        // incluso sin red. Las llamadas a la API usan NetworkFirst: intenta
        // la red primero (datos frescos) y cae al cache solo si no hay
        // conexion, en vez de servir siempre datos viejos.
        runtimeCaching: [
          {
            urlPattern: ({ url }: { url: URL }) => url.pathname.startsWith('/api/'),
            handler: 'NetworkFirst',
            options: {
              cacheName: 'infomatt360-api-cache',
              networkTimeoutSeconds: 5,
              cacheableResponse: { statuses: [0, 200] },
            },
          },
        ],
      },
    }),
  ],
});
