/**
 * Proyecto: InfoMatt360
 * Modulo: Runtime Draft
 * Responsabilidad: Guardar borradores locales para evitar perdida de datos en formularios grandes.
 */

import { useEffect, useState } from 'react';
import type { RuntimeFormValues } from './types';

export function useRuntimeDraft(templateId: string) {
  const storageKey = `infomatt360_draft_${templateId}`;
  const [values, setValues] = useState<RuntimeFormValues>(() => {
    const saved = localStorage.getItem(storageKey);
    return saved ? JSON.parse(saved) : {};
  });

  useEffect(() => {
    localStorage.setItem(storageKey, JSON.stringify(values));
  }, [storageKey, values]);

  function clearDraft() {
    localStorage.removeItem(storageKey);
    setValues({});
  }

  return { values, setValues, clearDraft };
}
