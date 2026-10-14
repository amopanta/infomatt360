import type { RuntimePage } from './types';
import { useI18n } from '../../i18n';

type Props = {
  pages: RuntimePage[];
  activePageIndex: number;
  onSelect: (index: number) => void;
};

export function RuntimeStepper({ pages, activePageIndex, onSelect }: Props) {
  const { t } = useI18n();
  return (
    <nav className="runtime-stepper" aria-label={t('runtime.formPages')}>
      {pages.map((page, index) => (
        <button key={page.id} className={index === activePageIndex ? 'active' : ''} onClick={() => onSelect(index)}>
          {index + 1}. {page.title}
        </button>
      ))}
    </nav>
  );
}
