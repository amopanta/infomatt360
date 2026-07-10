import { useEffect, useState } from 'react';
import { brand } from '../../theme/brand';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const ORG_SLUG = import.meta.env.VITE_ORG_SLUG ?? 'default';

export type PublicBranding = {
  organization_name: string;
  logo_url: string | null;
  primary_color: string | null;
  accent_color: string | null;
  background_color: string | null;
  slogan: string | null;
};

const STORAGE_KEY = 'infomatt360_branding_cache';

function applyBrandingVariables(branding: Partial<PublicBranding>) {
  const root = document.documentElement.style;
  root.setProperty('--brand-primary', branding.primary_color || brand.colors.primaryBlue);
  root.setProperty('--brand-accent', branding.accent_color || brand.colors.cyan);
  root.setProperty('--brand-background', branding.background_color || brand.colors.white);
}

/** Aplica el fallback local (theme/brand.ts) de inmediato para no bloquear el primer render. */
export function applyFallbackBranding(): void {
  applyBrandingVariables({});
}

/**
 * Carga la marca blanca de la organizacion activa desde el backend y la
 * inyecta como variables CSS globales. Offline-first: si falla (sin red,
 * organizacion aun no configurada), conserva el fallback ya aplicado.
 */
export async function loadOrganizationBranding(): Promise<PublicBranding | null> {
  try {
    const response = await fetch(`${API_BASE_URL}/public/branding?slug=${encodeURIComponent(ORG_SLUG)}`);
    if (!response.ok) return readCachedBranding();
    const branding = (await response.json()) as PublicBranding;
    applyBrandingVariables(branding);
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(branding));
    return branding;
  } catch {
    return readCachedBranding();
  }
}

function readCachedBranding(): PublicBranding | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    const cached = JSON.parse(raw) as PublicBranding;
    applyBrandingVariables(cached);
    return cached;
  } catch {
    return null;
  }
}

let brandingPromise: Promise<PublicBranding | null> | null = null;

/** Hook para consumir la marca blanca cargada en componentes (ej. BrandLogo). */
export function useOrganizationBranding(): PublicBranding | null {
  const [branding, setBranding] = useState<PublicBranding | null>(() => readCachedBrandingQuiet());

  useEffect(() => {
    if (!brandingPromise) brandingPromise = loadOrganizationBranding();
    let active = true;
    brandingPromise.then((result) => {
      if (active && result) setBranding(result);
    });
    return () => {
      active = false;
    };
  }, []);

  return branding;
}

function readCachedBrandingQuiet(): PublicBranding | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as PublicBranding;
  } catch {
    return null;
  }
}
