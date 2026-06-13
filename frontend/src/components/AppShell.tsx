import { BrandLogo } from './BrandLogo';

const menu = ['Dashboard', 'Formularios', 'Registros', 'Reportes', 'Mapas', 'Usuarios'];

type Props = {
  title: string;
  children: React.ReactNode;
};

export function AppShell({ title, children }: Props) {
  return (
    <div className="app-shell">
      <aside className="app-sidebar">
        <BrandLogo />
        <nav>
          {menu.map((item) => (
            <a key={item} href="#">{item}</a>
          ))}
        </nav>
        <small>InfoMatt360 · v0.1</small>
      </aside>
      <section className="app-main">
        <header className="app-header">
          <h1>{title}</h1>
          <span>Runtime MVP</span>
        </header>
        {children}
      </section>
    </div>
  );
}
