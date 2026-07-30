import { useEffect, useState } from 'react';
import { ChevronLeft, ChevronRight } from 'lucide-react';
import { api } from '../../api';
import type { CustomerOrder } from '../../api';
import { cardClass, inputClass, secondaryButtonClass } from '../../constants/styles';
import { useI18n } from '../../i18n';

const PAGE_SIZE = 15;

function displayDate(value: string | null | undefined) {
  if (!value) return '—';
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString();
}

type CustomerOrdersProps = {
  companyId: string | null | undefined;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
  onAnalyticsChange?: () => void | Promise<void>;
};

export function CustomerOrders({ companyId, setError }: CustomerOrdersProps) {
  const { t } = useI18n();
  const [leads, setLeads] = useState<CustomerOrder[]>([]);
  const [fromDate, setFromDate] = useState('');
  const [toDate, setToDate] = useState('');
  const [page, setPage] = useState(1);
  const [hasNextPage, setHasNextPage] = useState(false);
  const [loading, setLoading] = useState(false);

  const visibleLeads = leads.slice(0, PAGE_SIZE);

  useEffect(() => {
    let cancelled = false;

    async function loadLeads() {
      if (!companyId) return;
      setLoading(true);
      setError('');
      try {
        const data = await api.customerOrders(companyId, {
          status: 'all',
          from: fromDate || undefined,
          to: toDate || undefined,
          limit: PAGE_SIZE + 1,
          offset: (page - 1) * PAGE_SIZE,
        });
        if (cancelled) return;
        setLeads(data);
        setHasNextPage(data.length > PAGE_SIZE);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoading(false);
      }
    }

    void loadLeads();
    return () => { cancelled = true; };
  }, [companyId, fromDate, page, setError, toDate]);

  function resetFilters() {
    setFromDate('');
    setToDate('');
    setPage(1);
  }

  return (
    <section className="space-y-5">
      <div className={cardClass}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#15803d]">{t('orders.eyebrow')}</p>
            <h2 className="mt-2 text-2xl font-light text-[#18261d]">{t('orders.title')}</h2>
            <p className="mt-2 max-w-2xl text-sm text-[#586b60]">{t('orders.subtitle')}</p>
          </div>

          <div className="grid gap-3 sm:grid-cols-[repeat(2,minmax(150px,1fr))_auto] lg:min-w-[560px]">
            <label className="text-xs font-semibold uppercase tracking-[0.18em] text-[#18261d]">
              {t('orders.from')}
              <input
                type="date"
                className={`${inputClass} mt-2`}
                value={fromDate}
                onChange={(event) => { setFromDate(event.target.value); setPage(1); }}
              />
            </label>
            <label className="text-xs font-semibold uppercase tracking-[0.18em] text-[#18261d]">
              {t('orders.to')}
              <input
                type="date"
                className={`${inputClass} mt-2`}
                value={toDate}
                onChange={(event) => { setToDate(event.target.value); setPage(1); }}
              />
            </label>
            <div className="flex items-end">
              <button type="button" onClick={resetFilters} className={secondaryButtonClass}>{t('orders.reset')}</button>
            </div>
          </div>
        </div>

        <div className="mt-5 inline-flex items-center gap-3 rounded-[24px] bg-[#e4f5e9] px-5 py-4">
          <span className="text-sm font-medium text-[#586b60]">{t('orders.total')}</span>
          <span className="text-2xl font-semibold text-[#116932]">{visibleLeads.length}</span>
        </div>
      </div>

      <div className={`${cardClass} overflow-hidden p-0`}>
        {loading ? (
          <div className="p-6 text-sm text-[#586b60]">{t('orders.loading')}</div>
        ) : visibleLeads.length === 0 ? (
          <div className="p-6 text-sm text-[#586b60]">{t('orders.empty')}</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="min-w-full border-collapse text-left text-sm">
              <thead className="bg-[#e4f5e9] text-xs font-semibold uppercase tracking-[0.14em] text-[#586b60]">
                <tr>
                  <th className="px-5 py-4">{t('orders.customer')}</th>
                  <th className="px-5 py-4">{t('orders.course')}</th>
                  <th className="px-5 py-4">{t('orders.price')}</th>
                  <th className="px-5 py-4">{t('orders.channel')}</th>
                  <th className="px-5 py-4">{t('orders.date')}</th>
                  <th className="px-5 py-4">{t('orders.comment')}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#e1ebe4] bg-white">
                {visibleLeads.map((lead) => (
                  <tr key={lead.id} className="align-top transition-colors hover:bg-[#f7fbf8]">
                    <td className="px-5 py-4">
                      <p className="font-semibold text-[#18261d]">{lead.customer_name || lead.customer_phone || lead.customer_id}</p>
                      {lead.customer_phone && lead.customer_name && (
                        <p className="mt-1 text-xs text-[#586b60]">{lead.customer_phone}</p>
                      )}
                      <p className="mt-1 max-w-[220px] truncate text-xs text-[#708078]">ID: {lead.customer_id}</p>
                    </td>
                    <td className="px-5 py-4 font-medium text-[#18261d]">{lead.product_title || t('orders.courseUnknown')}</td>
                    <td className="whitespace-nowrap px-5 py-4 text-[#18261d]">{lead.product_price || '—'}</td>
                    <td className="px-5 py-4">
                      <span className="rounded-full bg-[#e4f5e9] px-3 py-1 text-xs font-semibold uppercase text-[#116932]">
                        {lead.channel}
                      </span>
                    </td>
                    <td className="whitespace-nowrap px-5 py-4 text-[#586b60]">{displayDate(lead.created_at)}</td>
                    <td className="max-w-[280px] px-5 py-4 text-[#586b60]">{lead.customer_comment || '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <div className="flex flex-col gap-3 rounded-[24px] border border-[#e1ebe4] bg-white p-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm text-[#586b60]">{t('orders.page')} {page} · {t('orders.shown')} {visibleLeads.length}</p>
        <div className="flex gap-2">
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={page === 1 || loading}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            <ChevronLeft size={16} /> {t('orders.previous')}
          </button>
          <button
            type="button"
            className={secondaryButtonClass}
            disabled={!hasNextPage || loading}
            onClick={() => setPage((current) => current + 1)}
          >
            {t('orders.next')} <ChevronRight size={16} />
          </button>
        </div>
      </div>
    </section>
  );
}
