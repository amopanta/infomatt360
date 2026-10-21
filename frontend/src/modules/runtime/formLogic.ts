import { parseFieldConfig } from './fieldConfig';
import { evaluateXlsExpression } from './xlsExpression';
import { repeatFieldComponents } from './repeatEngine';
import type { RepeatItem, RuntimeComponent, RuntimeFormValue, RuntimeFormValues, RuntimeTemplate } from './types';

export function allComponents(template: RuntimeTemplate): RuntimeComponent[] {
  return template.pages.flatMap((page) => page.sections.flatMap((section) => section.rows.flatMap((row) => row.columns.flatMap((column) => column.components))));
}

export function isFieldVisible(component: RuntimeComponent, values: RuntimeFormValues): boolean {
  const config = parseFieldConfig(component.config_json);
  if (config.relevant_expression) {
    try { return Boolean(evaluateXlsExpression(config.relevant_expression, values)); }
    catch { /* Older native rule can still be evaluated. */ }
  }
  const relevant = config.relevant;
  if (!relevant?.field) return true;
  const source = values[relevant.field];
  const sourceText = Array.isArray(source) ? source.map(String).join(',') : String(source ?? '');
  switch (relevant.operator) {
    case 'not_equals': return sourceText !== (relevant.value ?? '');
    case 'not_empty': return sourceText !== '';
    case 'empty': return sourceText === '';
    default: return sourceText === (relevant.value ?? '');
  }
}

function scalar(value: unknown): value is RuntimeFormValue {
  return value === null || ['string', 'number', 'boolean'].includes(typeof value);
}

export function resolveFormValues(template: RuntimeTemplate, input: RuntimeFormValues, pulls: Record<string, string> = {}): RuntimeFormValues {
  const values = { ...input };
  const components = allComponents(template);
  for (const component of components) {
    const config = parseFieldConfig(component.config_json);
    if (values[component.name] !== undefined || config.default === undefined || config.default === '') continue;
    let value: unknown = config.default;
    if (typeof value === 'string' && (value.includes('${') || /^(?:today|now|true|false)\(/.test(value))) {
      try { value = evaluateXlsExpression(value, values, {}, null, pulls); } catch { continue; }
    }
    if (typeof value === 'string' && ['NUMBER', 'INTEGER', 'DECIMAL', 'CURRENCY', 'PERCENTAGE'].includes(component.type.toUpperCase()) && Number.isFinite(Number(value))) value = Number(value);
    if (scalar(value)) values[component.name] = value;
  }
  for (let pass = 0; pass < Math.min(components.length, 5); pass += 1) {
    let changed = false;
    for (const component of components) {
      const calculation = parseFieldConfig(component.config_json).calculation;
      if (!calculation) continue;
      try {
        const result = evaluateXlsExpression(calculation, values, {}, null, pulls);
        if (scalar(result) && values[component.name] !== result) { values[component.name] = result; changed = true; }
      } catch { /* Preview warns about expressions outside the supported subset. */ }
    }
    if (!changed) break;
  }
  return values;
}

/** Segundos entre la apertura del formulario y el envío, en cada campo
 * INTERVIEW_DURATION (el servidor no puede saber cuándo empezó la captura). */
export function stampInterviewDuration(template: RuntimeTemplate, values: RuntimeFormValues, startedAt: number, now = Date.now()): RuntimeFormValues {
  const durationFields = allComponents(template).filter((component) => component.type.toUpperCase() === 'INTERVIEW_DURATION');
  if (!durationFields.length) return values;
  const seconds = Math.max(0, Math.round((now - startedAt) / 1000));
  const next = { ...values };
  for (const component of durationFields) next[component.name] = seconds;
  return next;
}

export function validateFormValues(template: RuntimeTemplate, values: RuntimeFormValues): string | null {
  return validateComponents(allComponents(template), values, '');
}

function isEmpty(value: unknown): boolean {
  return value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0);
}

/** `where` describe la fila de un grupo repetible (" en «Integrantes» (fila 2)")
 * para que el mensaje diga exactamente dónde está el dato que falta. */
function validateComponents(components: RuntimeComponent[], values: RuntimeFormValues, where: string): string | null {
  for (const component of components) {
    if (!isFieldVisible(component, values)) continue;
    const config = parseFieldConfig(component.config_json);
    const value = values[component.name];
    const empty = isEmpty(value);
    if (config.required && empty) return config.required_message || `Completa «${component.label}»${where}.`;
    if (!empty && config.constraint_expression) {
      try { if (!evaluateXlsExpression(config.constraint_expression, values, {}, value)) return config.constraint_message || `El valor de «${component.label}»${where} no cumple la regla.`; }
      catch { /* Native min/max/pattern validation still applies. */ }
    }
    if (component.type.toUpperCase() === 'REPEAT' && Array.isArray(value)) {
      const children = repeatFieldComponents(component.name, (config as Record<string, unknown>).fields);
      for (const item of value as RepeatItem[]) {
        const rowError = validateComponents(children, (item.values ?? {}) as RuntimeFormValues, ` en «${component.label}» (fila ${item.index + 1})`);
        if (rowError) return rowError;
      }
    }
  }
  return null;
}
