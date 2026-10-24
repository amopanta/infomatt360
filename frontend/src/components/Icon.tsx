/**
 * Proyecto: InfoMatt360
 * Modulo: Icon
 * Responsabilidad: Set de iconos SVG en linea (sin dependencias externas) para
 * la navegacion y acciones. Los iconos heredan color via `currentColor`, asi
 * que siguen la marca por organizacion (docs/122) sin fijar colores literales.
 */

const ICONS: Record<string, string> = {
  dash: '<rect x="3" y="3" width="7" height="9" rx="1.5"/><rect x="14" y="3" width="7" height="5" rx="1.5"/><rect x="14" y="12" width="7" height="9" rx="1.5"/><rect x="3" y="16" width="7" height="5" rx="1.5"/>',
  form: '<rect x="4" y="3" width="16" height="18" rx="2"/><path d="M8 8h8M8 12h8M8 16h5"/>',
  acta: '<rect x="5" y="3" width="14" height="18" rx="2"/><path d="M9 8h6M9 12h6"/><path d="m9.5 16.5 1.5 1.5 3-3"/>',
  users: '<circle cx="9" cy="8" r="3.2"/><path d="M3.5 20a5.5 5.5 0 0 1 11 0"/><path d="M16 6.2a3 3 0 0 1 0 5.6M21 20a5 5 0 0 0-4-4.9"/>',
  records: '<ellipse cx="12" cy="5.5" rx="8" ry="2.8"/><path d="M4 5.5v13c0 1.5 3.6 2.8 8 2.8s8-1.3 8-2.8v-13"/><path d="M4 12c0 1.5 3.6 2.8 8 2.8s8-1.3 8-2.8"/>',
  photo: '<rect x="3" y="5" width="18" height="15" rx="2"/><circle cx="8.5" cy="10.5" r="1.8"/><path d="m3 17 5-4 4 3 3-2 6 5"/>',
  map: '<path d="M9 3 3 5.5v15L9 18l6 2.5 6-2.5v-15L15 5.5 9 3Z"/><path d="M9 3v15M15 5.5v15"/>',
  report: '<path d="M4 20V4"/><rect x="7" y="11" width="3.4" height="7" rx="1"/><rect x="13" y="7" width="3.4" height="11" rx="1"/><rect x="19" y="13" width="1.4" height="5" rx=".7"/>',
  msg: '<path d="M21 12a8 8 0 0 1-11.5 7.2L4 21l1.8-5.5A8 8 0 1 1 21 12Z"/>',
  shield: '<path d="M12 3 5 6v5c0 4.4 3 8.3 7 9.5 4-1.2 7-5.1 7-9.5V6l-7-3Z"/><path d="m9 12 2 2 4-4"/>',
  check: '<path d="M4 12.5 9 17.5 20 6.5"/><path d="M4 19h16"/>',
  aiaudit: '<rect x="4" y="6" width="16" height="12" rx="2"/><path d="M9 2v4M15 2v4M8 11h.01M12 11h.01M16 11h.01M8 15h5"/>',
  metric: '<path d="M4 15l4-5 4 3 6-7"/><path d="M4 20h16"/>',
  data: '<path d="M4 7V5.5C4 4.1 7.6 3 12 3s8 1.1 8 2.5V7"/><path d="M20 7c0 1.4-3.6 2.5-8 2.5S4 8.4 4 7"/><path d="M4 7v10c0 1.4 3.6 2.5 8 2.5"/><path d="M14.5 14.5 17 17l4-4"/>',
  exchange: '<path d="M4 8h13l-3-3M20 16H7l3 3"/>',
  plug: '<path d="M9 3v5M15 3v5"/><path d="M7 8h10v3a5 5 0 0 1-10 0Z"/><path d="M12 16v5"/>',
  key: '<circle cx="8" cy="15" r="4"/><path d="M11 12l8-8M17 6l2 2M14 9l2 2"/>',
  sync: '<path d="M4 10a8 8 0 0 1 13-4l3 3"/><path d="M20 14a8 8 0 0 1-13 4l-3-3"/><path d="M20 4v5h-5M4 20v-5h5"/>',
  box: '<path d="M3 8.5 12 4l9 4.5-9 4.5-9-4.5Z"/><path d="M3 8.5V16l9 4.5V13"/><path d="M21 8.5V16l-9 4.5"/>',
  erp: '<rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/>',
  link: '<path d="M9 15l6-6"/><path d="M10.5 6.5 12 5a4 4 0 0 1 6 6l-1.5 1.5M13.5 17.5 12 19a4 4 0 0 1-6-6l1.5-1.5"/>',
  gov: '<path d="M4 9 12 4l8 5"/><path d="M5 9v9M19 9v9M9 9v9M15 9v9M4 20h16"/>',
  brand: '<path d="M12 3v18M7 6h10M6 10c0 3.3 2.7 6 6 6s6-2.7 6-6"/>',
  mail: '<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m4 7 8 6 8-6"/>',
  backup: '<path d="M12 3a6 6 0 0 1 5.7 4.1A4.5 4.5 0 0 1 17 16H7A5 5 0 0 1 6 6.1 6 6 0 0 1 12 3Z"/><path d="M12 11v6M9.5 14.5 12 17l2.5-2.5"/>',
  lock: '<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>',
  gOper: '<path d="M3 12h4l2 6 4-14 2 8h6"/>',
  gRev: '<circle cx="12" cy="12" r="9"/><path d="m8.5 12 2.5 2.5 4.5-5"/>',
  gData: '<ellipse cx="12" cy="6" rx="7" ry="3"/><path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6"/>',
  gAdmin: '<circle cx="12" cy="12" r="3"/><path d="M12 2v3M12 19v3M4.2 4.2l2.1 2.1M17.7 17.7l2.1 2.1M2 12h3M19 12h3M4.2 19.8l2.1-2.1M17.7 6.3l2.1-2.1"/>',
  tablet: '<rect x="5" y="2.5" width="14" height="19" rx="2"/><path d="M10.5 18.5h3"/><path d="M9 8.5a4 4 0 0 1 6 0M10.5 10.5a1.8 1.8 0 0 1 3 0"/>',
  chevron: '<path d="M6 9l6 6 6-6"/>',
  db: '<ellipse cx="9" cy="6" rx="6" ry="2.5"/><path d="M3 6v10c0 1.4 2.7 2.5 6 2.5"/><path d="M3 11c0 1.4 2.7 2.5 6 2.5"/><path d="M14 14h7m-3-3 3 3-3 3"/>',
  eye: '<path d="M2.5 12S6 5.5 12 5.5 21.5 12 21.5 12 18 18.5 12 18.5 2.5 12 2.5 12Z"/><circle cx="12" cy="12" r="3"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16v4Z"/><path d="m13.5 6.5 4 4"/>',
  text: '<path d="M5 6V4.5h14V6"/><path d="M12 4.5v15"/><path d="M9 19.5h6"/>',
  hash: '<path d="M9 4 7 20M17 4l-2 16M4.5 9h15M3.5 15h15"/>',
  list: '<circle cx="5" cy="7" r="1.4"/><circle cx="5" cy="12" r="1.4"/><circle cx="5" cy="17" r="1.4"/><path d="M9.5 7H20M9.5 12H20M9.5 17H20"/>',
  calendar: '<rect x="3.5" y="5" width="17" height="15.5" rx="2"/><path d="M3.5 10h17M8 3v4M16 3v4"/>',
  camera: '<path d="M4 8h3l1.6-2.5h6.8L17 8h3v11H4Z"/><circle cx="12" cy="13.2" r="3.4"/>',
  pin: '<path d="M12 21s-6.5-6.2-6.5-11a6.5 6.5 0 0 1 13 0c0 4.8-6.5 11-6.5 11Z"/><circle cx="12" cy="10" r="2.4"/>',
  scale: '<path d="M4 17a8 8 0 0 1 16 0"/><path d="m12 17 4-5"/><path d="M4 20h16"/>',
  scan: '<path d="M4 8V5.5A1.5 1.5 0 0 1 5.5 4H8M16 4h2.5A1.5 1.5 0 0 1 20 5.5V8M20 16v2.5a1.5 1.5 0 0 1-1.5 1.5H16M8 20H5.5A1.5 1.5 0 0 1 4 18.5V16"/><path d="M7.5 12h9"/>',
  auto: '<path d="M13 3 5 13.5h6L10 21l8-10.5h-6Z"/>',
  gear: '<circle cx="12" cy="12" r="3"/><path d="M12 3.5v2.2M12 18.3v2.2M3.5 12h2.2M18.3 12h2.2M6 6l1.6 1.6M16.4 16.4 18 18M6 18l1.6-1.6M16.4 7.6 18 6"/>',
  sparkle: '<path d="M12 3.5 13.8 9 19.5 10.8 13.8 12.6 12 18.1 10.2 12.6 4.5 10.8 10.2 9Z"/><path d="M18.5 15.5v4M16.5 17.5h4"/>',
  file: '<path d="M6 3.5h8l4 4v13H6Z"/><path d="M14 3.5v4h4"/>',
  filePdf: '<path d="M6 3.5h8l4 4v13H6Z"/><path d="M14 3.5v4h4"/><path d="M9 13h6M9 16.5h4"/>',
  sheet: '<rect x="4" y="4" width="16" height="16" rx="1.5"/><path d="M4 9.5h16M4 15h16M10 4v16"/>',
  menu: '<path d="M4 7h16M4 12h16M4 17h16"/>',
  close: '<path d="M6 6l12 12M18 6 6 18"/>',
  route: '<circle cx="6" cy="18" r="2.2"/><circle cx="18" cy="6" r="2.2"/><path d="M8 18h7.5a3 3 0 0 0 0-6h-7a3 3 0 0 1 0-6H16"/>',
};

type IconProps = { name: string; className?: string };

export function Icon({ name, className }: IconProps) {
  return (
    <svg
      className={className ? `ic ${className}` : 'ic'}
      viewBox="0 0 24 24"
      aria-hidden="true"
      focusable="false"
      dangerouslySetInnerHTML={{ __html: ICONS[name] ?? '' }}
    />
  );
}
