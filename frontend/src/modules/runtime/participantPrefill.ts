import type { EligibleParticipant } from './api';
import { parseFieldConfig } from './fieldConfig';
import { allComponents, resolveFormValues } from './formLogic';
import { participantPhone } from './ParticipantSummaryTable';
import type { RuntimeFormValues, RuntimeTemplate } from './types';

export function prefillParticipantAnswers(template: RuntimeTemplate, person: EligibleParticipant, current: RuntimeFormValues, pulls: Record<string, string> = {}): RuntimeFormValues {
  const source: Record<string, string | null | undefined> = {
    full_name: person.full_name, document_id: person.document_id, external_code: person.external_code,
    phone: participantPhone(person), department: person.department, municipality: person.municipality,
    group_name: person.group_name,
  };
  const next = { ...current };
  for (const component of allComponents(template)) {
    const config = parseFieldConfig(component.config_json);
    const prefill = config.participant_field ? source[config.participant_field] : undefined;
    if (!prefill) continue;
    const existing = next[component.name];
    if (existing === undefined || existing === null || existing === '' || existing === config.default) next[component.name] = prefill;
  }
  return resolveFormValues(template, next, pulls);
}
