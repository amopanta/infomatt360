import { describe, expect, it } from 'vitest';

import { buildGeometry, editableCoordinates, geometryViewport, isValidCoordinate, projectCoordinate, unprojectCoordinate } from './geoEngine';

describe('geoEngine', () => {
  it('valida rangos geograficos', () => {
    expect(isValidCoordinate(-74.07, 4.71)).toBe(true);
    expect(isValidCoordinate(181, 4.71)).toBe(false);
    expect(isValidCoordinate(-74.07, -91)).toBe(false);
  });

  it('cierra poligonos sin duplicar el punto durante edicion', () => {
    const polygon = buildGeometry('GEOSHAPE', [[-74, 4], [-73, 4], [-73, 5]]);
    expect(polygon).toEqual({ type: 'Polygon', coordinates: [[[-74, 4], [-73, 4], [-73, 5], [-74, 4]]] });
    expect(editableCoordinates(polygon)).toEqual([[-74, 4], [-73, 4], [-73, 5]]);
  });

  it('proyecta y recupera coordenadas dentro del visor', () => {
    const viewport = geometryViewport([[-74.1, 4.6], [-73.9, 4.8]]);
    const projected = projectCoordinate([-74, 4.7], viewport, 640, 260);
    const restored = unprojectCoordinate(projected[0], projected[1], viewport, 640, 260);
    expect(restored[0]).toBeCloseTo(-74);
    expect(restored[1]).toBeCloseTo(4.7);
  });
});
