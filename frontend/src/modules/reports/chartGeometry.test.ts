import { describe, expect, it } from 'vitest';
import { CHART_PALETTE, barChartGeometry, paletteColor, pieChartGeometry } from './chartGeometry';

describe('paletteColor', () => {
  it('cicla correctamente pasado el largo de la paleta', () => {
    expect(paletteColor(0)).toBe(CHART_PALETTE[0]);
    expect(paletteColor(CHART_PALETTE.length)).toBe(CHART_PALETTE[0]);
    expect(paletteColor(CHART_PALETTE.length + 2)).toBe(CHART_PALETTE[2]);
  });
});

describe('barChartGeometry', () => {
  const opts = { width: 480, height: 240, padding: 20 };

  it('la altura de cada barra es proporcional a su valor', () => {
    const bars = barChartGeometry([{ label: 'a', value: 10 }, { label: 'b', value: 5 }], opts);
    expect(bars[0].height).toBeCloseTo(bars[1].height * 2, 5);
  });

  it('todas las barras quedan en 0 cuando el valor maximo es 0', () => {
    const bars = barChartGeometry([{ label: 'a', value: 0 }, { label: 'b', value: 0 }], opts);
    expect(bars.every((bar) => bar.height === 0)).toBe(true);
  });

  it('sin puntos no genera barras', () => {
    expect(barChartGeometry([], opts)).toEqual([]);
  });
});

describe('pieChartGeometry', () => {
  const opts = { cx: 120, cy: 120, r: 100 };

  it('los porcentajes de las rebanadas suman ~100', () => {
    const slices = pieChartGeometry([{ label: 'a', value: 30 }, { label: 'b', value: 70 }], opts);
    const total = slices.reduce((sum, slice) => sum + slice.percent, 0);
    expect(total).toBeCloseTo(100, 1);
  });

  it('un solo punto (100%) genera un path valido sin romper', () => {
    const slices = pieChartGeometry([{ label: 'unico', value: 42 }], opts);
    expect(slices).toHaveLength(1);
    expect(slices[0].percent).toBe(100);
    expect(slices[0].path.startsWith('M')).toBe(true);
  });

  it('sin valor total (todo en 0) no genera rebanadas', () => {
    expect(pieChartGeometry([{ label: 'a', value: 0 }], opts)).toEqual([]);
  });
});
