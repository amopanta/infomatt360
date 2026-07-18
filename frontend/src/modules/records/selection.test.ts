import { describe, expect, it } from 'vitest';
import { deselectPage, isPageFullySelected, selectPage, toggleSelection } from './selection';

describe('toggleSelection', () => {
  it('agrega un id que no estaba', () => {
    expect(toggleSelection(new Set(), 'r1')).toEqual(new Set(['r1']));
  });

  it('quita un id que ya estaba', () => {
    expect(toggleSelection(new Set(['r1', 'r2']), 'r1')).toEqual(new Set(['r2']));
  });

  it('alternar dos veces el mismo id es un no-op', () => {
    const once = toggleSelection(new Set(), 'r1');
    const twice = toggleSelection(once, 'r1');
    expect(twice).toEqual(new Set());
  });
});

describe('selectPage', () => {
  it('une la pagina sin duplicar', () => {
    expect(selectPage(new Set(['r1']), ['r1', 'r2', 'r3'])).toEqual(new Set(['r1', 'r2', 'r3']));
  });

  it('conserva ids de otras paginas ya seleccionados', () => {
    expect(selectPage(new Set(['other-page-id']), ['r1'])).toEqual(new Set(['other-page-id', 'r1']));
  });
});

describe('deselectPage', () => {
  it('quita solo los ids de la pagina, conservando el resto', () => {
    expect(deselectPage(new Set(['r1', 'r2', 'other-page-id']), ['r1', 'r2'])).toEqual(new Set(['other-page-id']));
  });
});

describe('isPageFullySelected', () => {
  it('false para una pagina vacia', () => {
    expect(isPageFullySelected(new Set(['r1']), [])).toBe(false);
  });

  it('false cuando la seleccion es parcial', () => {
    expect(isPageFullySelected(new Set(['r1']), ['r1', 'r2'])).toBe(false);
  });

  it('true solo cuando todos los ids de la pagina estan seleccionados', () => {
    expect(isPageFullySelected(new Set(['r1', 'r2', 'other']), ['r1', 'r2'])).toBe(true);
  });
});
