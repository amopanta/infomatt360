import { useEffect, useRef, useState } from 'react';
import { authorizationHeader } from '../auth/session';
import { allComponents } from './formLogic';
import { parseFieldConfig } from './fieldConfig';
import type { RuntimeFormValues, RuntimeTemplate } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000/api/v1';
const CALL = /pulldata\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*,\s*\$\{([\w.-]+)\}\s*\)/gi;

export type PullRequest = { file: string; column: string; key_column: string; key: string };
export function pullKey(request: PullRequest): string { return JSON.stringify([request.file, request.column, request.key_column, request.key]); }

export function findPullRequests(template: RuntimeTemplate, values: RuntimeFormValues): PullRequest[] {
  const requests: PullRequest[] = [];
  for (const component of allComponents(template)) {
    const config = parseFieldConfig(component.config_json);
    for (const expression of [config.calculation, config.default, config.relevant_expression, config.constraint_expression]) {
      if (typeof expression !== 'string') continue;
      for (const match of expression.matchAll(CALL)) {
        const value = values[match[4]];
        const key = String(value ?? '').trim();
        if (key) requests.push({ file: match[1], column: match[2], key_column: match[3], key });
      }
    }
  }
  return [...new Map(requests.map((request) => [pullKey(request), request])).values()];
}

export function usePullData(template: RuntimeTemplate | null, values: RuntimeFormValues, publicToken?: string) {
  const [pulls, setPulls] = useState<Record<string, string>>({});
  const [error, setError] = useState('');
  const pending = useRef(new Set<string>());
  const requests = template ? findPullRequests(template, values) : [];
  const signature = requests.map(pullKey).join('|');

  useEffect(() => {
    if (!template) return;
    for (const request of requests) {
      const cacheKey = pullKey(request);
      if (Object.prototype.hasOwnProperty.call(pulls, cacheKey) || pending.current.has(cacheKey)) continue;
      pending.current.add(cacheKey);
      const url = publicToken
        ? `${API_BASE_URL}/form-lookups/public/${encodeURIComponent(publicToken)}/value`
        : `${API_BASE_URL}/form-lookups/templates/${encodeURIComponent(template.template_id)}/value`;
      void fetch(url, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(!publicToken ? authorizationHeader() : {}) }, body: JSON.stringify(request) })
        .then(async (response) => { if (!response.ok) { const body = await response.json().catch(() => null); throw new Error(body?.detail || `No se pudo consultar ${request.file}.csv`); } return response.json() as Promise<{ value: string }>; })
        .then((result) => { setPulls((current) => ({ ...current, [cacheKey]: result.value })); setError(''); })
        .catch((reason: Error) => setError(reason.message))
        .finally(() => pending.current.delete(cacheKey));
    }
  }, [template, signature, pulls, publicToken]);
  return { pulls, error, ready: requests.every((request) => Object.prototype.hasOwnProperty.call(pulls, pullKey(request))) };
}
