import { useEffect, useState } from 'react';
import { Link2, RefreshCw, Unplug } from 'lucide-react';
import { api } from '../../api';
import type { LinkedInIntegration } from '../../api';
import { SocialIntegrationLayout } from '../../components/social/SocialIntegrationLayout';
import { primaryButtonClass, secondaryButtonClass } from '../../constants/styles';

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
      if (!auth_url) throw new Error('LinkedIn boş OAuth ünvanı qaytardı.');
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
  const accountContent = (
    <div className="grid gap-3 text-sm sm:grid-cols-2">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">Hesab</p>
        <p className="mt-1 font-semibold text-[#18261d]">{label}</p>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">Qoşulma vaxtı</p>
        <p className="mt-1 font-semibold text-[#18261d]">{formatDate(integration?.connected_at)}</p>
      </div>
      {integration?.linkedin_account_id && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">LinkedIn ID</p>
          <p className="mt-1 break-all font-semibold text-[#18261d]">{integration.linkedin_account_id}</p>
        </div>
      )}
    </div>
  );
  const actions = (
    <>
      <button type="button" className={primaryButtonClass} onClick={connect} disabled={connecting || !companyId}>
        {connecting ? 'OAuth açılır...' : connected ? 'Yenidən qoş' : 'LinkedIn qoş'}
      </button>
      <button type="button" className={secondaryButtonClass} onClick={() => void load()} disabled={loading || !companyId}>
        <RefreshCw size={16} /> Statusu yenilə
      </button>
      {connected && (
        <button type="button" className={secondaryButtonClass} onClick={disconnect} disabled={disconnecting}>
          <Unplug size={16} /> {disconnecting ? 'Ayrılır...' : 'Hesabı ayır'}
        </button>
      )}
    </>
  );

  return (
    <SocialIntegrationLayout
      icon={<Link2 size={28} />}
      title="LinkedIn"
      subtitle="LinkedIn hesabınızı qoşun və təqvimdən post paylaşın."
      connected={connected}
      connectedLabel="Qoşulub"
      disconnectedLabel="Qoşulmayıb"
      loading={loading}
      loadingLabel="LinkedIn statusu yüklənir..."
      accountTitle="Qoşulmuş hesab"
      accountContent={accountContent}
      actionsTitle="Əməliyyatlar"
      actions={actions}
    />
  );
}
