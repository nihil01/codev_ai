import { useEffect, useMemo, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../../api';
import type { CustomerOrder, OrderStatus } from '../../api';
import { cardClass, inputClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { useI18n } from '../../i18n';

const ORDER_STATUSES: Array<'all' | 'paid' | 'cancelled'> = ['all', 'paid', 'cancelled'];
const PAGE_SIZE = 12;

function money(value: string | number | null | undefined) {
  const amount = Number(value ?? 0);
  return `${Number.isFinite(amount) ? amount.toFixed(2) : '0.00'} ₼`;
}

function displayDate(value: string | null | undefined) {
  if (!value) return '—';
  return new Date(value).toLocaleString();
}

function inferRevenue(order: CustomerOrder) {
  if (order.revenue_amount) return order.revenue_amount;
  const parsedPrice = Number(String(order.product_price ?? '').replace(/[^0-9.]/g, ''));
  const quantity = order.quantity && order.quantity > 0 ? order.quantity : 1;
  return Number.isFinite(parsedPrice) && parsedPrice > 0 ? (parsedPrice * quantity).toFixed(2) : '';
}

function statusBadgeClass(status: OrderStatus) {
  if (status === 'paid' || status === 'completed' || status === 'done') return 'bg-emerald-50 text-emerald-700 ring-emerald-100';
  if (status === 'cancelled') return 'bg-rose-50 text-rose-700 ring-rose-100';
  return 'bg-[#f5f5f5] text-[#696a72] ring-[#e2e4e9]';
}

type CustomerOrdersProps = {
  companyId: string | null | undefined;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
  onAnalyticsChange?: () => void | Promise<void>;
};

export function CustomerOrders({ companyId, setError, setNotice, onAnalyticsChange }: CustomerOrdersProps) {
  const { t } = useI18n();
  const [orders, setOrders] = useState<CustomerOrder[]>([]);
  const [statusFilter, setStatusFilter] = useState<'all' | 'paid' | 'cancelled'>('all');
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [page, setPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [loading, setLoading] = useState(false);
  const [savingId, setSavingId] = useState<string | null>(null);
  const [edits, setEdits] = useState<Record<string, { revenue_amount: string; cost_amount: string }>>({});

  const visibleOrders = orders.slice(0, PAGE_SIZE);

  const totals = useMemo(() => {
    return visibleOrders.reduce(
      (acc, order) => {
        const isPaid = ['paid', 'completed', 'done'].includes(order.status);
        if (!isPaid) return acc;
        acc.revenue += Number(order.revenue_amount ?? 0) || 0;
        acc.costs += Number(order.cost_amount ?? 0) || 0;
        acc.profit += Number(order.gross_profit ?? 0) || 0;
        acc.paid += 1;
        return acc;
      },
      { revenue: 0, costs: 0, profit: 0, paid: 0 },
    );
  }, [visibleOrders]);

  async function loadOrders(nextPage = page) {
    if (!companyId) return;
    setLoading(true);
    setError('');
    try {
      const data = await api.customerOrders(companyId, {
        status: statusFilter,
        from: fromDate || undefined,
        to: toDate || undefined,
        limit: PAGE_SIZE + 1,
        offset: (nextPage - 1) * PAGE_SIZE,
      });
      setOrders(data);
      setHasNextPage(data.length > PAGE_SIZE);
      setEdits(
        Object.fromEntries(
          data.slice(0, PAGE_SIZE).map((order) => [
            order.id,
            {
              revenue_amount: order.revenue_amount ?? inferRevenue(order),
              cost_amount: order.cost_amount ?? '',
            },
          ]),
        ),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadOrders(page);
  }, [companyId, statusFilter, fromDate, toDate, page]);

  function resetFilters() {
    setStatusFilter('all');
    setFromDate('');
    setToDate('');
    setPage(1);
  }

  function changeStatusFilter(status: 'all' | 'paid' | 'cancelled') {
    setStatusFilter(status);
    setPage(1);
  }

  async function updateOrder(order: CustomerOrder, status: 'paid' | 'cancelled') {
    if (!companyId) return;
    setSavingId(order.id);
    setError('');
    setNotice('');
    const edit = edits[order.id] ?? { revenue_amount: inferRevenue(order), cost_amount: order.cost_amount ?? '' };
    try {
      const updated = await api.updateCustomerOrder(companyId, order.id, {
        status,
        revenue_amount: edit.revenue_amount || null,
        cost_amount: edit.cost_amount || null,
      });
      setOrders((current) => current.map((item) => item.id === updated.id ? updated : item));
      setEdits((current) => ({
        ...current,
        [updated.id]: {
          revenue_amount: updated.revenue_amount ?? inferRevenue(updated),
          cost_amount: updated.cost_amount ?? '',
        },
      }));
      setNotice(t('orders.updated'));
      await onAnalyticsChange?.();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingId(null);
    }
  }

  function updateEdit(orderId: string, field: 'revenue_amount' | 'cost_amount', value: string) {
    setEdits((current) => ({
      ...current,
      [orderId]: {
        revenue_amount: current[orderId]?.revenue_amount ?? '',
        cost_amount: current[orderId]?.cost_amount ?? '',
        [field]: value,
      },
    }));
  }

  return (
    <section className="space-y-5">
      <div className={cardClass}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#145aff]">{t('orders.eyebrow')}</p>
            <h2 className="mt-2 text-2xl font-semibold text-[#020520]">{t('orders.title')}</h2>
            <p className="mt-2 text-sm text-[#696a72]">Only final statuses are exposed to managers now: paid or cancelled.</p>
          </div>
          <div className="grid gap-3 md:grid-cols-[repeat(2,minmax(150px,1fr))_auto] lg:min-w-[560px]">
            <label className="text-xs font-semibold uppercase tracking-[0.18em] text-[#696a72]">
              From
              <input type="date" className={`${inputClass} mt-2`} value={fromDate} onChange={(event) => { setFromDate(event.target.value); setPage(1); }} />
            </label>
            <label className="text-xs font-semibold uppercase tracking-[0.18em] text-[#696a72]">
              To
              <input type="date" className={`${inputClass} mt-2`} value={toDate} onChange={(event) => { setToDate(event.target.value); setPage(1); }} />
            </label>
            <div className="flex items-end">
              <button type="button" onClick={resetFilters} className={secondaryButtonClass}>Reset</button>
            </div>
          </div>
        </div>

        <div className="mt-5 flex flex-wrap gap-2">
          {ORDER_STATUSES.map((status) => (
            <button
              key={status}
              type="button"
              className={statusFilter === status ? primaryButtonClass : secondaryButtonClass}
              onClick={() => changeStatusFilter(status)}
            >
              {t(`orders.status.${status}`)}
            </button>
          ))}
        </div>

        <div className="mt-6 grid gap-3 md:grid-cols-4">
          <div className="rounded-lg bg-[#f0f4fe] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#696a72]">{t('orders.total')}</p>
            <p className="mt-2 text-2xl font-semibold text-[#020520]">{visibleOrders.length}</p>
          </div>
          <div className="rounded-lg bg-emerald-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-emerald-600">{t('orders.paid')}</p>
            <p className="mt-2 text-2xl font-semibold text-emerald-700">{totals.paid}</p>
          </div>
          <div className="rounded-lg bg-sky-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-sky-600">{t('orders.revenue')}</p>
            <p className="mt-2 text-2xl font-semibold text-sky-700">{money(totals.revenue)}</p>
          </div>
          <div className="rounded-lg bg-violet-50 p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-violet-600">{t('orders.profit')}</p>
            <p className="mt-2 text-2xl font-semibold text-violet-700">{money(totals.profit)}</p>
          </div>
        </div>
      </div>

      <div className="space-y-4">
        {loading ? (
          <div className={cardClass}>{t('orders.loading')}</div>
        ) : visibleOrders.length === 0 ? (
          <div className={cardClass}>{t('orders.empty')}</div>
        ) : visibleOrders.map((order) => {
          const edit = edits[order.id] ?? { revenue_amount: inferRevenue(order), cost_amount: order.cost_amount ?? '' };
          return (
            <article key={order.id} className={cardClass}>
              <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase ring-1 ${statusBadgeClass(order.status)}`}>
                      {t(`orders.status.${order.status}`)}
                    </span>
                    <span className="rounded-full bg-[#f0f4fe] px-3 py-1 text-xs font-semibold uppercase text-[#696a72]">
                      {order.channel}
                    </span>
                  </div>
                  <h3 className="mt-3 text-xl font-semibold text-[#020520]">{order.product_title || t('orders.productUnknown')}</h3>
                  <p className="mt-1 text-sm text-[#696a72]">
                    {order.customer_name || order.customer_phone || order.customer_id} · {displayDate(order.created_at)}
                  </p>
                  <div className="mt-4 grid gap-3 text-sm text-[#696a72] md:grid-cols-2 xl:grid-cols-4">
                    <div><b>{t('orders.quantity')}:</b> {order.quantity ?? '—'}</div>
                    <div><b>{t('orders.price')}:</b> {order.product_price || '—'}</div>
                    <div><b>{t('orders.phone')}:</b> {order.customer_phone || '—'}</div>
                    <div><b>{t('orders.notified')}:</b> {displayDate(order.manager_notified_at)}</div>
                  </div>
                  {order.customer_comment && <p className="mt-3 rounded-lg bg-[#f0f4fe] p-3 text-sm text-[#696a72]">{order.customer_comment}</p>}
                </div>

                <div className="w-full max-w-xl space-y-3 rounded-lg border border-[#e2e4e9] bg-[#fcfcfc] p-4">
                  <div className="grid gap-3 md:grid-cols-2">
                    <label className="text-sm font-semibold text-[#020520]">
                      {t('orders.revenue')}
                      <input
                        className={`${inputClass} mt-2`}
                        value={edit.revenue_amount}
                        onChange={(event) => updateEdit(order.id, 'revenue_amount', event.target.value)}
                        placeholder="0.00"
                      />
                    </label>
                    <label className="text-sm font-semibold text-[#020520]">
                      {t('orders.costs')}
                      <input
                        className={`${inputClass} mt-2`}
                        value={edit.cost_amount}
                        onChange={(event) => updateEdit(order.id, 'cost_amount', event.target.value)}
                        placeholder="0.00"
                      />
                    </label>
                  </div>
                  <p className="text-sm font-semibold text-[#696a72]">{t('orders.currentProfit')}: {money(order.gross_profit)}</p>
                  <div className="flex flex-wrap gap-2">
                    <button className={primaryButtonClass} disabled={savingId === order.id} onClick={() => updateOrder(order, 'paid')}>{t('orders.markPaid')}</button>
                    <button className="inline-flex items-center justify-center gap-2 rounded-xl border border-[#fecaca] bg-[#fff5f5] px-5 py-3 text-sm font-semibold text-[#b91c1c] transition hover:bg-[#fef2f2] disabled:opacity-50" disabled={savingId === order.id} onClick={() => updateOrder(order, 'cancelled')}>{t('orders.cancel')}</button>
                  </div>
                </div>
              </div>
            </article>
          );
        })}
      </div>

      <div className="flex flex-col gap-3 rounded-2xl border border-[#e2e4e9] bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-[#696a72]">Page {page} · showing {visibleOrders.length} orders</p>
        <div className="flex gap-2">
          <button type="button" className={secondaryButtonClass} disabled={page === 1 || loading} onClick={() => setPage((current) => Math.max(1, current - 1))}>
            <ChevronLeft size={16} /> Previous
          </button>
          <button type="button" className={secondaryButtonClass} disabled={!hasNextPage || loading} onClick={() => setPage((current) => current + 1)}>
            Next <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}
