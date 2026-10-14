import type { RuntimeSection } from './types';
import { useI18n } from '../../i18n';

type Props = {
  sections: RuntimeSection[];
  activeSectionIndex: number;
  onSelect: (index: number) => void;
};

export function RuntimeSectionNavigator({ sections, activeSectionIndex, onSelect }: Props) {
  const { t } = useI18n();
  return (
    <nav className="runtime-section-nav" aria-label={t('runtime.pageSections')}>
      {sections.map((section, index) => (
        <button key={section.id} className={index === activeSectionIndex ? 'active' : ''} onClick={() => onSelect(index)}>
          {section.title}
        </button>
      ))}
    </nav>
  );
}
