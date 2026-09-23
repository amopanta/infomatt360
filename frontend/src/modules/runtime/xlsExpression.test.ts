import { describe, expect, it } from 'vitest';
import { evaluateXlsExpression } from './xlsExpression';
import { isFieldVisible, resolveFormValues, validateFormValues } from './formLogic';
import type { RuntimeTemplate } from './types';

describe('XLSForm expressions', () => {
  it('evaluates field dependencies, selected and calculations safely', () => {
    const values = { visita: 'si', municipio: 'Bogotá', ayudas: ['kit'], edad: 20 };
    expect(evaluateXlsExpression("${visita} = 'si' and ${edad} >= 18", values)).toBe(true);
    expect(evaluateXlsExpression("selected(${ayudas}, 'kit')", values)).toBe(true);
    expect(evaluateXlsExpression('(${edad} + 2) * 3', values)).toBe(66);
    expect(evaluateXlsExpression('municipio = ${municipio}', values, { municipio: 'Bogotá' })).toBe(true);
    expect(evaluateXlsExpression('municipio = ${municipio}', values, { municipio: 'Soacha' })).toBe(false);
  });

  it('applies defaults, calculations, relevance and constraint messages', () => {
    const template: RuntimeTemplate = { template_id: 'one', name: 'Prueba', status: 'draft', pages: [{ id: 'p', title: 'P', sections: [{ id: 's', title: 'S', rows: [{ id: 'r', columns: [{ id: 'c', desktop_width: 12, tablet_width: 12, mobile_width: 12, components: [
      { id: '1', type: 'TEXT', name: 'visita', label: 'Visita', config_json: JSON.stringify({ default: 'si' }) },
      { id: '2', type: 'NUMBER', name: 'edad', label: 'Edad', config_json: JSON.stringify({ required: true, required_message: 'Edad obligatoria', constraint_expression: '. >= 18', constraint_message: 'Debe ser mayor de edad' }) },
      { id: '3', type: 'NUMBER', name: 'doble', label: 'Doble', config_json: JSON.stringify({ calculation: '${edad} * 2', relevant_expression: "${visita} = 'si' and ${edad} >= 18" }) },
    ] }] }] }] }] };
    expect(resolveFormValues(template, {}).visita).toBe('si');
    expect(validateFormValues(template, {})).toBe('Edad obligatoria');
    expect(validateFormValues(template, { visita: 'si', edad: 16 })).toBe('Debe ser mayor de edad');
    const complete = resolveFormValues(template, { visita: 'si', edad: 20 });
    expect(complete.doble).toBe(40);
    expect(isFieldVisible(template.pages[0].sections[0].rows[0].columns[0].components[2], complete)).toBe(true);
    expect(validateFormValues(template, complete)).toBeNull();
  });
});
