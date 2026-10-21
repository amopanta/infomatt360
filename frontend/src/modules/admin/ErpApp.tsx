import { formatOperationalDate, operationalStatusLabel } from '../../lib/operationalFormat';
import { useEffect, useState } from 'react';

import { AppShell } from '../../components/AppShell';
import { useI18n } from '../../i18n';
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
  return formatOperationalDate(value);
}

export function ErpApp() {
  const { t } = useI18n();
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
      setMessage(error instanceof Error ? error.message : t('admin.erp.errorLoadInventory'));
    }
  }

  async function selectItem(item: ErpInventoryItem) {
    setSelectedItem(item);
    try {
      setMovements(await fetchInventoryMovements(item.id));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.erp.errorLoadMovements'));
    }
  }

  async function submitNewItem() {
    try {
      const created = await createInventoryItem({ projectId, sku: newSku, name: newName, unit: newUnit, quantityOnHand: newQuantity });
      setItems((current) => [...current, created]);
      setNewSku('');
      setNewName('');
      setNewQuantity('0');
      setMessage(t('admin.erp.itemCreated'));
      await selectItem(created);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.erp.errorCreateItem'));
    }
  }

  async function loadPayroll() {
    try {
      setPayroll(await fetchPayrollEntries(projectId, gestorFilter.trim() || undefined));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.erp.errorLoadPayroll'));
    }
  }

  async function markPaid(entryId: string) {
    if (!window.confirm(t('admin.erp.confirmMarkPaid'))) return;
    try {
      const updated = await markPayrollEntryPaid(entryId);
      setPayroll((current) => current.map((entry) => (entry.id === updated.id ? updated : entry)));
      setMessage(t('admin.erp.payrollMarkedPaid'));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.erp.errorMarkPaid'));
    }
  }

  async function submitTemplateConfig() {
    try {
      await createTemplateConfig({ templateId: configTemplateId, skuFieldName: configSkuField, quantityFieldName: configQuantityField, feeAmount: configFeeAmount });
      setMessage(t('admin.erp.templateLinked'));
      setConfigTemplateId('');
      setConfigSkuField('');
      setConfigQuantityField('');
      setConfigFeeAmount('');
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.erp.errorLinkTemplate'));
    }
  }

  async function lookupTemplate() {
    try {
      setLookupResult(await fetchTemplateConfig(lookupTemplateId.trim()));
    } catch (error) {
      setMessage(error instanceof Error ? error.message : t('admin.erp.errorLookupTemplate'));
    }
  }

  useEffect(() => {
    if (tab === 'inventory') void loadInventory();
    if (tab === 'payroll') void loadPayroll();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [tab, projectId]);

  return (
    <AppShell title={t('admin.erp.title')}>
      <main className="erp-shell">
        <section className="erp-resources" aria-labelledby="erp-resources-title">
          <div>
            <h2 id="erp-resources-title">{t('admin.erp.guidesTitle')}</h2>
            <p>{t('admin.erp.guidesDescription')}</p>
          </div>
          <div className="erp-resource-links">
            <a href="/erp/manual-usuario-erp-infomatt360.pdf" target="_blank" rel="noopener noreferrer">{t('admin.erp.viewManual')}</a>
            <a href="/erp/manual-usuario-erp-infomatt360.docx" download>{t('admin.erp.downloadManual')}</a>
            <a href="/erp/plantilla-erp-infomatt360.xlsx" download>{t('admin.erp.downloadTemplate')}</a>
            <a href="/erp/validacion-erp-infomatt360-2026-09-28.md" download>{t('admin.erp.downloadDiagnostic')}</a>
          </div>
          <p className="erp-resource-note">{t('admin.erp.templateNote')}</p>
        </section>
        <nav className="erp-tabs">
          <button className={tab === 'inventory' ? 'active' : undefined} onClick={() => setTab('inventory')}>{t('admin.erp.tabInventory')}</button>
          <button className={tab === 'payroll' ? 'active' : undefined} onClick={() => setTab('payroll')}>{t('admin.erp.tabPayroll')}</button>
          <button className={tab === 'config' ? 'active' : undefined} onClick={() => setTab('config')}>{t('admin.erp.tabConfig')}</button>
        </nav>
        {message ? <p role="status" className="erp-message">{message}</p> : null}

        {tab === 'inventory' ? (
          <section className="erp-inventory">
            <div className="erp-inventory-create">
              <h2>{t('admin.erp.newItemTitle')}</h2>
              <label>{t('admin.erp.skuLabel')}<input value={newSku} onChange={(event) => setNewSku(event.target.value)} placeholder={t('admin.erp.skuPlaceholder')} /></label>
              <label>{t('admin.erp.nameLabel')}<input value={newName} onChange={(event) => setNewName(event.target.value)} placeholder={t('admin.erp.namePlaceholder')} /></label>
              <label>{t('admin.erp.unitLabel')}<input value={newUnit} onChange={(event) => setNewUnit(event.target.value)} /></label>
              <label>{t('admin.erp.initialQuantityLabel')}<input value={newQuantity} onChange={(event) => setNewQuantity(event.target.value)} /></label>
              <button className="primary" disabled={!newSku.trim() || !newName.trim()} onClick={() => void submitNewItem()}>{t('admin.erp.createItem')}</button>
            </div>
            <div className="erp-inventory-list">
              <h2>{t('admin.erp.currentStock')}</h2>
              {items.length ? items.map((item) => (
                <article className={selectedItem?.id === item.id ? 'erp-item-card active' : 'erp-item-card'} key={item.id}>
                  <button onClick={() => void selectItem(item)}>
                    <strong>{item.sku}</strong>
                    <span>{item.name}</span>
                    <small>{item.quantity_on_hand} {item.unit}</small>
                  </button>
                </article>
              )) : <p>{t('admin.erp.noItemsYet')}</p>}
            </div>
            <div className="erp-inventory-detail">
              {selectedItem ? (
                <>
                  <h2>{t('admin.erp.movementsOf', { sku: selectedItem.sku })}</h2>
                  {movements.length ? movements.map((movement) => (
                    <article className="erp-movement-card" key={movement.id}>
                      <strong>{Number(movement.quantity_delta) > 0 ? '+' : ''}{movement.quantity_delta}</strong>
                      <span>{operationalStatusLabel(movement.reason)}</span>
                      <small>{formatDate(movement.created_at)}{movement.reference_record_id ? ` · ${t('admin.erp.recordRef', { id: movement.reference_record_id })}` : ''}</small>
                    </article>
                  )) : <p>{t('admin.erp.noMovementsYet')}</p>}
                </>
              ) : <p>{t('admin.erp.selectItemPrompt')}</p>}
            </div>
          </section>
        ) : null}

        {tab === 'payroll' ? (
          <section className="erp-payroll">
            <div className="erp-payroll-filter">
              <label>
                {t('admin.erp.filterByGestor')}
                <input value={gestorFilter} onChange={(event) => setGestorFilter(event.target.value)} onKeyDown={(event) => { if (event.key === 'Enter') void loadPayroll(); }} placeholder={t('admin.erp.filterOptional')} />
              </label>
              <button onClick={() => void loadPayroll()}>{t('admin.erp.query')}</button>
            </div>
            <div className="erp-payroll-list">
              {payroll.length ? payroll.map((entry) => (
                <article className={`erp-payroll-card ${entry.status}`} key={entry.id}>
                  <div>
                    <strong>${entry.amount}</strong>
                    <span>{t('admin.erp.gestorLabel', { id: entry.gestor_name || entry.gestor_user_id })}</span>
                    <small>{formatDate(entry.created_at)}{entry.reference_record_id ? ` · ${t('admin.erp.recordRefPayroll', { id: entry.reference_record_id })}` : ''}</small>
                  </div>
                  {entry.status === 'accrued' ? <button onClick={() => void markPaid(entry.id)}>{t('admin.erp.markPaid')}</button> : <span className="erp-paid-badge">{entry.status === 'paid' ? t('admin.erp.paidBadge', { date: formatDate(entry.paid_at) }) : operationalStatusLabel(entry.status)}</span>}
                </article>
              )) : <p>{t('admin.erp.noPayrollYet')}</p>}
            </div>
          </section>
        ) : null}

        {tab === 'config' ? (
          <section className="erp-config">
            <div className="erp-config-create">
              <h2>{t('admin.erp.linkTemplateTitle')}</h2>
              <p>{t('admin.erp.linkTemplateDescription')}</p>
              <label>{t('admin.erp.templateIdLabel')}<input value={configTemplateId} onChange={(event) => setConfigTemplateId(event.target.value)} placeholder={t('admin.erp.templateIdPlaceholder')} /></label>
              <label>{t('admin.erp.skuFieldLabel')}<input value={configSkuField} onChange={(event) => setConfigSkuField(event.target.value)} placeholder={t('admin.erp.skuFieldPlaceholder')} /></label>
              <label>{t('admin.erp.quantityFieldLabel')}<input value={configQuantityField} onChange={(event) => setConfigQuantityField(event.target.value)} placeholder={t('admin.erp.quantityFieldPlaceholder')} /></label>
              <label>{t('admin.erp.feeLabel')}<input value={configFeeAmount} onChange={(event) => setConfigFeeAmount(event.target.value)} placeholder={t('admin.erp.feePlaceholder')} /></label>
              <button className="primary" disabled={!configTemplateId.trim() || !configSkuField.trim() || !configQuantityField.trim() || !configFeeAmount.trim()} onClick={() => void submitTemplateConfig()}>{t('admin.erp.linkButton')}</button>
            </div>
            <div className="erp-config-lookup">
              <h2>{t('admin.erp.lookupTitle')}</h2>
              <label>{t('admin.erp.lookupTemplateLabel')}<input value={lookupTemplateId} onChange={(event) => setLookupTemplateId(event.target.value)} placeholder={t('admin.erp.templateIdPlaceholder')} /></label>
              <button onClick={() => void lookupTemplate()}>{t('admin.erp.lookupButton')}</button>
              {lookupResult === null ? <p>{t('admin.erp.noErpConfig')}</p> : null}
              {lookupResult ? (
                <dl>
                  <div><dt>{t('admin.erp.skuFieldResult')}</dt><dd>{lookupResult.sku_field_name}</dd></div>
                  <div><dt>{t('admin.erp.quantityFieldResult')}</dt><dd>{lookupResult.quantity_field_name}</dd></div>
                  <div><dt>{t('admin.erp.feeResult')}</dt><dd>${lookupResult.fee_amount}</dd></div>
                </dl>
              ) : null}
            </div>
          </section>
        ) : null}
      </main>
    </AppShell>
  );
}
