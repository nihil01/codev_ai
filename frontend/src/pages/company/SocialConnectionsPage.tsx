import { useEffect, useState } from 'react';
import { Check, Link2, Loader2, Unlink, X } from 'lucide-react';
import type { InstagramIntegration } from '../../api';
import { api } from '../../api';
import { InstagramIcon, TikTokIcon, WhatsAppIcon } from '../../components/ui/SocialIcons';
import { cardClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';

type Props = {
  companyId?: string | null;
  instagramForm: { external_account_id: string; display_name: string };
  instagramIntegration: InstagramIntegration | null;
  instagramActivated: boolean;
  instagramEnabled: boolean;
  connectingInstagram: boolean;
  togglingInstagram: boolean;
  unlinkingInstagram: boolean;
  onConnectInstagram: () => void;
  onToggleInstagramBot: () => void;
  onUnlinkInstagram: () => void;
  onWhatsAppActivationChange: (activated: boolean) => void;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
};

type ConnectionStatus = 'connected' | 'disconnected' | 'loading';

type ConnectionCardProps = {
  name: string;
  icon: React.ReactNode;
  status: ConnectionStatus;
  description: string;
  onConnect?: () => void;
  onDisconnect?: () => void;
  connecting?: boolean;
  children?: React.ReactNode;
};

function ConnectionCard({ name, icon, status, description, onConnect, onDisconnect, connecting, children }: ConnectionCardProps) {
  return (
    <div className={`${cardClass} space-y-4`}>
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-12 w-12 items-center justify-center rounded-2xl bg-[#e4f5e9] text-[#15803d]">
            {icon}
          </div>
          <div>
            <h3 className="text-base font-semibold text-[#18261d]">{name}</h3>
            <p className="text-xs text-[#708078]">{description}</p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {status === 'connected' ? (
            <span className="flex items-center gap-1.5 rounded-full bg-[#e4f5e9] px-3 py-1.5 text-xs font-semibold text-[#15803d]">
              <Check size={14} /> Qoşulub
            </span>
          ) : status === 'loading' ? (
            <span className="flex items-center gap-1.5 rounded-full bg-[#f0f4f2] px-3 py-1.5 text-xs font-semibold text-[#708078]">
              <Loader2 size={14} className="animate-spin" /> Yüklənir
            </span>
          ) : (
            <span className="flex items-center gap-1.5 rounded-full bg-[#f0f4f2] px-3 py-1.5 text-xs font-semibold text-[#708078]">
              <X size={14} /> Qoşulmayıb
            </span>
          )}
        </div>
      </div>

      {children}

      <div className="flex gap-2">
        {status === 'connected' ? (
          <>
            {onDisconnect && (
              <button type="button" onClick={onDisconnect} disabled={connecting}
                className="inline-flex items-center gap-2 rounded-xl border border-red-200 px-4 py-2.5 text-sm font-semibold text-red-600 transition hover:bg-red-50 disabled:opacity-50">
                <Unlink size={16} /> Ayır
              </button>
            )}
          </>
        ) : (
          onConnect && (
            <button type="button" onClick={onConnect} disabled={connecting}
              className={`${primaryButtonClass} !rounded-xl !px-4 !py-2.5 !text-sm`}>
              <Link2 size={16} /> {connecting ? 'Qoşulur...' : 'Qoş'}
            </button>
          )
        )}
      </div>
    </div>
  );
}

export function SocialConnectionsPage(props: Props) {
  const { companyId, setError, setNotice } = props;

  // LinkedIn state
  const [linkedinStatus, setLinkedinStatus] = useState<ConnectionStatus>('loading');
  const [linkedinAccount, setLinkedinAccount] = useState<{ display_name?: string; connected_at?: string } | null>(null);
  const [connectingLinkedin, setConnectingLinkedin] = useState(false);

  // TikTok state
  const [tiktokStatus, setTiktokStatus] = useState<ConnectionStatus>('loading');
  const [tiktokAccount, setTiktokAccount] = useState<{ display_name?: string; connected_at?: string } | null>(null);
  const [connectingTiktok, setConnectingTiktok] = useState(false);

  useEffect(() => {
    if (!companyId) return;
    let cancelled = false;

    Promise.allSettled([
      api.linkedinIntegration(companyId),
      api.tiktokIntegration(companyId),
    ]).then(([linkedinResult, tiktokResult]) => {
      if (cancelled) return;

      if (linkedinResult.status === 'fulfilled' && linkedinResult.value) {
        const data = linkedinResult.value as any;
        if (data.status === 'connected') {
          setLinkedinStatus('connected');
          setLinkedinAccount({ display_name: data.display_name, connected_at: data.connected_at });
        } else {
          setLinkedinStatus('disconnected');
        }
      } else {
        setLinkedinStatus('disconnected');
      }

      if (tiktokResult.status === 'fulfilled' && tiktokResult.value) {
        const data = tiktokResult.value as any;
        if (data.status === 'connected') {
          setTiktokStatus('connected');
          setTiktokAccount({ display_name: data.display_name, connected_at: data.connected_at });
        } else {
          setTiktokStatus('disconnected');
        }
      } else {
        setTiktokStatus('disconnected');
      }
    });

    return () => { cancelled = true; };
  }, [companyId]);

  async function connectLinkedin() {
    if (!companyId) return;
    setConnectingLinkedin(true);
    setError('');
    try {
      const { auth_url } = await api.connectLinkedIn(companyId);
      if (auth_url) window.open(auth_url, '_blank');
      setNotice('LinkedIn OAuth açıldı. Qoşulmanı tamamlayın.');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnectingLinkedin(false);
    }
  }

  async function disconnectLinkedin() {
    if (!companyId || !window.confirm('LinkedIn qoşulmasını ayırmaq istəyirsiniz?')) return;
    setConnectingLinkedin(true);
    setError('');
    try {
      await api.disconnectLinkedIn(companyId);
      setLinkedinStatus('disconnected');
      setLinkedinAccount(null);
      setNotice('LinkedIn ayrıldı');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnectingLinkedin(false);
    }
  }

  async function connectTiktok() {
    if (!companyId) return;
    setConnectingTiktok(true);
    setError('');
    try {
      const { auth_url } = await api.connectTikTok(companyId);
      if (auth_url) window.open(auth_url, '_blank');
      setNotice('TikTok OAuth açıldı. Qoşulmanı tamamlayın.');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnectingTiktok(false);
    }
  }

  async function disconnectTiktok() {
    if (!companyId || !window.confirm('TikTok qoşulmasını ayırmaq istəyirsiniz?')) return;
    setConnectingTiktok(true);
    setError('');
    try {
      await api.disconnectTikTok(companyId);
      setTiktokStatus('disconnected');
      setTiktokAccount(null);
      setNotice('TikTok ayrıldı');
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnectingTiktok(false);
    }
  }

  // Instagram status
  const igStatus: ConnectionStatus = props.instagramActivated ? 'connected' : 'loading';
  const igEnabledStatus = props.instagramEnabled ? 'Aktiv' : 'Söndürülüb';

  // WhatsApp status
  const wpStatus: ConnectionStatus = 'loading'; // Will be updated by WhatsAppSettings

  return (
    <section className="space-y-5">
      <div className={cardClass}>
        <div className="flex items-center gap-3">
          <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#15803d]"><Link2 size={22} /></span>
          <div>
            <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#15803d]">Bağlantılar</p>
            <h2 className="mt-1 text-2xl font-semibold text-[#18261d]">Sosial şəbəkə hesabları</h2>
            <p className="mt-1 text-sm text-[#708078]">Bütün sosial şəbəkə bağlantılarını bir səhifədən idarə edin.</p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {/* Instagram */}
        <ConnectionCard
          name="Instagram"
          icon={<InstagramIcon size={24} />}
          status={igStatus}
          description="Instagram bot inteqrasiyası"
          onConnect={props.onConnectInstagram}
          onDisconnect={props.onUnlinkInstagram}
          connecting={props.connectingInstagram}
        >
          {props.instagramActivated && (
            <div className="flex items-center justify-between rounded-xl border border-[#e1ebe4] bg-[#f8faf9] p-3">
              <div>
                <p className="text-xs font-semibold text-[#708078]">Bot statusu</p>
                <p className="text-sm font-semibold text-[#18261d]">{igEnabledStatus}</p>
              </div>
              <button type="button" onClick={props.onToggleInstagramBot} disabled={props.togglingInstagram}
                className={`${secondaryButtonClass} !rounded-xl !px-3 !py-1.5 !text-xs`}>
                {props.instagramEnabled ? 'Söndür' : 'Yandır'}
              </button>
            </div>
          )}
        </ConnectionCard>

        {/* WhatsApp */}
        <ConnectionCard
          name="WhatsApp"
          icon={<WhatsAppIcon size={24} />}
          status={wpStatus}
          description="WhatsApp Cloud API inteqrasiyası"
        />

        {/* LinkedIn */}
        <ConnectionCard
          name="LinkedIn"
          icon={<span className="grid h-6 w-6 place-items-center rounded bg-[#15803d] text-xs font-bold text-white">in</span>}
          status={linkedinStatus}
          description="LinkedIn paylaşım inteqrasiyası"
          onConnect={connectLinkedin}
          onDisconnect={disconnectLinkedin}
          connecting={connectingLinkedin}
        >
          {linkedinAccount && (
            <div className="rounded-xl border border-[#e1ebe4] bg-[#f8faf9] p-3">
              <p className="text-xs font-semibold text-[#708078]">Hesab</p>
              <p className="text-sm font-semibold text-[#18261d]">{linkedinAccount.display_name}</p>
              {linkedinAccount.connected_at && (
                <p className="mt-1 text-xs text-[#708078]">Qoşulma: {new Date(linkedinAccount.connected_at).toLocaleDateString('az-AZ')}</p>
              )}
            </div>
          )}
        </ConnectionCard>

        {/* TikTok */}
        <ConnectionCard
          name="TikTok"
          icon={<TikTokIcon size={24} />}
          status={tiktokStatus}
          description="TikTok paylaşım inteqrasiyası"
          onConnect={connectTiktok}
          onDisconnect={disconnectTiktok}
          connecting={connectingTiktok}
        >
          {tiktokAccount && (
            <div className="rounded-xl border border-[#e1ebe4] bg-[#f8faf9] p-3">
              <p className="text-xs font-semibold text-[#708078]">Hesab</p>
              <p className="text-sm font-semibold text-[#18261d]">{tiktokAccount.display_name}</p>
              {tiktokAccount.connected_at && (
                <p className="mt-1 text-xs text-[#708078]">Qoşulma: {new Date(tiktokAccount.connected_at).toLocaleDateString('az-AZ')}</p>
              )}
            </div>
          )}
        </ConnectionCard>
      </div>
    </section>
  );
}
