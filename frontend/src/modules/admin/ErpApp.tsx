import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { PROJECT_KEY } from '../auth/session';
import {
  createInventoryItem,
  createTemplateConfig,
  fetchInventoryItems,
  fetchInventoryMovements,
  fetchPayrollEntries,
  fetchTemplateConfig,
  markPayrollEntryPaid,
} from './erpApi';
import type { ErpInventoryItem, ErpInventoryMovement, ErpPayrollEntry, ErpTemplateConfig } from './erpApi';

type Tab = 'inventory' | 'payroll' | 'config';

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : '—';
}

export function ErpApp() {
  const projectId = localStorage.getItem(PROJECT_KEY) ?? '';
  const [tab, setTab] = useState<Tab>('inventory');
  const [message, setMessage] = useState('');

  const [items, setItems] = useState<ErpInventoryItem[]>([]);
  const [selectedItem, setSelectedItem] = useState<ErpInventoryItem | null>(null);
  const [movements, setMovements] = useState<ErpInventoryMovement[]>([]);
  const [newSku, setNewSku] = useState('');
  const [newName, setNewName] = useState('');
  const [newUnit, setNewUnit] = useState('unidad');
  const [newQuantity, setNewQuantity] = useState('0');

  const [payroll, setPayroll] = useState<ErpPayrollEntry[]>([]);
  const [gestorFilter, setGestorFilter] = useState('');

  const [configTemplateId, setConfigTemplateId] = useState('');
  const [configSkuField, setConfigSkuField] = useState('');
  const [configQuantityField, setConfigQuantityField] = useState('');
  const [configFeeAmount, setConfigFeeAmount] = useState('');
  const [lookupTemplateId, setLookupTemplateId] = useState('');
  const [lookupResult, setLookupResult] = useState<ErpTemplateConfig | null | undefined>(undefined);

  async function loadInventory() {
    try {
      const rows = await fetchInventoryItems(projectId);
      setItems(rows);
      if (rows[0]) await selectItem(rows[0]);
      else setSelectedItem(null);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar el inventario.');
    }
  }

  async function selectItem(item: ErpInventoryItem) {
    setSelectedItem(item);
    try {
      setMovements(await fetchInventoryMovements(item.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar los movimientos.');
    }
  }

  async function submitNewItem() {
    try {
      const created = await createInventoryItem({ projectId, sku: newSku, name: newName, unit: newUnit, quantityOnHand: newQuantity });
      setItems((current) => [...current, created]);
      setNewSku('');
      setNewName('');
      setNewQuantity('0');
      setMessage('Item de inventario creado.');
      await selectItem(created);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible crear el item.');
    }
  }

  async function loadPayroll() {
    try {
      setPayroll(await fetchPayrollEntries(projectId, gestorFilter.trim() || undefined));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible cargar los honorarios.');
    }
  }

  async function markPaid(entryId: string) {
    if (!window.confirm('Vas a marcar este honorario como pagado. Esta accion no revierte un desembolso bancario real, solo actualiza el registro. ¿Continuar?')) return;
    try {
      const updated = await markPayrollEntryPaid(entryId);
      setPayroll((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      setMessage('Honorario marcado como pagado.');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible marcar el honorario.');
    }
  }

  async function submitTemplateConfig() {
    try {
      await createTemplateConfig({ templateId: configTemplateId, skuFieldName: configSkuField, quantityFieldName: configQuantityField, feeAmount: configFeeAmount });
      setMessage('Plantilla vinculada al motor ERP.');
      setConfigTemplateId('');
      setConfigSkuField('');
      setConfigQuantityField('');
      setConfigFeeAmount('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible vincular la plantilla.');
    }
  }

  async function lookupTemplate() {
    try {
      setLookupResult(await fetchTemplateConfig(lookupTemplateId.trim()));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : 'No fue posible consultar la plantilla.');
    }
  }

  useEffect(() => {
    if (tab === 'inventory') void loadInventory();
    if (tab === 'payroll') void loadPayroll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, projectId]);

  return (
    <AppShell title="ERP">
      <main className="erp-shell">
        <nav className="erp-tabs">
          <button className={tab === 'inventory' ? 'active' : undefined} onClick={() => setTab('inventory')}>Inventario</button>
          <button className={tab === 'payroll' ? 'active' : undefined} onClick={() => setTab('payroll')}>Honorarios</button>
          <button className={tab === 'config' ? 'active' : undefined} onClick={() => setTab('config')}>Configuracion por plantilla</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'inventory' ? (
          <section className="erp-inventory">
            <div className="erp-inventory-create">
              <h2>Nuevo item de inventario</h2>
              <label>SKU<input value={newSku} onChange={(event) => setNewSku(event.target.value)} placeholder="KIT-001" /></label>
              <label>Nombre<input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder="Kit de herramientas" /></label>
              <label>Unidad<input value={newUnit} onChange={(event) => setNewUnit(event.target.value)} /></label>
              <label>Cantidad inicial<input value={newQuantity} onChange={(event) => setNewQuantity(event.target.value)} /></label>
              <button className="primary" disabled={!newSku.trim() || !newName.trim()} onClick={() => void submitNewItem()}>Crear item</button>
            </div>
            <div className="erp-inventory-list">
              <h2>Stock actual</h2>
              {items.length ? items.map((item) => (
                <article className={selectedItem?.id === item.id ? 'erp-item-card active' : 'erp-item-card'} key={item.id}>
                  <button onClick={() => void selectItem(item)}>
                    <strong>{item.sku}</strong>
                    <span>{item.name}</span>
                    <small>{item.quantity_on_hand} {item.unit}</small>
                  </button>
                </article>
              )) : <p>Aun no hay items de inventario en este proyecto.</p>}
            </div>
            <div className="erp-inventory-detail">
              {selectedItem ? (
                <>
                  <h2>Movimientos de {selectedItem.sku}</h2>
                  {movements.length ? movements.map((movement) => (
                    <article className="erp-movement-card" key={movement.id}>
                      <strong>{Number(movement.quantity_delta) > 0 ? '+' : ''}{movement.quantity_delta}</strong>
                      <span>{movement.reason}</span>
                      <small>{formatDate(movement.created_at)}{movement.reference_record_id ? ` · registro ${movement.reference_record_id}` : ''}</small>
                    </article>
                  )) : <p>Este item aun no tiene movimientos.</p>}
                </>
              ) : <p>Selecciona un item para ver su historial.</p>}
            </div>
          </section>
        ) : null}

        {tab === 'payroll' ? (
          <section className="erp-payroll">
            <div className="erp-payroll-filter">
              <label>
                Filtrar por gestor (user_id)
                <input value={gestorFilter} onChange={(event) => setGestorFilter(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void loadPayroll(); }} placeholder="opcional" />
              </label>
              <button onClick={() => void loadPayroll()}>Consultar</button>
            </div>
            <div className="erp-payroll-list">
              {payroll.length ? payroll.map((entry) => (
                <article className={`erp-payroll-card ${entry.status}`} key={entry.id}>
                  <div>
                    <strong>${entry.amount}</strong>
                    <span>Gestor: {entry.gestor_user_id}</span>
                    <small>{formatDate(entry.created_at)}{entry.reference_record_id ? ` · registro ${entry.reference_record_id}` : ''}</small>
                  </div>
                  {entry.status === 'accrued' ? <button onClick={() => void markPaid(entry.id)}>Marcar pagado</button> : <span className="erp-paid-badge">Pagado {formatDate(entry.paid_at)}</span>}
                </article>
              )) : <p>No hay honorarios registrados.</p>}
            </div>
          </section>
        ) : null}

        {tab === 'config' ? (
          <section className="erp-config">
            <div className="erp-config-create">
              <h2>Vincular plantilla al ERP</h2>
              <p>Al aprobarse un registro de esta plantilla, se descuenta stock del SKU indicado y se acredita el honorario al gestor.</p>
              <label>ID de la plantilla (Builder)<input value={configTemplateId} onChange={(event) => setConfigTemplateId(event.target.value)} placeholder="template_id" /></label>
              <label>Campo con el SKU<input value={configSkuField} onChange={(event) => setConfigSkuField(event.target.value)} placeholder="sku_kit" /></label>
              <label>Campo con la cantidad entregada<input value={configQuantityField} onChange={(event) => setConfigQuantityField(event.target.value)} placeholder="cantidad_entregada" /></label>
              <label>Honorario por registro aprobado<input value={configFeeAmount} onChange={(event) => setConfigFeeAmount(event.target.value)} placeholder="15000.00" /></label>
              <button className="primary" disabled={!configTemplateId.trim() || !configSkuField.trim() || !configQuantityField.trim() || !configFeeAmount.trim()} onClick={() => void submitTemplateConfig()}>Vincular</button>
            </div>
            <div className="erp-config-lookup">
              <h2>Consultar configuracion existente</h2>
              <label>ID de la plantilla<input value={lookupTemplateId} onChange={(event) => setLookupTemplateId(event.target.value)} placeholder="template_id" /></label>
              <button onClick={() => void lookupTemplate()}>Consultar</button>
              {lookupResult === null ? <p>Esta plantilla no tiene configuracion ERP.</p> : null}
              {lookupResult ? (
                <dl>
                  <div><dt>Campo SKU</dt><dd>{lookupResult.sku_field_name}</dd></div>
                  <div><dt>Campo cantidad</dt><dd>{lookupResult.quantity_field_name}</dd></div>
                  <div><dt>Honorario</dt><dd>${lookupResult.fee_amount}</dd></div>
                </dl>
              ) : null}
            </div>
          </section>
        ) : null}
      </main>
    </AppShell>
  );
}
