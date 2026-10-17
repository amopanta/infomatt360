import { describe, expect, it } from 'vitest';
import { AUTOMATIC_TYPES, FIELD_CATALOG, fieldTypeInfo } from './fieldCatalog';

describe('fieldCatalog', () => {
  it('no repite tipos y todos tienen icono, nombre y descripción', () => {
    const types = FIELD_CATALOG.map((item) => item.type);
    expect(new Set(types).size).toBe(types.length);
    for (const item of FIELD_CATALOG) {
      expect(item.icon).toBeTruthy();
      expect(item.label.trim()).not.toBe('');
      expect(item.description.trim()).not.toBe('');
    }
  });

  it('mantiene una lista corta de preguntas básicas', () => {
    const basic = FIELD_CATALOG.filter((item) => item.basic);
    expect(basic.length).toBeGreaterThanOrEqual(10);
    expect(basic.length).toBeLessThanOrEqual(16);
    expect(basic.some((item) => AUTOMATIC_TYPES.has(item.type))).toBe(false);
  });

  it('traduce el código interno a un nombre legible', () => {
    expect(fieldTypeInfo('MULTISELECT').label).toBe('Elegir varias opciones');
    expect(fieldTypeInfo('TIPO_DESCONOCIDO').label).toBe('TIPO_DESCONOCIDO');
    expect(AUTOMATIC_TYPES.has('UUID')).toBe(true);
    expect(AUTOMATIC_TYPES.has('TEXT')).toBe(false);
  });
});
