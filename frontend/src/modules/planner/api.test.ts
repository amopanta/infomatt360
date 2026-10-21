import { describe, expect, it } from 'vitest';
import { formatCompliance } from './api';
import { resolveAppRoute } from '../../routeConfig';

describe('planeador', () => {
  it('muestra «Sin meta» y no trunca el cumplimiento sobre 100 %', () => {
    expect(formatCompliance(null, 'Sin meta')).toBe('Sin meta');
    expect(formatCompliance(85, 'Sin meta')).toBe('85 %');
    expect(formatCompliance(91.67, 'Sin meta')).toBe('91,67 %');
    expect(formatCompliance(125, 'Sin meta')).toBe('125 %');
  });

  it('la ruta exige un permiso de captura, supervisión o planeación', () => {
    const route = resolveAppRoute('/planner');
    expect(route.key).toBe('planner');
    expect(route.permissions).toEqual(expect.arrayContaining(['planner.manage', 'records.write']));
  });
});
