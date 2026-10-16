/**
 * Proyecto: InfoMatt360
 * Modulo: Runtime Draft
 * Responsabilidad: Guardar borradores locales para evitar perdida de datos en formularios grandes.
 */

import { useEffect, useState } from 'react';
import type { RuntimeFormValues } from './types';

function readDraft(storageKey: string): RuntimeFormValues {
  try {
    const saved = localStorage.getItem(storageKey);
    const parsed: unknown = saved ? JSON.parse(saved) : {};
    return parsed && typeof parsed === 'object' && !Array.isArray(parsed) ? parsed as RuntimeFormValues : {};
  } catch { return {}; }
}

export function useRuntimeDraft(templateId: string, participantId = '') {
  const storageKey = `infomatt360_draft_${templateId}_${participantId || 'sin-participante'}`;
  const [activeKey, setActiveKey] = useState(storageKey);
  const [values, setValues] = useState<RuntimeFormValues>(() => readDraft(storageKey));

  useEffect(() => {
    if (activeKey === storageKey) return;
    setValues(readDraft(storageKey));
    setActiveKey(storageKey);
  }, [activeKey, storageKey]);

  useEffect(() => {
    if (activeKey !== storageKey) return;
    localStorage.setItem(storageKey, JSON.stringify(values));
  }, [activeKey, storageKey, values]);

  function clearDraft() {
    localStorage.removeItem(storageKey);
    setValues({});
  }

  return { values, setValues, clearDraft, ready: activeKey === storageKey };
}
