import { useRef, useState } from 'react';
import type { ActaBlock, ActaFieldOption } from './types';

type Props = {
  blocks: ActaBlock[];
  fields: ActaFieldOption[];
  onReorder: (fromIndex: number, toIndex: number) => void;
  onUpdateBlock: (index: number, block: ActaBlock) => void;
  onRemoveBlock: (index: number) => void;
};

const BLOCK_LABELS: Record<ActaBlock['type'], string> = {
  logo: 'Logo',
  header: 'Encabezado',
  table: 'Tabla',
  signature: 'Firma',
};

export function ActaCanvas({ blocks, fields, onReorder, onUpdateBlock, onRemoveBlock }: Props) {
  const [draggedIndex, setDraggedIndex] = useState<number | null>(null);
  const [dropTarget, setDropTarget] = useState<number | null>(null);
  const textareaRefs = useRef<Record<number, HTMLTextAreaElement | null>>({});

  if (blocks.length === 0) {
    return (
      <section className="acta-canvas">
        <div className="acta-canvas-empty">
          <h3>Esta acta aun no tiene bloques</h3>
          <p>Haz clic en un bloque de la paleta para empezar.</p>
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
              title="Arrastra para cambiar el orden"
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
            <strong>{BLOCK_LABELS[block.type]}</strong>
            <button type="button" className="secondary" onClick={() => onRemoveBlock(index)}>Eliminar</button>
          </div>

          {block.type === 'logo' ? (
            <label>
              <span>Alineacion</span>
              <select value={block.alignment} onChange={(event) => onUpdateBlock(index, { ...block, alignment: event.target.value as 'left' | 'center' | 'right' })}>
                <option value="left">Izquierda</option>
                <option value="center">Centro</option>
                <option value="right">Derecha</option>
              </select>
            </label>
          ) : null}

          {block.type === 'header' ? (
            <div className="acta-header-config">
              <label>
                <span>Texto (puede usar {'{{campo}}'})</span>
                <textarea
                  ref={(element) => { textareaRefs.current[index] = element; }}
                  value={block.text}
                  onChange={(event) => onUpdateBlock(index, { ...block, text: event.target.value })}
                />
              </label>
              <label>
                <span>Tamaño</span>
                <select value={block.level} onChange={(event) => onUpdateBlock(index, { ...block, level: Number(event.target.value) as 1 | 2 | 3 })}>
                  <option value={1}>Titulo</option>
                  <option value={2}>Subtitulo</option>
                  <option value={3}>Texto destacado</option>
                </select>
              </label>
              {fields.length > 0 ? (
                <div className="acta-token-helper">
                  <span>Insertar campo:</span>
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
              {fields.length === 0 ? <p>Este formulario aun no tiene campos.</p> : null}
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
              <span>Etiqueta (ej. "Firma del coordinador")</span>
              <input value={block.label} onChange={(event) => onUpdateBlock(index, { ...block, label: event.target.value })} />
            </label>
          ) : null}
        </div>
      ))}
    </section>
  );
}
