import { useRef, useState } from 'react';
import type { ActaBlock, ActaFieldOption } from './types';
import { useI18n } from '../../i18n';

type Props = {
  blocks: ActaBlock[];
  fields: ActaFieldOption[];
  onReorder: (fromIndex: number, toIndex: number) => void;
  onUpdateBlock: (index: number, block: ActaBlock) => void;
  onRemoveBlock: (index: number) => void;
};

function blockLabels(t: (key: string) => string): Record<ActaBlock['type'], string> {
  return {
    logo: t('acta.blockLogo'),
    header: t('acta.blockHeader'),
    table: t('acta.blockTable'),
    signature: t('acta.blockSignature'),
  };
}

export function ActaCanvas({ blocks, fields, onReorder, onUpdateBlock, onRemoveBlock }: Props) {
  const { t } = useI18n();
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<number | null>(null);
  const textareaRefs = useRef<Record<number, HTMLTextAreaElement | null>>({});
  const labels = blockLabels(t);

  if (blocks.length === 0) {
    return (
      <section className="acta-canvas">
        <div className="acta-canvas-empty">
          <h3>{t('acta.noBlocksYet')}</h3>
          <p>{t('acta.clickPaletteHint')}</p>
        </div>
      </section>
    );
  }

  function insertTokenAtCursor(index: number, fieldName: string) {
    const block = blocks[index];
    if (block.type !== 'header') return;
    const textarea = textareaRefs.current[index];
    const token = `{{${fieldName}}}`;
    if (!textarea) {
      onUpdateBlock(index, { ...block, text: `${block.text}${token}` });
      return;
    }
    const start = textarea.selectionStart ?? block.text.length;
    const end = textarea.selectionEnd ?? block.text.length;
    const nextText = `${block.text.slice(0, start)}${token}${block.text.slice(end)}`;
    onUpdateBlock(index, { ...block, text: nextText });
  }

  return (
    <section className="acta-canvas">
      {blocks.map((block, index) => (
        <div
          key={index}
          className={`acta-block-card ${dropTarget === index ? 'drag-target' : ''}`}
          onDragOver={(event) => {
            if (draggedIndex === null) return;
            event.preventDefault();
            setDropTarget(index);
          }}
          onDragLeave={() => setDropTarget(null)}
          onDrop={(event) => {
            event.preventDefault();
            if (draggedIndex !== null) onReorder(draggedIndex, index);
            setDraggedIndex(null);
            setDropTarget(null);
          }}
        >
          <div className="acta-block-header">
            <span
              className="builder-drag-handle"
              title={t('acta.dragToReorder')}
              draggable
              onDragStart={(event) => {
                event.dataTransfer.effectAllowed = 'move';
                event.dataTransfer.setData('text/plain', String(index));
                setDraggedIndex(index);
              }}
              onDragEnd={() => {
                setDraggedIndex(null);
                setDropTarget(null);
              }}
            >
              ⋮⋮
            </span>
            <strong>{labels[block.type]}</strong>
            <button type="button" className="secondary" onClick={() => onRemoveBlock(index)}>{t('acta.removeBlock')}</button>
          </div>

          {block.type === 'logo' ? (
            <label>
              <span>{t('acta.alignmentLabel')}</span>
              <select value={block.alignment} onChange={(event) => onUpdateBlock(index, { ...block, alignment: event.target.value as 'left' | 'center' | 'right' })}>
                <option value="left">{t('acta.alignLeft')}</option>
                <option value="center">{t('acta.alignCenter')}</option>
                <option value="right">{t('acta.alignRight')}</option>
              </select>
            </label>
          ) : null}

          {block.type === 'header' ? (
            <div className="acta-header-config">
              <label>
                <span>{t('acta.headerTextLabel')}</span>
                <textarea
                  ref={(element) => { textareaRefs.current[index] = element; }}
                  value={block.text}
                  onChange={(event) => onUpdateBlock(index, { ...block, text: event.target.value })}
                />
              </label>
              <label>
                <span>{t('acta.sizeLabel')}</span>
                <select value={block.level} onChange={(event) => onUpdateBlock(index, { ...block, level: Number(event.target.value) as 1 | 2 | 3 })}>
                  <option value={1}>{t('acta.sizeTitle')}</option>
                  <option value={2}>{t('acta.sizeSubtitle')}</option>
                  <option value={3}>{t('acta.sizeHighlight')}</option>
                </select>
              </label>
              {fields.length > 0 ? (
                <div className="acta-token-helper">
                  <span>{t('acta.insertField')}</span>
                  {fields.map((field) => (
                    <button key={field.name} type="button" className="secondary" onClick={() => insertTokenAtCursor(index, field.name)}>
                      {field.label}
                    </button>
                  ))}
                </div>
              ) : null}
            </div>
          ) : null}

          {block.type === 'table' ? (
            <div className="acta-table-config">
              {fields.length === 0 ? <p>{t('acta.noFieldsYet')}</p> : null}
              {fields.map((field) => {
                const checked = block.field_names.includes(field.name);
                return (
                  <label key={field.name} className="acta-field-checkbox">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={(event) => {
                        const nextFieldNames = event.target.checked
                          ? [...block.field_names, field.name]
                          : block.field_names.filter((name) => name !== field.name);
                        onUpdateBlock(index, { ...block, field_names: nextFieldNames });
                      }}
                    />
                    {field.label}
                  </label>
                );
              })}
            </div>
          ) : null}

          {block.type === 'signature' ? (
            <label>
              <span>{t('acta.signatureLabelHint')}</span>
              <input value={block.label} onChange={(event) => onUpdateBlock(index, { ...block, label: event.target.value })} />
            </label>
          ) : null}
        </div>
      ))}
    </section>
  );
}
