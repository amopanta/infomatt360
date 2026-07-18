import { describe, expect, it } from 'vitest';
import { extractTokens, reorderBlocks } from './blockOrder';
import type { ActaBlock } from './types';

function sampleBlocks(): ActaBlock[] {
  return [
    { type: 'logo', alignment: 'center' },
    { type: 'header', text: 'Titulo', level: 1 },
    { type: 'table', field_names: ['nombre'] },
  ];
}

describe('reorderBlocks', () => {
  it('mueve un bloque de indice 0 a 2 conservando el resto en orden', () => {
    const result = reorderBlocks(sampleBlocks(), 0, 2);
    expect(result.map((block) => block.type)).toEqual(['header', 'table', 'logo']);
  });

  it('mueve un bloque de indice 2 a 0 conservando el resto en orden', () => {
    const result = reorderBlocks(sampleBlocks(), 2, 0);
    expect(result.map((block) => block.type)).toEqual(['table', 'logo', 'header']);
  });

  it('con un solo bloque no hace nada', () => {
    const single: ActaBlock[] = [{ type: 'signature', label: 'Firma' }];
    expect(reorderBlocks(single, 0, 0)).toBe(single);
  });

  it('con indices iguales es un no-op', () => {
    const blocks = sampleBlocks();
    expect(reorderBlocks(blocks, 1, 1)).toBe(blocks);
  });

  it('con un indice fuera de rango es un no-op', () => {
    const blocks = sampleBlocks();
    expect(reorderBlocks(blocks, 0, 10)).toBe(blocks);
  });
});

describe('extractTokens', () => {
  it('extrae los nombres de campo de un texto con varios tokens', () => {
    expect(extractTokens('Hogar: {{nombre}}, fecha {{fecha}}')).toEqual(['nombre', 'fecha']);
  });

  it('devuelve una lista vacia sin tokens', () => {
    expect(extractTokens('Texto sin marcadores')).toEqual([]);
  });

  it('ignora llaves vacias o mal formadas', () => {
    expect(extractTokens('{{}} y { nombre } no son tokens validos')).toEqual([]);
  });
});
