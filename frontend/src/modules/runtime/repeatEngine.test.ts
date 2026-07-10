import { describe, expect, it } from 'vitest';

import { normalizeRepeatCount, reconcileRepeatItems } from './repeatEngine';
import type { RepeatItem } from './types';

const existing: RepeatItem[] = [
  { id: 'productos_1', index: 0, values: { nombre: 'A' } },
  { id: 'productos_2', index: 1, values: { nombre: 'B' } },
  { id: 'productos_3', index: 2, values: { nombre: 'C' } },
];

describe('reconcileRepeatItems', () => {
  it('conserva valores al reducir y volver a crecer', () => {
    const reduced = reconcileRepeatItems('productos', existing, 2);
    const expanded = reconcileRepeatItems('productos', reduced, 4);

    expect(reduced.map((item) => item.values)).toEqual([{ nombre: 'A' }, { nombre: 'B' }]);
    expect(expanded).toEqual([
      existing[0],
      existing[1],
      { id: 'productos_3', index: 2, values: {} },
      { id: 'productos_4', index: 3, values: {} },
    ]);
  });

  it('normaliza cantidades invalidas', () => {
    expect(normalizeRepeatCount(-2)).toBe(0);
    expect(normalizeRepeatCount(2.9)).toBe(2);
    expect(normalizeRepeatCount(Number.NaN)).toBe(0);
    expect(normalizeRepeatCount(Number.POSITIVE_INFINITY)).toBe(0);
  });

  it('evita identificadores duplicados al reconciliar datos importados', () => {
    const imported = [
      { id: 'productos_1', index: 0, values: {} },
      { id: 'productos_3', index: 1, values: {} },
    ];

    const result = reconcileRepeatItems('productos', imported, 3);

    expect(result.map((item) => item.id)).toEqual(['productos_1', 'productos_3', 'productos_3_2']);
  });
});
