import { useEffect, useState } from 'react';
import type { PrinterInfo } from './desktopBridge';

/** Selector de impresora + copias reutilizado por GenerateActaPanel y
 * BulkActaBar (docs/96 item #10). Solo se monta cuando isDesktopApp() es
 * true -- window.desktopBridge!.listPrinters() está garantizado ahí. */
export function PrinterPicker({
  printerName,
  onPrinterNameChange,
  copies,
  onCopiesChange,
}: {
  printerName: string;
  onPrinterNameChange: (value: string) => void;
  copies: number;
  onCopiesChange: (value: number) => void;
}) {
  const [printers, setPrinters] = useState<PrinterInfo[]>([]);

  useEffect(() => {
    window.desktopBridge!
      .listPrinters()
      .then((rows) => {
        setPrinters(rows);
        const preferred = rows.find((printer) => printer.isDefault) ?? rows[0];
        if (preferred && !printerName) onPrinterNameChange(preferred.name);
      })
      .catch(() => setPrinters([]));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <span className="printer-picker">
      <select value={printerName} onChange={(event) => onPrinterNameChange(event.target.value)} disabled={printers.length === 0}>
        {printers.length === 0 && <option value="">Sin impresoras detectadas</option>}
        {printers.map((printer) => (
          <option key={printer.name} value={printer.name}>
            {printer.displayName}
            {printer.isDefault ? ' (predeterminada)' : ''}
          </option>
        ))}
      </select>
      <input type="number" min={1} max={99} value={copies} onChange={(event) => onCopiesChange(Math.max(1, Number(event.target.value) || 1))} />
    </span>
  );
}
