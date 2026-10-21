/**
 * Proyecto: InfoMatt360
 * Modulo: Repeat Engine
 * Responsabilidad: Mantener grupos repetidos consistentes cuando cambia la cantidad esperada.
 */

import type { RepeatItem, RuntimeComponent } from './types';

/** Campo de un grupo repetible tal como lo guarda el importador/constructor
 * en `config.fields` (ver backend xlsform_import_service). */
export type RepeatFieldDefinition = {
  name: string;
  label?: string;
  component_type?: string;
  config?: Record<string, unknown>;
};

/** Convierte los campos del grupo en componentes que RuntimeField sabe
 * pintar. El id incluye el grupo para que dos filas no compartan ids. */
export function repeatFieldComponents(repeatName: string, fields: unknown): RuntimeComponent[] {
  if (!Array.isArray(fields)) return [];
  return (fields as RepeatFieldDefinition[])
    .filter((field) => field && typeof field.name === 'string' && field.name)
    .map((field) => ({
      id: `${repeatName}.${field.name}`,
      type: String(field.component_type || 'TEXT'),
      name: field.name,
      label: field.label || field.name,
      config_json: JSON.stringify(field.config ?? {}),
    }));
}

/** Agrega una fila vacía con id estable y único dentro del grupo. */
export function addRepeatItem(repeatName: string, items: RepeatItem[]): RepeatItem[] {
  const used = new Set(items.map((item) => item.id));
  let next = items.length;
  let id = makeRepeatId(repeatName, next);
  while (used.has(id)) { next += 1; id = makeRepeatId(repeatName, next); }
  return [...items, { id, index: items.length, values: {} }];
}

export function removeRepeatItem(items: RepeatItem[], id: string): RepeatItem[] {
  return items.filter((item) => item.id !== id).map((item, index) => ({ ...item, index }));
}

export function updateRepeatItem(items: RepeatItem[], id: string, fieldName: string, value: unknown): RepeatItem[] {
  return items.map((item) => item.id === id ? { ...item, values: { ...item.values, [fieldName]: value } } : item);
}

function makeRepeatId(repeatName: string, index: number): string {
  return `${repeatName}_${index + 1}`;
}

export function normalizeRepeatCount(expectedCount: number): number {
  if (!Number.isFinite(expectedCount)) return 0;
  return Math.max(0, Math.floor(expectedCount));
}

export function reconcileRepeatItems(repeatName: string, currentItems: RepeatItem[], expectedCount: number): RepeatItem[] {
  const safeCount = normalizeRepeatCount(expectedCount);
  const nextItems = currentItems.slice(0, safeCount);
  const usedIds = new Set(nextItems.map((item) => item.id));

  while (nextItems.length < safeCount) {
    const index = nextItems.length;
    const baseId = makeRepeatId(repeatName, index);
    let id = baseId;
    let suffix = 2;
    while (usedIds.has(id)) {
      id = `${baseId}_${suffix}`;
      suffix += 1;
    }
    usedIds.add(id);
    nextItems.push({ id, index, values: {} });
  }

  return nextItems.map((item, index) => ({ ...item, index }));
}

export function repeatItemsEqual(left: RepeatItem[], right: RepeatItem[]): boolean {
  return left.length === right.length && left.every((item, index) => (
    item.id === right[index].id
    && item.index === right[index].index
    && item.values === right[index].values
  ));
}
