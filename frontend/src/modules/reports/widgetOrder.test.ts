import { describe, expect, it } from 'vitest';
import { reorderWidgets } from './widgetOrder';
import type { ReportWidget } from './types';

function sampleWidgets(): ReportWidget[] {
  return [
    { type: 'kpi', title: 'KPI', source: { kind: 'records_total' } },
    { type: 'table', title: 'Tabla' },
    { type: 'chart', title: 'Grafico', chart_kind: 'bar', source: { kind: 'status_breakdown' } },
  ];
}

describe('reorderWidgets', () => {
  it('mueve un widget de indice 0 a 2 conservando el resto en orden', () => {
    const result = reorderWidgets(sampleWidgets(), 0, 2);
    expect(result.map((widget) => widget.type)).toEqual(['table', 'chart', 'kpi']);
  });

  it('mueve un widget de indice 2 a 0 conservando el resto en orden', () => {
    const result = reorderWidgets(sampleWidgets(), 2, 0);
    expect(result.map((widget) => widget.type)).toEqual(['chart', 'kpi', 'table']);
  });

  it('con un solo widget no hace nada', () => {
    const single: ReportWidget[] = [{ type: 'table', title: 'Tabla' }];
    expect(reorderWidgets(single, 0, 0)).toBe(single);
  });

  it('con indices iguales es un no-op', () => {
    const widgets = sampleWidgets();
    expect(reorderWidgets(widgets, 1, 1)).toBe(widgets);
  });

  it('con un indice fuera de rango es un no-op', () => {
    const widgets = sampleWidgets();
    expect(reorderWidgets(widgets, 0, 10)).toBe(widgets);
  });
});
