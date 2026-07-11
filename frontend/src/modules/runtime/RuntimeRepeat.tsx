import { useEffect, useMemo, useState } from 'react';
import { detectDeviceProfile } from './deviceProfile';
import { reconcileRepeatItems, repeatItemsEqual } from './repeatEngine';
import type { RepeatItem } from './types';
import { getVirtualWindow } from './useVirtualWindow';

type Props = {
  name: string;
  label: string;
  count: number;
  items: RepeatItem[];
  onChange: (items: RepeatItem[]) => void;
};

export function RuntimeRepeat({ name, label, count, items, onChange }: Props) {
  const [activeIndex, setActiveIndex] = useState(0);
  const profile = useMemo(() => detectDeviceProfile(), []);
  const reconciledItems = useMemo(
    () => reconcileRepeatItems(name, items, count),
    [name, items, count],
  );
  const { visibleItems, start, end } = getVirtualWindow(reconciledItems, activeIndex, profile.repeatWindowSize);

  useEffect(() => {
    if (!repeatItemsEqual(reconciledItems, items)) onChange(reconciledItems);
  }, [items, onChange, reconciledItems]);

  useEffect(() => {
    setActiveIndex((current) => Math.max(0, Math.min(current, reconciledItems.length - 1)));
  }, [reconciledItems.length]);

  const visibleStart = reconciledItems.length === 0 ? 0 : start + 1;

  return (
    <section className="runtime-repeat">
      <header>{label}</header>
      <small>Modo {profile.mode}. Mostrando {visibleStart}-{end} de {reconciledItems.length}</small>
      <div className="runtime-repeat-controls">
        <button disabled={activeIndex === 0} onClick={() => setActiveIndex((current) => Math.max(0, current - 1))}>Anterior</button>
        <button disabled={activeIndex >= reconciledItems.length - 1} onClick={() => setActiveIndex((current) => Math.min(reconciledItems.length - 1, current + 1))}>Siguiente</button>
      </div>
      {visibleItems.map((item) => (
        <article key={item.id} className="runtime-repeat-item">
          <strong>Registro {item.index + 1}</strong>
        </article>
      ))}
    </section>
  );
}
