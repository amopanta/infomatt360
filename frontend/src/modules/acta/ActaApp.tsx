import { ActaBuilderApp } from './ActaBuilderApp';
import { ActaListApp } from './ActaListApp';

function actaIdFromPath(): string {
  const parts = window.location.pathname.split('/').filter(Boolean);
  return parts[0] === 'acta' ? parts[1] ?? '' : '';
}

export function ActaApp() {
  const id = actaIdFromPath();
  if (!id) return <ActaListApp />;
  if (id === 'new') return <ActaBuilderApp mode="create" />;
  return <ActaBuilderApp mode="edit" actaTemplateId={id} />;
}
