import type { ActaBlock } from './types';

/** Mueve un bloque de `fromIndex` a `toIndex`, conservando el orden relativo
 * del resto -- usado por el arrastre de reordenamiento de ActaCanvas. */
export function reorderBlocks(blocks: ActaBlock[], fromIndex: number, toIndex: number): ActaBlock[] {
  if (fromIndex === toIndex || fromIndex < 0 || fromIndex >= blocks.length || toIndex < 0 || toIndex >= blocks.length) {
    return blocks;
  }
  const next = blocks.slice();
  const [moved] = next.splice(fromIndex, 1);
  next.splice(toIndex, 0, moved);
  return next;
}

const TOKEN_PATTERN = /\{\{\s*(\w+)\s*\}\}/g;

/** Extrae los nombres de campo referenciados como `{{campo}}` en un texto de
 * encabezado -- usado para validar/resaltar tokens conocidos en la UI. */
export function extractTokens(text: string): string[] {
  const tokens: string[] = [];
  for (const match of text.matchAll(TOKEN_PATTERN)) {
    tokens.push(match[1]);
  }
  return tokens;
}
