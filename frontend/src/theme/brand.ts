/**
 * Proyecto: InfoMatt360
 * Modulo: Brand Theme
 * Responsabilidad: Centralizar colores, tipografia y tokens visuales aprobados.
 *
 * Paleta turquesa + azul marino (docs/123), tomada del mockup aprobado por el
 * usuario. Estos valores son el FALLBACK: `modules/branding/brandingLoader.ts`
 * los sobreescribe con los colores que cada organizacion configure en la
 * pantalla de Marca (docs/122), asi que la marca blanca sigue funcionando.
 */

export const brand = {
  colors: {
    /** Superficies oscuras: barra lateral y encabezados sobre fondo oscuro. */
    darkBlue: '#0F172A',
    navySoft: '#1E293B',
    /** Color de accion principal (botones, enlaces, estado activo). */
    primaryBlue: '#0D9488',
    primaryStrong: '#0F766E',
    /** Acento para graficos y realces. */
    cyan: '#14B8A6',
    /** Fondo suave derivado del acento (chips, filas resaltadas). */
    lightBlue: '#CCFBF1',
    white: '#FFFFFF',
  },
  fontFamily: 'Inter, Montserrat, system-ui, -apple-system, Segoe UI, Arial, sans-serif',
  radius: {
    sm: '6px',
    md: '8px',
    lg: '12px',
  },
};
