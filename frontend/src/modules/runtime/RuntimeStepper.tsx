import type { RuntimePage } from './types';

type Props = {
  pages: RuntimePage[];
  activePageIndex: number;
  onSelect: (index: number) => void;
};

export function RuntimeStepper({ pages, activePageIndex, onSelect }: Props) {
  return (
    <nav className="runtime-stepper" aria-label="Paginas del formulario">
      {pages.map((page, index) => (
        <button key={page.id} className={index === activePageIndex ? 'active' : ''} onClick={() => onSelect(index)}>
          {index + 1}. {page.title}
        </button>
      ))}
    </nav>
  );
}
