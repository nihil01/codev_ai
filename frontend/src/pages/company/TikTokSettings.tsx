import { useEffect, useState } from 'react';
import { Music2, RefreshCw, Unplug } from 'lucide-react';
import { api } from '../../api';
import type { TikTokIntegration } from '../../api';
import { SocialIntegrationLayout } from '../../components/social/SocialIntegrationLayout';
import { Alert } from '../../components/ui/Alert';
import { primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { useI18n } from '../../i18n';

type TikTokSettingsProps = {
  companyId: string | null | undefined;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
};

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Intl.DateTimeFormat(undefined, { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(value));
}

export function TikTokSettings({ companyId, setError, setNotice }: TikTokSettingsProps) {
  const { t } = useI18n();
  const [integration, setIntegration] = useState<TikTokIntegration | null>(null);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);

  async function loadStatus() {
    if (!companyId) return;
    setLoading(true);
    setError('');
    try { setIntegration(await api.tiktokIntegration(companyId)); }
    catch (err) { setError(err instanceof Error ? err.message : String(err)); }
    finally { setLoading(false); }
  }

  useEffect(() => { void loadStatus(); }, [companyId]);

  async function connectTikTok() {
    if (!companyId) return;
    let oauthWindow: Window | null = null;
    try {
      oauthWindow = window.open('', '_blank');
      if (oauthWindow) oauthWindow.document.write(`<p style="font-family: system-ui, sans-serif; padding: 24px;">${t('tiktok.prepareOAuth')}</p>`);
    } catch {
      oauthWindow = null;
    }
    setConnecting(true);
    setError('');
    setNotice('');
    try {
      const { auth_url } = await api.connectTikTok(companyId);
      if (!auth_url) throw new Error(t('tiktok.emptyOAuth'));
      if (oauthWindow) oauthWindow.location.href = auth_url;
      else window.location.assign(auth_url);
      setNotice(t('tiktok.oauthOpened'));
    } catch (err) {
      if (oauthWindow && !oauthWindow.closed) oauthWindow.close();
      setError(err instanceof Error ? err.message : String(err));
    } finally { setConnecting(false); }
  }

  async function disconnectTikTok() {
    if (!companyId || !window.confirm(t('tiktok.disconnectConfirm'))) return;
    setDisconnecting(true);
    setError('');
    setNotice('');
    try {
      setIntegration(await api.disconnectTikTok(companyId));
      setNotice(t('tiktok.disconnected'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally { setDisconnecting(false); }
  }

  const connected = Boolean(integration?.connected);
  const accountLabel = integration?.display_name || integration?.username || integration?.tiktok_account_id || integration?.zernio_account_id || t('tiktok.noAccount');
  const accountContent = (
    <div className="space-y-4">
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">{t('tiktok.display')}</p>
          <p className="mt-1 font-semibold text-[#18261d]">{accountLabel}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">{t('tiktok.connectedAt')}</p>
          <p className="mt-1 font-semibold text-[#18261d]">{formatDate(integration?.connected_at)}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">{t('tiktok.tiktokAccount')}</p>
          <p className="mt-1 break-all font-semibold text-[#18261d]">{integration?.tiktok_account_id || '—'}</p>
        </div>
      </div>
      {!connected && <Alert type="info">{t('tiktok.connectHint')}</Alert>}
    </div>
  );

  const actions = (
    <>
      <button type="button" onClick={connectTikTok} disabled={connecting || !companyId} className={primaryButtonClass}>
        {connecting ? t('tiktok.openingOAuth') : connected ? t('tiktok.reconnect') : t('tiktok.connect')}
      </button>
      <button type="button" onClick={() => void loadStatus()} disabled={loading || !companyId} className={secondaryButtonClass}>
        <RefreshCw size={16} /> {t('tiktok.refresh')}
      </button>
      {connected && (
        <button type="button" onClick={disconnectTikTok} disabled={disconnecting || !companyId} className={secondaryButtonClass}>
          <Unplug size={16} /> {disconnecting ? t('tiktok.disconnecting') : t('tiktok.disconnect')}
        </button>
      )}
    </>
  );

  return (
    <SocialIntegrationLayout
      icon={<Music2 size={28} />}
      title="TikTok"
      subtitle={t('tiktok.subtitle')}
      connected={connected}
      connectedLabel={t('common.connected')}
      disconnectedLabel={t('common.notConnected')}
      loading={loading}
      loadingLabel={t('tiktok.loading')}
      accountTitle={t('tiktok.account')}
      accountContent={accountContent}
      actionsTitle={t('tiktok.actions')}
      actions={actions}
    />
  );
}
