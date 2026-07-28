import { useEffect, useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { api, type WhatsAppCloudIntegration } from '../../api';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { cardClass, dangerButtonClass, primaryButtonClass } from '../../constants/styles';
import { useI18n } from '../../i18n';

interface WhatsappProps {
  companyId: string | null;
  onActivationChange?: (activated: boolean) => void;
}

function connectedLabel(integration: WhatsAppCloudIntegration | null, fallback: string): string {
  if (!integration?.connected) return fallback;
  return (
    integration.verified_name ||
    integration.display_phone_number ||
    integration.phone_number_id ||
    integration.waba_id ||
    'WhatsApp account'
  );
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

  useEffect(() => {
    companyIdRef.current = companyId;
  }, [companyId]);

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

  useEffect(() => {
    void refreshWhatsAppStatus(companyId);
  }, [companyId]);

  async function connectWhatsApp() {
    const currentCompanyId = companyIdRef.current;

    if (!currentCompanyId) {
      setError(t('common.companyIdMissing'));
      return;
    }

    let oauthWindow: Window | null = null;
    try {
      oauthWindow = window.open('', '_blank');
      if (oauthWindow) {
        oauthWindow.document.write(`<p style="font-family: system-ui, sans-serif; padding: 24px;">${t('whatsapp.prepareLink')}...</p>`);
      }
    } catch {
      oauthWindow = null;
    }

    setConnecting(true);
    setError('');
    setNotice('');

    try {
      const { auth_url } = await api.connectWhatsAppCloud(currentCompanyId);
      if (!auth_url) {
        throw new Error(t('dashboard.emptyOAuthUrl'));
      }

      if (oauthWindow) {
        oauthWindow.location.href = auth_url;
      } else {
        window.location.assign(auth_url);
      }

      setNotice(t('whatsapp.oauthOpened'));
    } catch (err) {
      if (oauthWindow && !oauthWindow.closed) {
        oauthWindow.close();
      }
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

    const confirmed = window.confirm(t('whatsapp.confirmUnlink'));
    if (!confirmed) return;

    setDisconnecting(true);
    setError('');
    setNotice('');

    try {
      const disconnected = await api.disconnectWhatsAppCloud(currentCompanyId);
      setIntegration(disconnected);
      onActivationChange?.(false);
      setNotice(t('whatsapp.unlinked'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDisconnecting(false);
    }
  }

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className={cardClass}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-light text-[#0f3e17]">{t('whatsapp.title')}</h2>
        </div>

        <span
          className={`w-fit rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] ${
            connected ? 'bg-[#e1f4df] text-[#0f3e17]' : 'bg-[#b1dbb8] text-[#0f3e17]'
          }`}
        >
          {connected ? t('whatsapp.connected') : t('whatsapp.notConnected')}
        </span>
      </div>

      {error && <Alert type="error">{error}</Alert>}
      {notice && <Alert type="success">{notice}</Alert>}

      <div className="mt-5 rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-5">
        <div className="grid gap-3 text-sm text-[#222222] sm:grid-cols-3">
          <div>
            <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#222222]">{t('common.status')}</span>
            <span className="mt-1 block font-semibold text-[#0f3e17]">
              {loading ? t('whatsapp.checking') : connected ? t('whatsapp.connectedStatus') : t('common.notConnected')}
            </span>
          </div>

          <div>
            <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#222222]">{t('whatsapp.account')}</span>
            <span className="mt-1 block break-all font-semibold text-[#0f3e17]">{connectedLabel(integration, t('common.notConnected'))}</span>
          </div>

          <div>
            <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#222222]">{t('whatsapp.accountId')}</span>
            <span className="mt-1 block break-all font-semibold text-[#0f3e17]">{integration?.waba_id || '—'}</span>
          </div>
        </div>
      </div>

      {!connected && (
        <div className="mt-5 rounded-[14px] border border-[#efeeeb] bg-[#b1dbb8] p-5 text-[#0f3e17]">
          <h3 className="text-lg font-light">{t('whatsapp.missingTitle')}</h3>

          <button
            type="button"
            className={`${primaryButtonClass} mt-4`}
            onClick={connectWhatsApp}
            disabled={busy || !companyId}
          >
            {connecting ? <Spinner label={t('whatsapp.prepareLink')} /> : t('whatsapp.connect')}
          </button>
        </div>
      )}

      {connected && (
        <div className="mt-5 grid gap-4 rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-5 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <h3 className="text-lg font-light text-[#0f3e17]">{t('whatsapp.manageTitle')}</h3>
          </div>

          <button type="button" className={dangerButtonClass} onClick={disconnectWhatsApp} disabled={busy}>
            {disconnecting ? <Spinner label={t('whatsapp.unlinking')} /> : t('whatsapp.unlink')}
          </button>
        </div>
      )}
    </motion.section>
  );
}
