import { describe, expect, it } from 'vitest';

import { pointerToCanvasPoint } from './signatureEngine';

describe('pointerToCanvasPoint', () => {
  it('convierte coordenadas visuales a pixeles internos del lienzo', () => {
    expect(pointerToCanvasPoint(60, 45, { left: 10, top: 20, width: 100, height: 50 }, 200, 100)).toEqual({ x: 100, y: 50 });
  });

  it('limita puntos fuera del lienzo y tolera dimensiones vacias', () => {
    expect(pointerToCanvasPoint(-10, 200, { left: 0, top: 0, width: 100, height: 100 }, 300, 150)).toEqual({ x: 0, y: 150 });
    expect(pointerToCanvasPoint(10, 10, { left: 0, top: 0, width: 0, height: 0 }, 300, 150)).toEqual({ x: 0, y: 0 });
  });
});

