import { describe, expect, it } from 'vitest';

import { getVirtualWindow } from './useVirtualWindow';

describe('getVirtualWindow', () => {
  it('ajusta el indice activo despues de reducir la lista', () => {
    const result = getVirtualWindow(['a', 'b', 'c'], 99, 2);

    expect(result).toEqual({ visibleItems: ['b', 'c'], start: 1, end: 3 });
  });

  it('maneja listas vacias', () => {
    expect(getVirtualWindow([], 5, 10)).toEqual({ visibleItems: [], start: 0, end: 0 });
  });
});
