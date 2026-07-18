import { barChartGeometry, pieChartGeometry } from './chartGeometry';
import type { ChartPoint } from './types';

export function ReportChart({ kind, points }: { kind: 'bar' | 'pie'; points: ChartPoint[] }) {
  if (points.length === 0) {
    return <p className="reports-chart-empty">Sin datos para graficar.</p>;
  }

  if (kind === 'pie') {
    const slices = pieChartGeometry(points, { cx: 120, cy: 120, r: 100 });
    return (
      <div className="reports-chart">
        <svg viewBox="0 0 240 240" role="img" aria-label="Grafico de torta">
          {slices.map((slice) => <path key={slice.label} d={slice.path} fill={slice.color} />)}
        </svg>
        <ul className="reports-chart-legend">
          {slices.map((slice) => (
            <li key={slice.label}><span className="reports-chart-swatch" style={{ background: slice.color }} />{slice.label}: {slice.value} ({slice.percent}%)</li>
          ))}
        </ul>
      </div>
    );
  }

  const bars = barChartGeometry(points, { width: 480, height: 240, padding: 24 });
  return (
    <div className="reports-chart">
      <svg viewBox="0 0 480 240" role="img" aria-label="Grafico de barras">
        {bars.map((bar) => (
          <g key={bar.label}>
            <rect x={bar.x} y={bar.y} width={bar.width} height={bar.height} fill={bar.color} />
            <text x={bar.x + bar.width / 2} y={232} textAnchor="middle" fontSize="11">{bar.label}</text>
            <text x={bar.x + bar.width / 2} y={Math.max(bar.y - 4, 12)} textAnchor="middle" fontSize="11">{bar.value}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
