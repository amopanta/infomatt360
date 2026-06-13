import type { BuilderPaletteItem } from './types';

const items: BuilderPaletteItem[] = [
  { type: 'TEXT', label: 'Texto', description: 'Campo de texto simple' },
  { type: 'NUMBER', label: 'Numero', description: 'Campo numerico' },
  { type: 'DATE', label: 'Fecha', description: 'Selector de fecha' },
  { type: 'TEXTAREA', label: 'Area de texto', description: 'Respuesta larga' },
  { type: 'GPS', label: 'Ubicacion GPS', description: 'Coordenadas' },
  { type: 'SIGNATURE', label: 'Firma', description: 'Firma digital' },
];

export function BuilderPalette() {
  return (
    <aside className="builder-palette">
      <h3>Componentes</h3>
      {items.map((item) => (
        <button key={item.type} className="builder-palette-item">
          <strong>{item.label}</strong>
          <span>{item.description}</span>
        </button>
      ))}
    </aside>
  );
}
