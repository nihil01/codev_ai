import { useEffect, useMemo, useRef, useState } from 'react';
import { Download, ExternalLink, MessageSquareText, Search, Trash2, UserRound, X } from 'lucide-react';
import { api } from '../../api';
import type { Lead, LeadFilters, LeadPlatform, LeadStatus, LeadUpdate } from '../../api';
import { cardClass, inputClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { Spinner } from '../../components/ui/Spinner';

type ContactsPanelProps = {
  companyId?: string | null;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

const statuses: Array<{ value: LeadStatus | 'all'; label: string }> = [
  { value: 'all', label: 'Bütün statuslar' },
  { value: 'new', label: 'Yeni' },
{ value: 'interested', label: 'Maraqlanır' },
{ value: 'contacted', label: 'Əlaqə saxlanılıb' },
{ value: 'qualified', label: 'Uyğun lead' },
{ value: 'enrolled', label: 'Qeydiyyatdan keçib' },
{ value: 'not_interested', label: 'Maraqlanmır' },
  { value: 'lost', label: 'İtirilmiş' },
  { value: 'archived', label: 'Arxiv' },
];

const platforms: Array<{ value: LeadPlatform | 'all'; label: string }> = [
  { value: 'all', label: 'Bütün platformalar' },
  { value: 'instagram', label: 'Instagram' },
  { value: 'facebook', label: 'Facebook' },
  { value: 'tiktok', label: 'TikTok' },
  { value: 'whatsapp', label: 'WhatsApp' },
  { value: 'manual', label: 'Manual' },
];

const PAGE_SIZE = 300;

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('az-AZ', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function leadName(lead: Lead) {
  return [lead.first_name, lead.last_name].filter(Boolean).join(' ') || lead.username || lead.phone || lead.external_id;
}

function dateTimeLocal(value?: string | null) {
  if (!value) return '';
  const date = new Date(value);
  const offset = date.getTimezoneOffset();
  return new Date(date.getTime() - offset * 60000).toISOString().slice(0, 16);
}

export function ContactsPanel({ companyId, onError, onNotice }: ContactsPanelProps) {
  const [rows, setRows] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(false);
  const [filters, setFilters] = useState<LeadFilters>({ status: 'all', platform: 'all' });
  const [appliedFilters, setAppliedFilters] = useState<LeadFilters>({ status: 'all', platform: 'all' });
  const [hasMore, setHasMore] = useState(false);
  const [selected, setSelected] = useState<Lead | null>(null);
  const leadDialogRef = useRef<HTMLElement>(null);
  const leadTriggerRef = useRef<HTMLButtonElement | null>(null);
  const [draft, setDraft] = useState<LeadUpdate>({});
  const [saving, setSaving] = useState(false);
  const [summarizing, setSummarizing] = useState(false);
  const [exporting, setExporting] = useState(false);

  async function load(next = appliedFilters, append = false) {
    if (!companyId) return;
    setLoading(true);
    try {
      const batch = await api.leads(companyId, next, { limit: PAGE_SIZE, offset: append ? rows.length : 0 });
      setRows((current) => append ? [...current, ...batch] : batch);
      setHasMore(batch.length === PAGE_SIZE);
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    setAppliedFilters({ status: 'all', platform: 'all' });
    load({ status: 'all', platform: 'all' });
  }, [companyId]);

  useEffect(() => {
    if (!selected) return;
    const dialog = leadDialogRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog?.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeLead();
      if (event.key !== 'Tab' || !dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], input:not(:disabled), select:not(:disabled), textarea:not(:disabled), [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      leadTriggerRef.current?.focus();
    };
  }, [selected?.id]);

  const statusCounts = useMemo(() => rows.reduce<Record<string, number>>((result, lead) => {
    result[lead.status] = (result[lead.status] || 0) + 1;
    return result;
  }, {}), [rows]);

  function closeLead() {
    setSelected(null);
  }

  function applyFilters() {
    const next = { ...filters };
    setAppliedFilters(next);
    load(next);
  }

  async function openLead(lead: Lead) {
    if (!companyId) return;
    try {
      const profile = await api.leadProfile(companyId, lead.id);
      setSelected(profile);
      setDraft(profile);
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
    }
  }

  async function saveLead() {
    if (!companyId || !selected) return;
    setSaving(true);
    try {
      const updated = await api.updateLead(companyId, selected.id, draft);
      setSelected({ ...selected, ...updated });
      setRows((current) => current.map((item) => item.id === updated.id ? updated : item));
      onNotice?.('Lead profili yadda saxlanıldı.');
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
    } finally {
      setSaving(false);
    }
  }

  async function summarizeLead() {
    if (!companyId || !selected) return;
    setSummarizing(true);
    try {
      const updated = await api.summarizeLead(companyId, selected.id);
      setSelected((current) => current ? { ...current, ...updated } : updated);
      setDraft((current) => ({ ...current, ai_summary: updated.ai_summary }));
      setRows((current) => current.map((item) => item.id === updated.id ? { ...item, ...updated } : item));
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
    } finally {
      setSummarizing(false);
    }
  }

  async function removeLead() {
    if (!companyId || !selected || !window.confirm('Bu lead siyahıdan silinsin? Yazışmalar qorunacaq.')) return;
    try {
      await api.deleteLead(companyId, selected.id);
      setRows((current) => current.filter((item) => item.id !== selected.id));
      setSelected(null);
      onNotice?.('Lead silindi.');
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
    }
  }

  async function exportXlsx() {
    if (!companyId) return;
    setExporting(true);
    try {
      const blob = await api.exportLeads(companyId, appliedFilters);
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = url;
      anchor.download = `codev-leads-${new Date().toISOString().slice(0, 10)}.xlsx`;
      anchor.click();
      URL.revokeObjectURL(url);
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
    } finally {
      setExporting(false);
    }
  }

  const field = (key: keyof LeadUpdate, value: string | null) => setDraft((current) => ({ ...current, [key]: value || null }));

  return (
    <section className="space-y-5">
      <div className={cardClass}>
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#15803d]">CRM</p>
            <h2 className="mt-1 text-2xl font-semibold text-[#18261d]">Lead profilləri</h2>
            <p className="mt-1 text-sm text-[#708078]">Kurslarla maraqlanan lead-lər və onların bütün əlaqə tarixçəsi.</p>
          </div>
          <button type="button" onClick={exportXlsx} disabled={exporting || !companyId} className={secondaryButtonClass}>
            <Download size={17} /> {exporting ? 'Hazırlanır...' : 'XLSX ixrac'}
          </button>
        </div>

        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <label className="relative sm:col-span-2">
            <Search className="absolute left-3 top-3.5 text-[#708078]" size={17} />
            <input value={filters.q || ''} onChange={(e) => setFilters({ ...filters, q: e.target.value })} className={`${inputClass} pl-10`} placeholder="Ad, username, telefon..." />
          </label>
          <select value={filters.status || 'all'} onChange={(e) => setFilters({ ...filters, status: e.target.value as LeadStatus | 'all' })} className={inputClass}>
            {statuses.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <select value={filters.platform || 'all'} onChange={(e) => setFilters({ ...filters, platform: e.target.value as LeadPlatform | 'all' })} className={inputClass}>
            {platforms.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
          </select>
          <input value={filters.interested_in || ''} onChange={(e) => setFilters({ ...filters, interested_in: e.target.value })} className={inputClass} placeholder="Kurs" />
          <button type="button" onClick={applyFilters} className={primaryButtonClass}>Filtrlə</button>
          <input type="date" value={filters.from_date || ''} onChange={(e) => setFilters({ ...filters, from_date: e.target.value })} className={inputClass} aria-label="Başlanğıc tarixi" />
          <input type="date" value={filters.to_date || ''} onChange={(e) => setFilters({ ...filters, to_date: e.target.value })} className={inputClass} aria-label="Son tarix" />
        </div>

        <p className="mt-4 text-xs text-[#708078]">Status sayları hazırda göstərilən {rows.length} lead üzrə hesablanır.</p>
        <div className="mt-2 flex flex-wrap gap-2 text-xs">
          {statuses.slice(1).map((item) => <span key={item.value} className="rounded-full bg-[#e4f5e9] px-3 py-1.5 font-semibold text-[#15803d]">{item.label}: {statusCounts[item.value] || 0}</span>)}
        </div>
      </div>

      <div className="overflow-hidden rounded-2xl border border-[#e1ebe4] bg-white">
        {loading ? <div className="p-8"><Spinner label="Lead-lər yüklənir..." /></div> : rows.length === 0 ? (
          <div className="p-10 text-center text-sm text-[#708078]">Filtrə uyğun lead tapılmadı.</div>
        ) : (
          <div className="divide-y divide-[#e1ebe4]">
            {rows.map((lead) => (
              <button key={lead.id} type="button" onClick={(event) => { leadTriggerRef.current = event.currentTarget; openLead(lead); }} className="grid w-full gap-3 px-4 py-4 text-left transition hover:bg-[#e4f5e9] sm:grid-cols-[minmax(0,1.5fr)_1fr_1fr_auto] sm:items-center sm:px-6">
                <span className="flex min-w-0 items-center gap-3">
                  <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-[#e4f5e9] text-[#15803d]"><UserRound size={19} /></span>
                  <span className="min-w-0">
                    <span className="flex min-w-0 flex-wrap items-center gap-2">
                      <span className="block max-w-full truncate font-semibold text-[#18261d]">{leadName(lead)}</span>
                      {lead.manually_updated_at && (
                        <span
                          className="shrink-0 rounded-full bg-[#fff4d6] px-2.5 py-1 text-[10px] font-bold uppercase tracking-wide text-[#8a5a00]"
                          title={`Əl ilə yenilənib: ${formatDate(lead.manually_updated_at)}${lead.manually_updated_by ? ` · ${lead.manually_updated_by}` : ''}`}
                        >
                          Əl ilə yenilənib
                        </span>
                      )}
                    </span>
                    <span className="block truncate text-xs text-[#708078]">{lead.phone || lead.email || lead.external_id}</span>
                  </span>
                </span>
                <span className="text-sm"><span className="block font-semibold capitalize text-[#18261d]">{lead.platform}</span><span className="text-xs text-[#708078]">{lead.interested_in || 'Maraq qeyd edilməyib'}</span></span>
                <span><span className="rounded-full bg-[#e4f5e9] px-3 py-1 text-xs font-semibold text-[#15803d]">{statuses.find((item) => item.value === lead.status)?.label}</span></span>
                <span className="text-xs text-[#708078] sm:text-right">{formatDate(lead.last_interaction_at)}</span>
              </button>
            ))}
          </div>
        )}
      </div>
      {hasMore && (
        <div className="flex justify-center">
          <button type="button" onClick={() => load(appliedFilters, true)} disabled={loading} className={secondaryButtonClass}>{loading ? 'Yüklənir...' : 'Daha çox göstər'}</button>
        </div>
      )}

      {selected && (
        <div className="fixed inset-0 z-50 flex justify-end bg-[#18261d]/35" onMouseDown={(e) => { if (e.target === e.currentTarget) closeLead(); }}>
          <aside ref={leadDialogRef} role="dialog" aria-modal="true" aria-labelledby="lead-profile-title" tabIndex={-1} className="h-full w-full overflow-y-auto bg-[#f3faf5] sm:max-w-2xl">
            <div className="sticky top-0 z-10 flex items-center justify-between border-b border-[#e1ebe4] bg-white px-5 py-4">
              <div><p className="text-xs font-bold uppercase tracking-wider text-[#15803d]">Lead profili</p><h3 id="lead-profile-title" className="text-xl font-semibold text-[#18261d]">{leadName(selected)}</h3></div>
              <button data-autofocus type="button" onClick={closeLead} className="rounded-xl p-2 hover:bg-[#e4f5e9]" aria-label="Bağla"><X size={20} /></button>
            </div>

            <div className="space-y-5 p-4 sm:p-6">
              <div className={`${cardClass} grid gap-4 sm:grid-cols-2`}>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Ad<input value={draft.first_name || ''} onChange={(e) => field('first_name', e.target.value)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Soyad<input value={draft.last_name || ''} onChange={(e) => field('last_name', e.target.value)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Username<input value={draft.username || ''} onChange={(e) => field('username', e.target.value)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Telefon<input value={draft.phone || ''} onChange={(e) => field('phone', e.target.value)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Email<input type="email" value={draft.email || ''} onChange={(e) => field('email', e.target.value)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Lead statusu<select value={draft.status || selected.status} onChange={(e) => field('status', e.target.value)} className={inputClass}>{statuses.slice(1).map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}</select></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078] sm:col-span-2">Maraqlandığı kurs<input value={draft.interested_in || ''} onChange={(e) => field('interested_in', e.target.value)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078] sm:col-span-2">Teqlər<input value={(draft.tags || []).join(', ')} onChange={(e) => setDraft((current) => ({ ...current, tags: e.target.value.split(',').map((item) => item.trim()).filter(Boolean) }))} className={inputClass} placeholder="CCNA, Hot Lead, Price Inquiry" /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Təyin olunub<input value={draft.assigned_to || ''} onChange={(e) => field('assigned_to', e.target.value)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078]">Növbəti əlaqə<input type="datetime-local" value={dateTimeLocal(draft.next_follow_up_at)} onChange={(e) => field('next_follow_up_at', e.target.value ? new Date(e.target.value).toISOString() : null)} className={inputClass} /></label>
                <label className="grid gap-1 text-xs font-semibold text-[#708078] sm:col-span-2">AI xülasəsi<textarea value={draft.ai_summary || ''} onChange={(e) => field('ai_summary', e.target.value)} className={`${inputClass} min-h-24`} /></label>
                <button type="button" onClick={summarizeLead} disabled={summarizing || !selected.conversation_history?.length} className={`${secondaryButtonClass} sm:col-span-2`}>{summarizing ? 'AI xülasə hazırlayır...' : 'Dialoqu AI ilə xülasə et'}</button>
                <label className="grid gap-1 text-xs font-semibold text-[#708078] sm:col-span-2">İşçi qeydləri<textarea value={draft.notes || ''} onChange={(e) => field('notes', e.target.value)} className={`${inputClass} min-h-24`} /></label>
                {selected.profile_link && <a href={selected.profile_link} target="_blank" rel="noreferrer" className="inline-flex items-center gap-2 text-sm font-semibold text-[#15803d]"><ExternalLink size={16} /> Sosial profilə keç</a>}
              </div>

              <div className={cardClass}>
                <div className="mb-4 flex items-center gap-2"><MessageSquareText size={19} className="text-[#15803d]" /><h4 className="font-semibold text-[#18261d]">Yazışma tarixçəsi</h4></div>
                {!selected.conversation_history?.length ? <p className="text-sm text-[#708078]">Mesaj tarixçəsi hələ yoxdur.</p> : (
                  <div className="max-h-80 space-y-3 overflow-y-auto pr-1">{selected.conversation_history.map((message) => (
                    <div key={message.id} className={`flex ${message.direction === 'outbound' ? 'justify-end' : 'justify-start'}`}><div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm ${message.direction === 'outbound' ? 'bg-[#15803d] text-white' : 'bg-[#e1ebe4] text-[#18261d]'}`}><p className="whitespace-pre-wrap">{message.text || '—'}</p><p className={`mt-1 text-[10px] ${message.direction === 'outbound' ? 'text-white/70' : 'text-[#708078]'}`}>{formatDate(message.created_at)}</p></div></div>
                  ))}</div>
                )}
              </div>

              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-between">
                <button type="button" onClick={removeLead} className="inline-flex items-center justify-center gap-2 rounded-xl border border-red-200 px-5 py-3 text-sm font-semibold text-red-600 hover:bg-red-50"><Trash2 size={17} /> Lead-i sil</button>
                <button type="button" onClick={saveLead} disabled={saving} className={primaryButtonClass}>{saving ? 'Yadda saxlanılır...' : 'Dəyişiklikləri saxla'}</button>
              </div>
            </div>
          </aside>
        </div>
      )}
    </section>
  );
}