import { useState } from 'react';
import type { BuilderPaletteItem } from './types';
import { FIELD_CATALOG, fieldLineIcon } from './fieldCatalog';
import { Icon } from '../../components/Icon';
import { useI18n } from '../../i18n';

const BASIC = FIELD_CATALOG.filter((item) => item.basic);
const MORE = FIELD_CATALOG.filter((item) => !item.basic);
const MORE_CATEGORIES = Array.from(new Set(MORE.map((item) => item.category)));

function normalize(value: string) {
  return value.toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '');
}

/** Paleta en dos niveles: las preguntas más usadas siempre visibles y el resto
 * plegado por categoría; el buscador filtra ambas por nombre o descripción. */
export function BuilderPalette({ onAddField }: { onAddField?: (item: BuilderPaletteItem) => void }) {
  const { t } = useI18n();
  const [query, setQuery] = useState('');
  const q = normalize(query.trim());
  const matches = q ? FIELD_CATALOG.filter((item) => normalize(`${item.label} ${item.description} ${item.category}`).includes(q)) : [];

  function renderItem(item: BuilderPaletteItem) {
    return (
      <button key={item.type} type="button" className="builder-palette-item" data-field-type={item.type} onClick={() => onAddField?.(item)}>
        <span className="builder-palette-icon" aria-hidden="true"><Icon name={fieldLineIcon(item.type)} /></span>
        <span className="builder-palette-text">
          <strong>{item.label}</strong>
          <span>{item.description}</span>
        </span>
      </button>
    );
  }

  return (
    <aside className="builder-palette">
      <h3>{t('builder.palette.title')}</h3>
      <p className="builder-help">{t('builder.palette.help')}</p>
      <input
        type="search"
        className="builder-palette-search"
        value={query}
        placeholder={t('ux.builder.searchFields')}
        aria-label={t('ux.builder.searchFields')}
        onChange={(event) => setQuery(event.target.value)}
      />
      {q ? (
        <section className="builder-palette-group">
          {matches.length ? matches.map(renderItem) : <p className="builder-help">{t('ux.builder.noFieldMatch')}</p>}
        </section>
      ) : (
        <>
          <section className="builder-palette-group">
            <h4>{t('ux.builder.basicFields')}</h4>
            {BASIC.map(renderItem)}
          </section>
          <details className="builder-palette-more">
            <summary>{t('ux.builder.moreFields')} ({MORE.length})</summary>
            {MORE_CATEGORIES.map((category) => (
              <section key={category} className="builder-palette-group">
                <h4>{category}</h4>
                {MORE.filter((item) => item.category === category).map(renderItem)}
              </section>
            ))}
          </details>
        </>
      )}
    </aside>
  );
}
