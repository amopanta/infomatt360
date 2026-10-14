import type { ActaBlock } from './types';
import { useI18n } from '../../i18n';

function paletteItems(t: (key: string) => string): Array<{ type: ActaBlock['type']; label: string; description: string; makeBlock: () => ActaBlock }> {
  return [
    { type: 'logo', label: t('acta.blockLogo'), description: t('acta.logoDescription'), makeBlock: () => ({ type: 'logo', alignment: 'left' }) },
    { type: 'header', label: t('acta.blockHeader'), description: t('acta.headerDescription'), makeBlock: () => ({ type: 'header', text: '', level: 1 }) },
    { type: 'table', label: t('acta.blockTable'), description: t('acta.tableDescription'), makeBlock: () => ({ type: 'table', field_names: [] }) },
    { type: 'signature', label: t('acta.blockSignature'), description: t('acta.signatureDescription'), makeBlock: () => ({ type: 'signature', label: '' }) },
  ];
}

export function ActaPalette({ onAddBlock }: { onAddBlock: (block: ActaBlock) => void }) {
  const { t } = useI18n();
  const items = paletteItems(t);
  return (
    <aside className="acta-palette">
      <h3>{t('acta.availableBlocks')}</h3>
      <p className="builder-help">{t('acta.paletteHelp')}</p>
      {items.map((item) => (
        <button key={item.type} type="button" className="acta-palette-item" onClick={() => onAddBlock(item.makeBlock())}>
          <strong>{item.label}</strong>
          <span>{item.description}</span>
        </button>
      ))}
    </aside>
  );
}
