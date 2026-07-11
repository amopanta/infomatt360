import type { BuilderPaletteItem } from './types';
import { FIELD_CATALOG } from './fieldCatalog';

const categories = Array.from(new Set(FIELD_CATALOG.map((item) => item.category)));

export function BuilderPalette({ onAddField }: { onAddField?: (item: BuilderPaletteItem) => void }) {
  return (
    <aside className="builder-palette">
      <h3>Banco de preguntas</h3>
      <p className="builder-help">Tipo KoboToolbox: elige un componente y se agrega al grupo activo.</p>
      {categories.map((category) => (
        <section key={category} className="builder-palette-group">
          <h4>{category}</h4>
          {FIELD_CATALOG.filter((item: BuilderPaletteItem) => item.category === category).map((item) => (
            <button key={item.type} type="button" className="builder-palette-item" data-field-type={item.type} onClick={() => onAddField?.(item)}>
              <strong>{item.label}</strong>
              <span>{item.description}</span>
            </button>
          ))}
        </section>
      ))}
    </aside>
  );
}
