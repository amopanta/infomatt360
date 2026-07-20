import type { DesktopBatchPrintResult } from './desktopBridge';

/** Mensaje de resultado tras imprimir un lote (docs/96 item #10), mismo
 * espíritu que el mensaje "Lote de actas generado." de BulkActaBar pero
 * reportando éxitos/fallas por ítem, como manifest.csv en el servidor. */
export function formatBatchPrintMessage(result: DesktopBatchPrintResult): string {
  if (result.failed === 0) return `${result.printed} acta(s) impresa(s).`;
  return `${result.printed} impresas, ${result.failed} fallaron.`;
}
