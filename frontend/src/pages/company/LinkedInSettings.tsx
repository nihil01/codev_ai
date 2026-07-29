import { useEffect, useState } from 'react';
import { Link2, RefreshCw, Unplug } from 'lucide-react';
import { api } from '../../api';
import type { LinkedInIntegration } from '../../api';
import { cardClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { Spinner } from '../../components/ui/Spinner';

type Props = {
  companyId?: string | null;
  onError: (message: string) => void;
  onNotice: (message: string) => void;
};

function formatDate(value?: string | null) {
  return value ? new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value)) : '—';
}

export function LinkedInSettings({ companyId, onError, onNotice }: Props) {
  const [integration, setIntegration] = useState<LinkedInIntegration | null>(null);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  async function load() {
    if (!companyId) return;
    setLoading(true);
    onError('');
    try { setIntegration(await api.linkedinIntegration(companyId)); }
    catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { setLoading(false); }
  }

  useEffect(() => { void load(); }, [companyId]);

  async function connect() {
    if (!companyId) return;
    const popup = window.open('', '_blank');
    setConnecting(true);
    onError('');
    try {
      const { auth_url } = await api.connectLinkedIn(companyId);
      if (!auth_url) throw new Error('Zernio boş OAuth ünvanı qaytardı.');
      if (popup) popup.location.href = auth_url;
      else window.location.assign(auth_url);
      onNotice('LinkedIn qoşulma səhifəsi açıldı. İcazədən sonra statusu yeniləyin.');
    } catch (error) {
      if (popup && !popup.closed) popup.close();
      onError(error instanceof Error ? error.message : String(error));
    } finally { setConnecting(false); }
  }

  async function disconnect() {
    if (!companyId || !window.confirm('LinkedIn hesabını ayırmaq istəyirsiniz?')) return;
    setDisconnecting(true);
    onError('');
    try {
      setIntegration(await api.disconnectLinkedIn(companyId));
      onNotice('LinkedIn hesabı ayrıldı.');
    } catch (error) { onError(error instanceof Error ? error.message : String(error)); }
    finally { setDisconnecting(false); }
  }

  const connected = Boolean(integration?.connected);
  const label = integration?.display_name || integration?.username || integration?.linkedin_account_id || integration?.zernio_account_id || 'Hesab seçilməyib';

  return (
    <section className="space-y-6">
      <div className={cardClass}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <span className="rounded-[24px] bg-[#e4f5e9] p-4 text-[#15803d]"><Link2 size={28} /></span>
            <div><p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#18261d]">Sosial şəbəkə</p><h2 className="mt-2 text-2xl font-light text-[#18261d]">LinkedIn</h2><p className="mt-2 text-sm text-[#18261d]">Zernio vasitəsilə LinkedIn hesabını qoşun və təqvimdən post paylaşın.</p></div>
          </div>
          <span className="rounded-full bg-[#e4f5e9] px-4 py-2 text-sm font-semibold text-[#18261d]">{connected ? 'Qoşulub' : 'Qoşulmayıb'}</span>
        </div>
      </div>
      <div className={cardClass}>
        {loading ? <Spinner label="LinkedIn statusu yüklənir..." /> : (
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5">
              <h3 className="text-lg font-light text-[#18261d]">Qoşulmuş hesab</h3>
              <p className="mt-4 font-semibold text-[#18261d]">{label}</p>
              <p className="mt-2 text-sm text-[#18261d]">Qoşulma vaxtı: {formatDate(integration?.connected_at)}</p>
              <p className="mt-2 break-all text-xs text-[#18261d]">Zernio ID: {integration?.zernio_account_id || '—'}</p>
            </div>
            <div className="grid content-start gap-3 rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5">
              <button type="button" className={primaryButtonClass} onClick={connect} disabled={connecting || !companyId}>{connecting ? 'OAuth açılır...' : connected ? 'Yenidən qoş' : 'LinkedIn qoş'}</button>
              <button type="button" className={secondaryButtonClass} onClick={load} disabled={loading || !companyId}><RefreshCw size={16} /> Statusu yenilə</button>
              {connected && <button type="button" className={secondaryButtonClass} onClick={disconnect} disabled={disconnecting}><Unplug size={16} /> {disconnecting ? 'Ayrılır...' : 'Hesabı ayır'}</button>}
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
