import { mapFieldSchemaToTableauColumns } from './schemaMapping';
import { mapTabularPageToTableauRows } from './rowMapping';
import type { ExternalFieldSchema, ExternalRecordTabularPage, ExternalTemplateSummary } from './types';
import './tableau-wdc.d.ts';

/** Web Data Connector real para Tableau (docs/96 item #9, docs/114).
 * Pagina estatica cargada por Tableau Desktop/Server via URL directa, no
 * parte del shell de React -- ver tableau-wdc/index.html y el input
 * multi-pagina de vite.config.ts. La logica de mapeo de esquema/filas vive
 * en schemaMapping.ts/rowMapping.ts (funciones puras, probadas con
 * vitest); este archivo es un wrapper delgado sobre la API JS de Tableau,
 * que solo puede verificarse con Tableau real instalado (limite honesto,
 * mismo criterio que el camino Postgres/PostGIS de docs/113). */

type ConnectionConfig = { apiBaseUrl: string; apiKey: string; templateId: string; statusFilter: string };

const PAGE_SIZE = 100;

function readConnectionConfig(): ConnectionConfig {
  return JSON.parse(tableau.connectionData) as ConnectionConfig;
}

async function fetchJson<T>(config: ConnectionConfig, path: string): Promise<T> {
  const response = await fetch(`${config.apiBaseUrl}${path}`, { headers: { 'X-API-Key': config.apiKey } });
  if (!response.ok) throw new Error(`No fue posible consultar ${path}: ${response.status}`);
  return response.json();
}

const connector = tableau.makeConnector();

connector.getSchema = function (schemaCallback: (tables: unknown[]) => void) {
  const config = readConnectionConfig();
  fetchJson<ExternalFieldSchema[]>(config, `/external-api/templates/${config.templateId}/schema`)
    .then((fields) => {
      const columns = mapFieldSchemaToTableauColumns(fields);
      schemaCallback([
        {
          id: 'records',
          alias: `InfoMatt360 - ${config.templateId}`,
          columns,
        },
      ]);
    })
    .catch((error: Error) => tableau.abortWithError(error.message));
};

connector.getData = function (table: { tableInfo: { id: string }; appendRows: (rows: Array<Record<string, unknown>>) => void }, doneCallback: () => void) {
  const config = readConnectionConfig();

  async function pullAllPages() {
    const fields = await fetchJson<ExternalFieldSchema[]>(config, `/external-api/templates/${config.templateId}/schema`);
    const columns = mapFieldSchemaToTableauColumns(fields);
    let offset = 0;
    let total = Infinity;
    while (offset < total) {
      const params = new URLSearchParams({ template_id: config.templateId, status: config.statusFilter, limit: String(PAGE_SIZE), offset: String(offset) });
      const page = await fetchJson<ExternalRecordTabularPage>(config, `/external-api/records/tabular?${params}`);
      table.appendRows(mapTabularPageToTableauRows(page, columns));
      total = page.total;
      offset += PAGE_SIZE;
    }
  }

  pullAllPages().then(doneCallback).catch((error: Error) => tableau.abortWithError(error.message));
};

tableau.registerConnector(connector);

function currentFormConfig(): ConnectionConfig {
  const byId = (id: string) => (document.getElementById(id) as HTMLInputElement).value;
  return { apiBaseUrl: byId('apiBaseUrl'), apiKey: byId('apiKey'), templateId: byId('templateId'), statusFilter: byId('statusFilter') };
}

async function fetchTemplates(config: ConnectionConfig): Promise<ExternalTemplateSummary[]> {
  return fetchJson<ExternalTemplateSummary[]>(config, '/external-api/templates');
}

window.addEventListener('DOMContentLoaded', () => {
  const submitButton = document.getElementById('submitButton');
  submitButton?.addEventListener('click', () => {
    const config = currentFormConfig();
    tableau.connectionData = JSON.stringify(config);
    tableau.connectionName = `InfoMatt360 - ${config.templateId}`;
    tableau.submit();
  });

  const loadTemplatesButton = document.getElementById('loadTemplatesButton');
  loadTemplatesButton?.addEventListener('click', () => {
    const status = document.getElementById('formStatus');
    fetchTemplates(currentFormConfig())
      .then((templates) => {
        if (status) status.textContent = templates.map((template) => `${template.id} — ${template.name}`).join('\n');
      })
      .catch((error: Error) => {
        if (status) status.textContent = error.message;
      });
  });
});
