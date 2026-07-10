import { describe, expect, it } from 'vitest';

import { normalizeOptions, parseFieldConfig, parseNumberInput } from './fieldConfig';

describe('fieldConfig', () => {
  it('tolera configuraciones vacias o invalidas', () => {
    expect(parseFieldConfig()).toEqual({});
    expect(parseFieldConfig('{invalido')).toEqual({});
    expect(parseFieldConfig('["A"]')).toEqual({});
  });

  it('normaliza opciones simples y opciones con etiqueta', () => {
    expect(normalizeOptions({ options: ['Activo', 2, { label: 'Bogota', value: 'BOG' }] })).toEqual([
      { label: 'Activo', value: 'Activo' },
      { label: '2', value: '2' },
      { label: 'Bogota', value: 'BOG' },
    ]);
  });

  it('acepta choices y nombres alternativos usados por fuentes externas', () => {
    expect(normalizeOptions({ choices: [{ name: 'Medellin', id: 5 }, { text: 'Cali', code: 'CLO' }] })).toEqual([
      { label: 'Medellin', value: '5' },
      { label: 'Cali', value: 'CLO' },
    ]);
  });

  it('convierte numeros sin guardar cadenas vacias o valores no finitos', () => {
    expect(parseNumberInput('12.5')).toBe(12.5);
    expect(parseNumberInput('')).toBeNull();
    expect(parseNumberInput('no-es-numero')).toBeNull();
  });
});

