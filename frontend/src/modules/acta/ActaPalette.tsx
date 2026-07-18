import type { ActaBlock } from './types';

const PALETTE_ITEMS: Array<{ type: ActaBlock['type']; label: string; description: string; makeBlock: () => ActaBlock }> = [
  { type: 'logo', label: 'Logo', description: 'Logo de la organizacion (automatico).', makeBlock: () => ({ type: 'logo', alignment: 'left' }) },
  { type: 'header', label: 'Encabezado', description: 'Titulo, puede usar {{campo}}.', makeBlock: () => ({ type: 'header', text: '', level: 1 }) },
  { type: 'table', label: 'Tabla', description: 'Campos del registro en formato campo/valor.', makeBlock: () => ({ type: 'table', field_names: [] }) },
  { type: 'signature', label: 'Firma', description: 'Linea + etiqueta para firma fisica.', makeBlock: () => ({ type: 'signature', label: '' }) },
];

export function ActaPalette({ onAddBlock }: { onAddBlock: (block: ActaBlock) => void }) {
  return (
    <aside className="acta-palette">
      <h3>Bloques disponibles</h3>
      <p className="builder-help">Haz clic en un bloque para agregarlo al final del acta.</p>
      {PALETTE_ITEMS.map((item) => (
        <button key={item.type} type="button" className="acta-palette-item" onClick={() => onAddBlock(item.makeBlock())}>
          <strong>{item.label}</strong>
          <span>{item.description}</span>
        </button>
      ))}
    </aside>
  );
}
