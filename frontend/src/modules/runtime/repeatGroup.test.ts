import { describe, expect, it } from 'vitest';
import { addRepeatItem, removeRepeatItem, repeatFieldComponents, updateRepeatItem } from './repeatEngine';
import { stampInterviewDuration, validateFormValues } from './formLogic';
import type { RepeatItem, RuntimeTemplate } from './types';

const integrantes = {
  fields: [
    { name: 'nombre', label: 'Nombre', component_type: 'TEXT', config: { required: true } },
    { name: 'edad', label: 'Edad', component_type: 'INTEGER', config: { constraint_expression: '. >= 0 and . <= 120' } },
    { name: 'contactos', label: 'Contactos', component_type: 'REPEAT', config: { fields: [
      { name: 'telefono', label: 'Teléfono', component_type: 'PHONE', config: { required: true } },
    ] } },
  ],
};

function template(): RuntimeTemplate {
  return {
    template_id: 't', name: 'Prueba', status: 'published',
    pages: [{ id: 'p', title: 'P', sections: [{ id: 's', title: 'S', rows: [{ id: 'r', columns: [{ id: 'c', desktop_width: 12, tablet_width: 12, mobile_width: 12, components: [
      { id: 'rep', type: 'REPEAT', name: 'integrantes', label: 'Integrantes', config_json: JSON.stringify(integrantes) },
      { id: 'dur', type: 'INTERVIEW_DURATION', name: 'duracion', label: 'Duración' },
    ] }] }] }] }],
  };
}

describe('grupo repetible', () => {
  it('convierte los campos del grupo en componentes, incluido el repeat anidado', () => {
    const components = repeatFieldComponents('integrantes', integrantes.fields);
    expect(components.map((c) => [c.name, c.type])).toEqual([['nombre', 'TEXT'], ['edad', 'INTEGER'], ['contactos', 'REPEAT']]);
    expect(JSON.parse(components[0].config_json!)).toEqual({ required: true });
  });

  it('agrega, actualiza y quita filas con ids únicos e índices consecutivos', () => {
    let rows: RepeatItem[] = [];
    rows = addRepeatItem('integrantes', rows);
    rows = addRepeatItem('integrantes', rows);
    expect(new Set(rows.map((r) => r.id)).size).toBe(2);
    rows = updateRepeatItem(rows, rows[1].id, 'nombre', 'Luis');
    expect(rows[1].values).toEqual({ nombre: 'Luis' });
    rows = removeRepeatItem(rows, rows[0].id);
    expect(rows.map((r) => [r.index, r.values.nombre])).toEqual([[0, 'Luis']]);
    rows = addRepeatItem('integrantes', rows);
    expect(new Set(rows.map((r) => r.id)).size).toBe(2);
  });

  it('valida obligatorios y reglas dentro de cada fila, también en el anidado', () => {
    const tpl = template();
    const row = (values: Record<string, unknown>, index = 0): RepeatItem => ({ id: `i${index}`, index, values });
    expect(validateFormValues(tpl, { integrantes: [row({ edad: 30 })] })).toBe('Completa «Nombre» en «Integrantes» (fila 1).');
    expect(validateFormValues(tpl, { integrantes: [row({ nombre: 'Ana', edad: 200 })] })).toBe('El valor de «Edad» en «Integrantes» (fila 1) no cumple la regla.');
    expect(validateFormValues(tpl, { integrantes: [row({ nombre: 'Ana', contactos: [row({}, 0)] })] })).toBe('Completa «Teléfono» en «Contactos» (fila 1).');
    expect(validateFormValues(tpl, { integrantes: [row({ nombre: 'Ana', edad: 30, contactos: [row({ telefono: '300' })] })] })).toBeNull();
  });

  it('registra la duración de la entrevista en segundos', () => {
    expect(stampInterviewDuration(template(), {}, 1_000, 91_400).duracion).toBe(90);
  });
});
