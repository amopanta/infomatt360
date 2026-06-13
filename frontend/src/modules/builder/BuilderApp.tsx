import { AppShell } from '../../components/AppShell';
import { BuilderCanvas } from './BuilderCanvas';
import { BuilderPalette } from './BuilderPalette';

export function BuilderApp() {
  return (
    <AppShell title="Constructor de Formularios">
      <div className="builder-layout">
        <BuilderPalette />
        <BuilderCanvas />
      </div>
    </AppShell>
  );
}
