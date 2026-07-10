import { useOrganizationBranding } from '../modules/branding/brandingLoader';

export function BrandLogo() {
  const branding = useOrganizationBranding();
  const name = branding?.organization_name || 'INFOMATT360';
  const mark = branding?.organization_name ? name.charAt(0).toUpperCase() : 'M';

  return (
    <div className="brand-logo" aria-label={name}>
      {branding?.logo_url ? (
        <img src={branding.logo_url} alt={name} className="brand-mark-image" />
      ) : (
        <div className="brand-mark">{mark}</div>
      )}
      <div>
        <strong>{name}</strong>
        {branding?.slogan ? <span>{branding.slogan}</span> : <span>360</span>}
      </div>
    </div>
  );
}
