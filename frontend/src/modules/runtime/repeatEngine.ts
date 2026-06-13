/**
 * Proyecto: InfoMatt360
 * Modulo: Repeat Engine
 * Responsabilidad: Mantener grupos repetidos consistentes cuando cambia la cantidad esperada.
 */

export type RepeatItem = {
  id: string;
  index: number;
  values: Record<string, unknown>;
};

function makeRepeatId(repeatName: string, index: number): string {
  return `${repeatName}_${index + 1}`;
}

export function reconcileRepeatItems(repeatName: string, currentItems: RepeatItem[], expectedCount: number): RepeatItem[] {
  const safeCount = Math.max(0, expectedCount);
  const nextItems = currentItems.slice(0, safeCount);

  while (nextItems.length < safeCount) {
    const index = nextItems.length;
    nextItems.push({ id: makeRepeatId(repeatName, index), index, values: {} });
  }

  return nextItems.map((item, index) => ({ ...item, index }));
}
