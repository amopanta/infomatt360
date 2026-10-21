import { useEffect, useMemo, useRef } from 'react';
import { RuntimeField } from './RuntimeField';
import { addRepeatItem, reconcileRepeatItems, removeRepeatItem, repeatFieldComponents, repeatItemsEqual, updateRepeatItem } from './repeatEngine';
import type { RepeatItem, RuntimeFormValues } from './types';
import { useI18n } from '../../i18n';

type Props = {
  name: string;
  label: string;
  /** `config.fields` del componente REPEAT */
  fields: unknown;
  /** Cantidad fija de filas (de `count_field`/`count`); sin ella, la persona agrega y quita filas. */
  fixedCount: number | null;
  minRows?: number;
  maxRows?: number;
  items: RepeatItem[];
  onChange: (items: RepeatItem[]) => void;
  templateId: string;
  projectId: string;
  uploadsDisabled?: boolean;
};

/**
 * Grupo repetible: una tarjeta por fila con los campos del grupo. Cada fila
 * se pinta con RuntimeField, así que un REPEAT dentro de otro (repeat
 * anidado de XLSForm) funciona igual. El valor guardado es la lista de
 * filas `{id, index, values}`.
 */
export function RuntimeRepeat({ name, label, fields, fixedCount, minRows = 0, maxRows, items, onChange, templateId, projectId, uploadsDisabled }: Props) {
  const { t } = useI18n();
  const components = useMemo(() => repeatFieldComponents(name, fields), [name, fields]);
  const reconciled = useMemo(
    () => (fixedCount === null ? items : reconcileRepeatItems(name, items, fixedCount)),
    [name, items, fixedCount],
  );

  useEffect(() => {
    if (!repeatItemsEqual(reconciled, items)) onChange(reconciled);
  }, [items, onChange, reconciled]);

  // Cada cambio parte de la versión más reciente de las filas: si dos campos
  // (o un repeat anidado) cambian antes de que React vuelva a pintar, partir
  // de `reconciled` borraría el primer cambio.
  const latest = useRef(reconciled);
  latest.current = reconciled;
  const commit = (next: RepeatItem[]) => { latest.current = next; onChange(next); };

  const canAdd = fixedCount === null && (maxRows === undefined || reconciled.length < maxRows);
  const canRemove = fixedCount === null && reconciled.length > minRows;

  return (
    <section className="runtime-repeat" aria-label={label}>
      <header>{label}</header>
      {reconciled.length === 0 ? <small>{t('ux.runtime.noRows')}</small> : null}
      {reconciled.map((item) => (
        <article key={item.id} className="runtime-repeat-item">
          <div className="runtime-repeat-item-header">
            <strong>{t('ux.runtime.rowTitle', { label, index: item.index + 1 })}</strong>
            {canRemove ? (
              <button type="button" className="runtime-repeat-remove" onClick={() => commit(removeRepeatItem(latest.current, item.id))}>
                {t('ux.runtime.removeRow')}
              </button>
            ) : null}
          </div>
          {components.map((component) => (
            <RuntimeField
              key={`${item.id}.${component.name}`}
              component={{ ...component, id: `${item.id}.${component.name}` }}
              templateId={templateId}
              projectId={projectId}
              values={item.values as RuntimeFormValues}
              uploadsDisabled={uploadsDisabled}
              onChange={(fieldName, value) => commit(updateRepeatItem(latest.current, item.id, fieldName, value))}
            />
          ))}
        </article>
      ))}
      {fixedCount === null ? (
        <div className="runtime-repeat-controls">
          <button type="button" disabled={!canAdd} onClick={() => commit(addRepeatItem(name, latest.current))}>+ {t('ux.runtime.addRow')}</button>
          {maxRows !== undefined && !canAdd ? <small>{t('ux.runtime.maxRows', { max: maxRows })}</small> : null}
        </div>
      ) : null}
    </section>
  );
}
