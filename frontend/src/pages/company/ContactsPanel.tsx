import { useEffect, useMemo, useState } from 'react';
import { Filter, Search, UserRound, UsersRound } from 'lucide-react';
import { api } from '../../api';
import type { Contact } from '../../api';
import { cardClass, inputClass } from '../../constants/styles';
import { Spinner } from '../../components/ui/Spinner';

type ContactsPanelProps = {
  companyId?: string | null;
  onError?: (message: string) => void;
};

type SegmentFilter = 'all' | 'lead' | 'customer' | 'hot';

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

function segmentLabel(segment: string) {
  if (segment === 'customer') return 'Müştəri';
  if (segment === 'hot') return 'Prioritet müraciət';
  return 'Müraciət';
}

function channelBadge(channel: Contact['channel']) {
  return channel === 'instagram' ? 'Instagram' : 'WhatsApp';
}

export function ContactsPanel({ companyId, onError }: ContactsPanelProps) {
  const [contacts, setContacts] = useState<Contact[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [segment, setSegment] = useState<SegmentFilter>('all');

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;
    setLoading(true);
    api.contacts(companyId, { q: query, segment })
      .then((items) => { if (!cancelled) setContacts(items); })
      .catch((err) => { if (!cancelled) onError?.(err instanceof Error ? err.message : String(err)); })
      .finally(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [companyId, query, segment]);

  const totals = useMemo(() => ({
    all: contacts.length,
    customers: contacts.filter((item) => item.segment === 'customer').length,
    hot: contacts.filter((item) => item.segment === 'hot').length,
  }), [contacts]);

  return (
    <section className="space-y-5">
      <div className={cardClass}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <div className="flex items-center gap-3">
              <span className="rounded-[14px] bg-[#e1f4df] p-3 text-[#0f3e17]"><UsersRound size={24} /></span>
              <div>
                <h2 className="text-2xl font-light tracking-[-0.02em] text-[#0f3e17]">Kontaktlar</h2>
                <p className="mt-1 text-sm text-[#222222]">İş məkanında {totals.all} kontakt · {totals.customers} müştəri · {totals.hot} prioritet müraciət</p>
              </div>
            </div>
          </div>
          <div className="grid gap-3 md:grid-cols-[minmax(260px,420px)_180px]">
            <label className="relative block">
              <Search className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#222222]" size={18} />
              <input
                className={`${inputClass} pl-10`}
                value={query}
                placeholder="Ad, telefon, istifadəçi adı və ya ID ilə axtar..."
                onChange={(event) => setQuery(event.target.value)}
              />
            </label>
            <label className="relative block">
              <Filter className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-[#222222]" size={18} />
              <select className={`${inputClass} pl-10`} value={segment} onChange={(event) => setSegment(event.target.value as SegmentFilter)}>
                <option value="all">Bütün seqmentlər</option>
                <option value="lead">Müraciətlər</option>
                <option value="hot">Prioritet müraciətlər</option>
                <option value="customer">Müştərilər</option>
              </select>
            </label>
          </div>
        </div>
      </div>

      <div className={cardClass}>
        {loading ? (
          <Spinner label="Kontaktlar yüklənir" />
        ) : contacts.length === 0 ? (
          <div className="flex min-h-[320px] flex-col items-center justify-center text-center">
            <div className="mb-4 rounded-full bg-[#efeeeb] p-5 text-[#222222]"><UserRound size={42} /></div>
            <h3 className="text-lg font-light text-[#0f3e17]">Hələ kontakt yoxdur</h3>
            <p className="mt-2 max-w-md text-sm text-[#222222]">Müştərilər yazışmağa başladıqda kontaktlar Instagram, WhatsApp və müraciət tarixçəsindən avtomatik yaradılacaq.</p>
          </div>
        ) : (
          <div className="overflow-hidden rounded-[14px] border border-[#efeeeb]">
            <table className="min-w-full divide-y divide-[#efeeeb] text-sm">
              <thead className="bg-[#e1f4df] text-left text-xs uppercase tracking-[0.08em] text-[#222222]">
                <tr>
                  <th className="px-4 py-3">Kontakt</th>
                  <th className="px-4 py-3">Kanal</th>
                  <th className="px-4 py-3">Seqment</th>
                  <th className="px-4 py-3">Müraciətlər</th>
                  <th className="px-4 py-3">Gəlir</th>
                  <th className="px-4 py-3">Son aktivlik</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#efeeeb] bg-[#fffefc]">
                {contacts.map((contact) => (
                  <tr key={`${contact.channel}-${contact.id}`} className="hover:bg-[#fffefc]">
                    <td className="px-4 py-3">
                      <div className="font-semibold text-[#0f3e17]">{contact.display_name || contact.username || contact.phone || contact.external_id}</div>
                      <div className="mt-1 text-xs text-[#222222]">{contact.username ? `@${contact.username}` : contact.phone || contact.external_id}</div>
                    </td>
                    <td className="px-4 py-3"><span className="rounded-full bg-[#e1f4df] px-3 py-1 text-xs font-semibold text-[#0f3e17]">{channelBadge(contact.channel)}</span></td>
                    <td className="px-4 py-3"><span className="rounded-full bg-[#e1f4df] px-3 py-1 text-xs font-semibold text-[#0f3e17]">{segmentLabel(contact.segment)}</span></td>
                    <td className="px-4 py-3 text-[#0f3e17]">{contact.orders_count}</td>
                    <td className="px-4 py-3 text-[#0f3e17]">{contact.total_revenue}</td>
                    <td className="px-4 py-3 text-[#222222]">{formatDate(contact.last_message_at || contact.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </section>
  );
}
