# 123. Sistema de diseño: paleta turquesa, densidad y primitivos compartidos

## Qué cierra esto

La devolución del usuario tras probar la aplicación (2026-07-25): *"me gustaría que la interfaz se pareciera a la de KoboToolbox, porque se ve más organizada"*, *"disminuir el tamaño de la letra y los espacios"*, *"que no se viera tan desorganizada"*. Después compartió un mockup de 16 pantallas con la identidad visual deseada (turquesa + azul marino, tarjetas compactas, tablas densas).

## Por qué se veía desorganizada: el diagnóstico

No era percepción. Medido sobre el código:

- **No existía un sistema de diseño.** `styles.css` tenía 736 líneas con **416 colores escritos a mano** (76 distintos) y apenas 23 variables CSS. `theme/brand.ts` definía tokens pero casi no estaban conectados al CSS.
- **No había componentes compartidos.** Cada módulo inventó su propio prefijo (`audit-*`, `erp-*`, `runtime-*`, `builder-*`, `records-*`, `ds-*`) y redefinió su propia tarjeta. Resultado: radios de 10/12/14/16/18px y sombras distintas conviviendo en pantallas contiguas.
- **`.panel` se usaba en 5 pantallas y no tenía ni una regla de estilo definida** — por eso la pantalla de Marca (docs/122) se veía plana.
- La tipografía base era la del navegador (16px), demasiado grande para pantallas con mucha información.

## Decisiones acordadas con el usuario

Antes de tocar código se acordaron tres cosas (AskUserQuestion):

1. **Sistema de diseño primero**, en vez de rediseñar pantalla por pantalla: al no haber tokens, definirlos mejora las 27 pantallas de una sola vez.
2. **Paleta del mockup**: turquesa (`#0D9488` / `#14B8A6`) + azul marino (`#0F172A`).
3. **Las 3 pantallas del mockup que muestran funcionalidad inexistente quedan fuera** — Validación documental con OCR/huella, IA Assistant conversacional y Análisis predictivo. Se le señaló explícitamente que un rediseño visual no las crea; construirlas sería trabajo nuevo y separado.

## Qué se hizo

### Tokens (`:root` en `styles.css` + `theme/brand.ts`)

Color de marca, superficies, texto, bordes, estados (éxito/advertencia/peligro/info), escala tipográfica compacta (**10→20px, con base en 12px**), espaciados, radios y sombras.

El alto de fila tiene sus propios tokens (`--cell-py: 5px` / `--cell-px: 10px`), separados de la escala de espaciado general, para poder apretar o soltar la densidad de las tablas sin tocar el resto del sistema.

`--brand-primary`, `--brand-accent` y `--brand-background` **siguen siendo sobreescribibles por organización**: `brandingLoader.ts` los inyecta en caliente con los colores que cada organización configure en la pantalla de Marca (docs/122). Los valores de `theme/brand.ts` son el fallback, no una imposición.

### Migración de colores

493 reemplazos a tokens en dos pasadas: los 8 colores dominantes (376) y los semánticos dispersos por módulo (117). Los colores hardcodeados sin contar blanco bajaron de **416 a 39** — el resto son casos puntuales.

### Normalización de la inconsistencia entre módulos

- 23 sombras de tarjeta distintas → `var(--shadow-sm/md)`
- 139 radios dispares → `var(--radius-sm/md/lg/pill)`
- 73 fondos `#ffffff` → `var(--surface)`
- 23 rellenos generosos (20/22px) → escala de espaciado
- 9 realces de foco/arrastre con la paleta azul vieja → turquesa

### Shell y primitivos

Barra lateral azul marino plana y compacta (232px, ítems de 12px, estado activo turquesa sólido en vez del degradado anterior), header de 56px (antes 72px), y un bloque nuevo de primitivos compartidos: `.panel`/`.card`, `.stat-card` con etiqueta/cifra/variación, `.badge` de estado en 4 variantes, `.feedback`, y estilos de tabla densa (encabezado gris en mayúsculas de 11px, filas de 8×12px, hover).

Se agregaron además defaults a nivel de elemento (`h1`-`h6`, `small`, `input`/`select`/`textarea`/`button`) para alcanzar a los módulos que definieron su propio prefijo de clases sin tener que reescribirlos uno por uno.

## Verificación en vivo (dev server con recarga en caliente)

Se levantó el servidor de Vite contra el backend real del stack Podman (agregando su origen a `CORS_ALLOWED_ORIGINS` solo en el `.env.production` local) para poder iterar viendo el resultado.

**Medición de consistencia sobre el DOM renderizado, recorriendo 7 pantallas:**

| | Resultado |
|---|---|
| Radios distintos | **7** (dominados por los 3 del sistema + pastilla) |
| Sombras distintas | **4** (dominadas por las 2 del sistema) |
| Tamaños de letra distintos | **8**, siguiendo la escala |
| Desbordes horizontales | **0 en 13 pantallas** |
| Errores de consola | ninguno |

Valores computados confirmados en vivo: `html` en 12px, barra lateral `rgb(15,23,42)`, ítem activo `rgb(13,148,136)`, ítems de menú de 27px, tabla de registros con encabezado de 10px en mayúsculas y celdas de 11px.

Un hallazgo del recorrido: los controles de formulario no heredan la fuente del documento y el navegador les aplicaba su propio `13.3333px`, rompiendo la escala en 142 elementos. Se corrigió con una regla explícita.

### Ajuste de densidad pedido por el usuario

Tras ver el resultado, pidió bajar la letra a 12px y apretar más las filas. Al medir el DOM apareció la causa real de las filas altas: **la columna Fecha envolvía a dos líneas** (`"25/7/2026, 22:53:12"` no entraba en su ancho), estirando toda la fila a 44px aunque el contenido más alto fuera un botón de 23px.

Se resolvió con el mismo criterio que usan las tablas de datos de KoboToolbox: **una sola línea por fila** (`white-space: nowrap` + truncado con puntos suspensivos), dejando que el ancho sobrante lo absorba el scroll horizontal que el contenedor ya tenía. Los valores truncados siguen completos en el detalle del registro.

Resultado medido: filas de **44px → 32px**, parejas en toda la tabla, y la página sigue sin desbordar (verificado en 10 pantallas).

`tsc --noEmit`, `vitest run` (101/101) y `npm run build` limpios.

## Límite explícito

Esto es **el sistema de diseño, no el rediseño pantalla por pantalla**. Todas las pantallas heredaron la paleta, la densidad, los radios y las sombras nuevas, pero los diseños específicos del mockup (el mapa de calor del monitoreo, la disposición exacta de los gráficos del dashboard, la tabla estilo Kobo con ocultar columnas y buscador por columna) siguen pendientes como trabajos aparte.

De la devolución original del usuario quedan abiertos: **tabla de registros estilo KoboToolbox** (ocultar columnas, buscador por columna, selector de filas por página, columnas fijas al hacer scroll) y **firma como imagen en las actas**.
