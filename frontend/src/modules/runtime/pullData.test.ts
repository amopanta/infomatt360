import { describe, expect, it } from 'vitest';
import { evaluateXlsExpression } from './xlsExpression';
import { findPullRequests, pullKey } from './pullData';
import { resolveFormValues } from './formLogic';
import type { RuntimeTemplate } from './types';

const template: RuntimeTemplate = {
  template_id: 'form', name: 'Visita', status: 'published', pages: [{ id: 'page', title: 'Página', sections: [{ id: 'section', title: 'Datos', rows: [{ id: 'row', columns: [{ id: 'column', desktop_width: 12, tablet_width: 12, mobile_width: 12, components: [
    { id: 'key', name: 'codigo', label: 'Código', type: 'TEXT' },
    { id: 'name', name: 'nombre', label: 'Nombre', type: 'CALCULATE', config_json: JSON.stringify({ calculation: "pulldata('familias', 'nombre', 'codigo', ${codigo})" }) },
  ] }] }] }] }],
};

describe('KoBo pulldata', () => {
  it('detects the CSV lookup and calculates from the returned value', () => {
    const values = { codigo: '001' };
    const request = findPullRequests(template, values)[0];
    expect(request).toEqual({ file: 'familias', column: 'nombre', key_column: 'codigo', key: '001' });
    const pulls = { [pullKey(request)]: 'Ana' };
    expect(evaluateXlsExpression("pulldata('familias', 'nombre', 'codigo', ${codigo})", values, {}, null, pulls)).toBe('Ana');
    expect(resolveFormValues(template, values, pulls).nombre).toBe('Ana');
    expect(findPullRequests(template, { codigo: '' })).toEqual([]);
  });
});
