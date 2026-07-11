/**
 * Proyecto: InfoMatt360
 * Modulo: Virtual Window
 * Responsabilidad: Mostrar solo una ventana de elementos para listas largas en tablets de bajos recursos.
 */

export function getVirtualWindow<T>(items: T[], activeIndex: number, windowSize: number): { visibleItems: T[]; start: number; end: number } {
  const safeWindow = Math.max(1, windowSize);
  const half = Math.floor(safeWindow / 2);
  const safeActiveIndex = items.length === 0
    ? 0
    : Math.min(items.length - 1, Math.max(0, activeIndex));
  const desiredStart = Math.max(0, safeActiveIndex - half);
  const start = Math.max(0, Math.min(desiredStart, items.length - safeWindow));
  const end = Math.min(items.length, start + safeWindow);

  return {
    visibleItems: items.slice(start, end),
    start,
    end,
  };
}
