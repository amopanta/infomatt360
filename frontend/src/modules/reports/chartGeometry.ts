import type { ChartPoint } from './types';

/** Sin dependencia de graficos: barra/torta se calculan como geometria SVG
 * a mano (docs/96 item #6, docs/111) -- este repo evita dependencias
 * nuevas para este tipo de necesidad (xhtml2pdf en vez de WeasyPrint,
 * drag HTML5 nativo en vez de una libreria de DnD). */
export const CHART_PALETTE = ['#0066cc', '#00c2ff', '#0a2540', '#4dd4ff', '#3384d6', '#7fe3ff'];

export function paletteColor(index: number): string {
  return CHART_PALETTE[index % CHART_PALETTE.length];
}

export type BarGeometry = { x: number; y: number; width: number; height: number; label: string; value: number; color: string };

export function barChartGeometry(points: ChartPoint[], opts: { width: number; height: number; padding: number }): BarGeometry[] {
  const { width, height, padding } = opts;
  if (points.length === 0) return [];
  const maxValue = Math.max(...points.map((point) => point.value), 0);
  const innerWidth = Math.max(width - padding * 2, 0);
  const innerHeight = Math.max(height - padding * 2, 0);
  const slotWidth = innerWidth / points.length;
  const barWidth = slotWidth * 0.7;
  return points.map((point, index) => {
    const barHeight = maxValue > 0 ? (point.value / maxValue) * innerHeight : 0;
    return {
      x: padding + index * slotWidth + (slotWidth - barWidth) / 2,
      y: padding + innerHeight - barHeight,
      width: barWidth,
      height: barHeight,
      label: point.label,
      value: point.value,
      color: paletteColor(index),
    };
  });
}

export type PieSlice = { path: string; label: string; value: number; percent: number; color: string };

export function pieChartGeometry(points: ChartPoint[], opts: { cx: number; cy: number; r: number }): PieSlice[] {
  const { cx, cy, r } = opts;
  const total = points.reduce((sum, point) => sum + point.value, 0);
  if (total <= 0) return [];

  // Un solo punto (100%): el comando de arco SVG no puede dibujar un
  // circulo completo con un solo tramo (inicio y fin coinciden), asi que
  // se arma como dos semicirculos.
  if (points.length === 1) {
    const point = points[0];
    const path = `M ${cx},${cy - r} A ${r},${r} 0 1,1 ${cx},${cy + r} A ${r},${r} 0 1,1 ${cx},${cy - r} Z`;
    return [{ path, label: point.label, value: point.value, percent: 100, color: paletteColor(0) }];
  }

  let cumulative = 0;
  return points.map((point, index) => {
    const startAngle = (cumulative / total) * 2 * Math.PI - Math.PI / 2;
    cumulative += point.value;
    const endAngle = (cumulative / total) * 2 * Math.PI - Math.PI / 2;
    const x1 = cx + r * Math.cos(startAngle);
    const y1 = cy + r * Math.sin(startAngle);
    const x2 = cx + r * Math.cos(endAngle);
    const y2 = cy + r * Math.sin(endAngle);
    const largeArcFlag = endAngle - startAngle > Math.PI ? 1 : 0;
    const path = `M ${cx},${cy} L ${x1},${y1} A ${r},${r} 0 ${largeArcFlag},1 ${x2},${y2} Z`;
    return { path, label: point.label, value: point.value, percent: Math.round((point.value / total) * 1000) / 10, color: paletteColor(index) };
  });
}
