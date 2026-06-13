import { reconcileRepeatItems, type RepeatItem } from './repeatEngine';

type Props = {
  name: string;
  label: string;
  count: number;
  items: RepeatItem[];
  onChange: (items: RepeatItem[]) => void;
};

export function RuntimeRepeat({ name, label, count, items, onChange }: Props) {
  const reconciledItems = reconcileRepeatItems(name, items, count);

  if (reconciledItems.length !== items.length) {
    onChange(reconciledItems);
  }

  return (
    <section className="runtime-repeat">
      <header>{label}</header>
      {reconciledItems.map((item) => (
        <article key={item.id} className="runtime-repeat-item">
          <strong>Registro {item.index + 1}</strong>
        </article>
      ))}
    </section>
  );
}
