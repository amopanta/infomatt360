import type { RuntimeSection } from './types';

type Props = {
  sections: RuntimeSection[];
  activeSectionIndex: number;
  onSelect: (index: number) => void;
};

export function RuntimeSectionNavigator({ sections, activeSectionIndex, onSelect }: Props) {
  return (
    <nav className="runtime-section-nav" aria-label="Secciones de la pagina">
      {sections.map((section, index) => (
        <button key={section.id} className={index === activeSectionIndex ? 'active' : ''} onClick={() => onSelect(index)}>
          {section.title}
        </button>
      ))}
    </nav>
  );
}
