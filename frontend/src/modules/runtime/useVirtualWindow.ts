/**
 * Proyecto: InfoMatt360
 * Modulo: Virtual Window
 * Responsabilidad: Mostrar solo una ventana de elementos para listas largas en tablets de bajos recursos.
 */

export function getVirtualWindow<T>(items: T[], activeIndex: number, windowSize: number): { visibleItems: T[]; start: number; end: number } {
  const safeWindow = Math.max(1, windowSize);
  const half = Math.floor(safeWindow / 2);
  const start = Math.max(0, activeIndex - half);
  const end = Math.min(items.length, start + safeWindow);

  return {
    visibleItems: items.slice(start, end),
    start,
    end,
  };
}
