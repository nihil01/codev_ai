import { useEffect, useState } from 'react';
import { Music2, RefreshCw, Unplug } from 'lucide-react';
import { api } from '../../api';
import type { TikTokIntegration } from '../../api';
import { cardClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
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
    try {
      const status = await api.tiktokIntegration(companyId);
      setIntegration(status);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadStatus();
  }, [companyId]);

  async function connectTikTok() {
    if (!companyId) return;
    let oauthWindow: Window | null = null;
    try {
      oauthWindow = window.open('', '_blank');
      if (oauthWindow) {
        oauthWindow.document.write(`<p style="font-family: system-ui, sans-serif; padding: 24px;">${t('tiktok.prepareOAuth')}</p>`);
      }
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
    } finally {
      setConnecting(false);
    }
  }

  async function disconnectTikTok() {
    if (!companyId) return;
    if (!window.confirm(t('tiktok.disconnectConfirm'))) return;
    setDisconnecting(true);
    setError('');
    setNotice('');
    try {
      const status = await api.disconnectTikTok(companyId);
      setIntegration(status);
      setNotice(t('tiktok.disconnected'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDisconnecting(false);
    }
  }

  const connected = Boolean(integration?.connected);
  const accountLabel = integration?.display_name || integration?.username || integration?.tiktok_account_id || integration?.zernio_account_id || t('tiktok.noAccount');

  return (
    <section className="space-y-6">
      <div className={cardClass}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <span className="rounded-[24px] bg-[#e4f5e9] p-4 text-[#18261d]"><Music2 size={28} /></span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#18261d]">{t('tiktok.eyebrow')}</p>
              <h2 className="mt-2 text-2xl font-light tracking-[-0.02em] text-[#18261d]">TikTok</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#18261d]">
                {t('tiktok.subtitle')}
              </p>
            </div>
          </div>
          <span className={`rounded-full px-4 py-2 text-sm font-semibold ${connected ? 'bg-[#e4f5e9] text-[#18261d]' : 'bg-[#e4f5e9] text-[#18261d]'}`}>
            {connected ? t('common.connected') : t('common.notConnected')}
          </span>
        </div>
      </div>

      <div className={cardClass}>
        {loading ? (
          <Spinner label={t('tiktok.loading')} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5">
              <h3 className="text-lg font-light text-[#18261d]">{t('tiktok.account')}</h3>
              <div className="mt-4 grid gap-3 text-sm md:grid-cols-2">
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#18261d]">{t('tiktok.display')}</p>
                  <p className="mt-1 font-semibold text-[#18261d]">{accountLabel}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#18261d]">{t('tiktok.connectedAt')}</p>
                  <p className="mt-1 font-semibold text-[#18261d]">{formatDate(integration?.connected_at)}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#18261d]">{t('tiktok.zernioAccount')}</p>
                  <p className="mt-1 break-all font-semibold text-[#18261d]">{integration?.zernio_account_id || '—'}</p>
                </div>
                <div>
                  <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#18261d]">{t('tiktok.tiktokAccount')}</p>
                  <p className="mt-1 break-all font-semibold text-[#18261d]">{integration?.tiktok_account_id || '—'}</p>
                </div>
              </div>
              {!connected && <Alert type="info">{t('tiktok.connectHint')}</Alert>}
            </div>

            <div className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5">
              <h3 className="text-lg font-light text-[#18261d]">{t('tiktok.actions')}</h3>
              <div className="mt-4 grid gap-3">
                <button type="button" onClick={connectTikTok} disabled={connecting || !companyId} className={primaryButtonClass}>
                  {connecting ? t('tiktok.openingOAuth') : connected ? t('tiktok.reconnect') : t('tiktok.connect')}
                </button>
                <button type="button" onClick={loadStatus} disabled={loading || !companyId} className={secondaryButtonClass}>
                  <RefreshCw size={16} /> {t('tiktok.refresh')}
                </button>
                {connected && (
                  <button type="button" onClick={disconnectTikTok} disabled={disconnecting || !companyId} className="inline-flex items-center justify-center gap-2 rounded-[24px] border border-[#d8e8dd] bg-[#d8e8dd] px-5 py-3 text-sm font-semibold text-[#116932] transition hover:bg-[#d8e8dd] disabled:opacity-50">
                    <Unplug size={16} /> {disconnecting ? t('tiktok.disconnecting') : t('tiktok.disconnect')}
                  </button>
                )}
              </div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
