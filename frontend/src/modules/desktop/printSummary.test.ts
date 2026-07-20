import { describe, expect, it } from 'vitest';
import { formatBatchPrintMessage } from './printSummary';

describe('formatBatchPrintMessage', () => {
  it('sin fallas, mensaje simple de conteo', () => {
    expect(formatBatchPrintMessage({ printed: 3, failed: 0, errors: [] })).toBe('3 acta(s) impresa(s).');
  });

  it('con fallas parciales, reporta ambos conteos', () => {
    expect(formatBatchPrintMessage({ printed: 2, failed: 1, errors: [{ name: 'x.pdf', reason: 'offline' }] })).toBe('2 impresas, 1 fallaron.');
  });

  it('lote vacío', () => {
    expect(formatBatchPrintMessage({ printed: 0, failed: 0, errors: [] })).toBe('0 acta(s) impresa(s).');
  });
});
