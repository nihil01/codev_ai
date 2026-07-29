import { useEffect, useRef, useState } from 'react';
import { MessageCircle, RefreshCw } from 'lucide-react';
import { api, type WhatsAppCloudIntegration } from '../../api';
import { SocialIntegrationLayout } from '../../components/social/SocialIntegrationLayout';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { dangerButtonClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { useI18n } from '../../i18n';

interface WhatsappProps {
  companyId: string | null;
  onActivationChange?: (activated: boolean) => void;
}

function connectedLabel(integration: WhatsAppCloudIntegration | null, fallback: string): string {
  if (!integration?.connected) return fallback;
  return integration.verified_name || integration.display_phone_number || integration.phone_number_id || integration.waba_id || 'WhatsApp account';
}

export function WhatsAppSettings({ companyId, onActivationChange }: WhatsappProps) {
  const { t } = useI18n();
  const companyIdRef = useRef<string | null>(companyId);
  const [integration, setIntegration] = useState<WhatsAppCloudIntegration | null>(null);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState(false);
  const [disconnecting, setDisconnecting] = useState(false);
  const [notice, setNotice] = useState('');
  const [error, setError] = useState('');
  const connected = Boolean(integration?.connected);
  const busy = loading || connecting || disconnecting;

  useEffect(() => { companyIdRef.current = companyId; }, [companyId]);

  async function refreshWhatsAppStatus(targetCompanyId?: string | null) {
    const currentCompanyId = targetCompanyId ?? companyIdRef.current;
    if (!currentCompanyId) {
      setIntegration(null);
      onActivationChange?.(false);
      return;
    }
    setLoading(true);
    setError('');
    try {
      const status = await api.getWhatsAppCloudStatus(currentCompanyId);
      setIntegration(status);
      onActivationChange?.(Boolean(status.connected));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void refreshWhatsAppStatus(companyId); }, [companyId]);

  async function connectWhatsApp() {
    const currentCompanyId = companyIdRef.current;
    if (!currentCompanyId) {
      setError(t('common.companyIdMissing'));
      return;
    }
    let oauthWindow: Window | null = null;
    try {
      oauthWindow = window.open('', '_blank');
      if (oauthWindow) oauthWindow.document.write(`<p style="font-family: system-ui, sans-serif; padding: 24px;">${t('whatsapp.prepareLink')}...</p>`);
    } catch {
      oauthWindow = null;
    }
    setConnecting(true);
    setError('');
    setNotice('');
    try {
      const { auth_url } = await api.connectWhatsAppCloud(currentCompanyId);
      if (!auth_url) throw new Error(t('dashboard.emptyOAuthUrl'));
      if (oauthWindow) oauthWindow.location.href = auth_url;
      else window.location.assign(auth_url);
      setNotice(t('whatsapp.oauthOpened'));
    } catch (err) {
      if (oauthWindow && !oauthWindow.closed) oauthWindow.close();
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnecting(false);
    }
  }

  async function disconnectWhatsApp() {
    const currentCompanyId = companyIdRef.current;
    if (!currentCompanyId) {
      setError(t('common.companyIdMissing'));
      return;
    }
    if (!window.confirm(t('whatsapp.confirmUnlink'))) return;
    setDisconnecting(true);
    setError('');
    setNotice('');
    try {
      setIntegration(await api.disconnectWhatsAppCloud(currentCompanyId));
      onActivationChange?.(false);
      setNotice(t('whatsapp.unlinked'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDisconnecting(false);
    }
  }

  const accountContent = (
    <div className="grid gap-3 text-sm sm:grid-cols-2">
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">{t('whatsapp.account')}</p>
        <p className="mt-1 break-all font-semibold text-[#18261d]">{connectedLabel(integration, t('common.notConnected'))}</p>
      </div>
      <div>
        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">{t('whatsapp.accountId')}</p>
        <p className="mt-1 break-all font-semibold text-[#18261d]">{integration?.waba_id || '—'}</p>
      </div>
      {integration?.display_phone_number && (
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">Telefon</p>
          <p className="mt-1 font-semibold text-[#18261d]">{integration.display_phone_number}</p>
        </div>
      )}
    </div>
  );

  const actions = (
    <>
      {!connected && (
        <button type="button" className={primaryButtonClass} onClick={connectWhatsApp} disabled={busy || !companyId}>
          {connecting ? <Spinner label={t('whatsapp.prepareLink')} /> : t('whatsapp.connect')}
        </button>
      )}
      <button type="button" className={secondaryButtonClass} onClick={() => void refreshWhatsAppStatus()} disabled={busy || !companyId}>
        <RefreshCw size={16} /> {t('common.refresh')}
      </button>
      {connected && (
        <button type="button" className={dangerButtonClass} onClick={disconnectWhatsApp} disabled={busy}>
          {disconnecting ? <Spinner label={t('whatsapp.unlinking')} /> : t('whatsapp.unlink')}
        </button>
      )}
    </>
  );

  return (
    <SocialIntegrationLayout
      icon={<MessageCircle size={28} />}
      title="WhatsApp"
      subtitle={t('whatsapp.subtitle')}
      connected={connected}
      connectedLabel={t('whatsapp.connected')}
      disconnectedLabel={t('whatsapp.notConnected')}
      loading={loading}
      loadingLabel={t('whatsapp.checking')}
      accountTitle={t('whatsapp.account')}
      accountContent={accountContent}
      actionsTitle={connected ? t('whatsapp.manageTitle') : t('whatsapp.missingTitle')}
      actions={actions}
      messages={<>{error && <Alert type="error">{error}</Alert>}{notice && <Alert type="success">{notice}</Alert>}</>}
    />
  );
}
