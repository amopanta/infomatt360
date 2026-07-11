/**
 * Proyecto: InfoMatt360
 * Modulo: Repeat Engine
 * Responsabilidad: Mantener grupos repetidos consistentes cuando cambia la cantidad esperada.
 */

import type { RepeatItem } from './types';

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
