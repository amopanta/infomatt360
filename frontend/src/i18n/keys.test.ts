/**
 * Toda clave t('...') usada en el código debe existir en es.json y en.json.
 * Sin esta prueba, una pantalla muestra el identificador interno
 * (por ejemplo «admin.storage.s3Title») en vez del texto (docs/149).
 */
import { describe, expect, it } from 'vitest';
import en from './locales/en.json';
import es from './locales/es.json';

const sources = import.meta.glob(['../**/*.ts', '../**/*.tsx', '!../**/*.test.ts', '!../**/*.test.tsx'], { query: '?raw', import: 'default', eager: true }) as Record<string, string>;

function has(dictionary: unknown, key: string): boolean {
  let node: unknown = dictionary;
  for (const part of key.split('.')) {
    if (!node || typeof node !== 'object' || !(part in (node as Record<string, unknown>))) return false;
    node = (node as Record<string, unknown>)[part];
  }
  return typeof node === 'string';
}

describe('textos de la interfaz', () => {
  it('revisa el código fuente', () => {
    expect(Object.keys(sources).length).toBeGreaterThan(50);
  });

  it('cada clave usada existe en español e inglés', () => {
    const missing: string[] = [];
    for (const [file, code] of Object.entries(sources)) {
      for (const match of code.matchAll(/\bt\(\s*'([a-zA-Z0-9_.]+)'/g)) {
        const key = match[1];
        if (!key.includes('.')) continue;
        if (!has(es, key)) missing.push(`${key} (es) en ${file}`);
        if (!has(en, key)) missing.push(`${key} (en) en ${file}`);
      }
    }
    expect(missing).toEqual([]);
  });
});
