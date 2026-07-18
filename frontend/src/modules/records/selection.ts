/** Seleccion multiple de registros para la generacion masiva de actas
 * (docs/96 item #5, docs/110). Funciones puras, separadas de RecordTable
 * para poder probarlas sin montar el componente (este repo no usa React
 * Testing Library, ver frontend/src/modules/acta/blockOrder.ts). */

export function toggleSelection(current: Set<string>, id: string): Set<string> {
  const next = new Set(current);
  if (next.has(id)) next.delete(id);
  else next.add(id);
  return next;
}

/** Agrega todos los ids de la pagina actual a la seleccion existente. */
export function selectPage(current: Set<string>, pageIds: string[]): Set<string> {
  return new Set([...current, ...pageIds]);
}

/** Quita todos los ids de la pagina actual de la seleccion existente. */
export function deselectPage(current: Set<string>, pageIds: string[]): Set<string> {
  const next = new Set(current);
  for (const id of pageIds) next.delete(id);
  return next;
}

export function isPageFullySelected(selected: Set<string>, pageIds: string[]): boolean {
  return pageIds.length > 0 && pageIds.every((id) => selected.has(id));
}
