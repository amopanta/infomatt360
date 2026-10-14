import { createContext, useContext, useState, useCallback, useEffect, type ReactNode } from 'react';
import es from './locales/es.json';
import en from './locales/en.json';

// ── Supported locales ──
export type Locale = 'es' | 'en';
export const LOCALES: { code: Locale; label: string }[] = [
  { code: 'es', label: 'Español' },
  { code: 'en', label: 'English' },
];

const STORAGE_KEY = 'infomatt360_locale';
const bundles: Record<Locale, Record<string, unknown>> = { es, en };

// ── Nested key resolver ──
// t('auth.mfa.title') → bundles[locale].auth.mfa.title
function resolve(obj: Record<string, unknown>, path: string): string {
  const keys = path.split('.');
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== 'object') return path;
    current = (current as Record<string, unknown>)[key];
  }
  return typeof current === 'string' ? current : path;
}

// ── Interpolation ──
// t('format.megabytes', { value: '3.2' }) → "3.2 MB"
function interpolate(template: string, params?: Record<string, string | number>): string {
  if (!params) return template;
  return template.replace(/\{(\w+)\}/g, (_, key) => String(params[key] ?? `{${key}}`));
}

// ── Detect initial locale ──
function detectLocale(): Locale {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored && stored in bundles) return stored as Locale;
  } catch { /* storage unavailable */ }
  const nav = navigator.language?.slice(0, 2);
  return nav in bundles ? (nav as Locale) : 'es';
}

// ── Context ──
type I18nContextType = {
  locale: Locale;
  setLocale: (locale: Locale) => void;
  t: (key: string, params?: Record<string, string | number>) => string;
};

const I18nContext = createContext<I18nContextType | null>(null);

// ── Provider ──
export function I18nProvider({ children }: { children: ReactNode }) {
  const [locale, setLocaleState] = useState<Locale>(detectLocale);

  const setLocale = useCallback((next: Locale) => {
    setLocaleState(next);
    try { localStorage.setItem(STORAGE_KEY, next); } catch { /* ok */ }
    document.documentElement.lang = next;
  }, []);

  useEffect(() => {
    document.documentElement.lang = locale;
  }, []);

  const t = useCallback((key: string, params?: Record<string, string | number>): string => {
    const bundle = bundles[locale] ?? bundles.es;
    const value = resolve(bundle as Record<string, unknown>, key);
    // Fallback to Spanish if key not found in current locale
    const resolved = value === key ? resolve(bundles.es as Record<string, unknown>, key) : value;
    return interpolate(resolved, params);
  }, [locale]);

  return (
    <I18nContext.Provider value={{ locale, setLocale, t }}>
      {children}
    </I18nContext.Provider>
  );
}

// ── Hook ──
export function useI18n() {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error('useI18n must be used within I18nProvider');
  return ctx;
}

// ── Language selector component ──
export function LanguageSelector({ className }: { className?: string }) {
  const { locale, setLocale } = useI18n();
  return (
    <select
      className={className}
      value={locale}
      onChange={(e) => setLocale(e.target.value as Locale)}
      aria-label="Language"
      title="Language"
    >
      {LOCALES.map((l) => (
        <option key={l.code} value={l.code}>{l.label}</option>
      ))}
    </select>
  );
}
