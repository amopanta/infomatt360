import type { ReportWidget } from './types';

/** Mueve un widget de `fromIndex` a `toIndex`, conservando el orden relativo
 * del resto -- usado por el arrastre de reordenamiento del constructor de
 * tableros (docs/96 item #6, docs/111). Identica a reorderBlocks del
 * constructor de actas (docs/109). */
export function reorderWidgets(widgets: ReportWidget[], fromIndex: number, toIndex: number): ReportWidget[] {
  if (fromIndex === toIndex || fromIndex < 0 || fromIndex >= widgets.length || toIndex < 0 || toIndex >= widgets.length) {
    return widgets;
  }
  const next = widgets.slice();
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}
