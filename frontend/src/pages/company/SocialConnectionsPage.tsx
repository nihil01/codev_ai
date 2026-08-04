import type { InstagramIntegration } from '../../api';
import { InstagramIcon, TikTokIcon, WhatsAppIcon } from '../../components/ui/SocialIcons';
import { InstagramSettings, type InstagramFormState } from './InstagramSettings';
import { LinkedInSettings } from './LinkedInSettings';
import { TikTokSettings } from './TikTokSettings';
import { WhatsAppSettings } from './WhatsAppSettings';

type Props = {
  companyId?: string | null;
  instagramForm: InstagramFormState;
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

export function SocialConnectionsPage(props: Props) {
  return (
    <section className="space-y-5">
      <div className="rounded-[28px] border border-[#e1ebe4] bg-white p-5 sm:p-7">
        <p className="text-xs font-bold uppercase tracking-[0.14em] text-[#15803d]">Bağlantılar</p>
        <h2 className="mt-1 text-2xl font-semibold text-[#18261d]">Sosial şəbəkə hesabları</h2>
        <p className="mt-2 text-sm text-[#708078]">Bütün sosial şəbəkə bağlantılarını bir səhifədən idarə edin.</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          <div className="flex items-center gap-3 rounded-[24px] bg-[#e4f5e9] p-4"><InstagramIcon size={22} /><span className="font-semibold">Instagram</span></div>
          <div className="flex items-center gap-3 rounded-[24px] bg-[#e4f5e9] p-4"><WhatsAppIcon size={22} /><span className="font-semibold">WhatsApp</span></div>
          <div className="flex items-center gap-3 rounded-[24px] bg-[#e4f5e9] p-4"><TikTokIcon size={22} /><span className="font-semibold">TikTok</span></div>
          <div className="flex items-center gap-3 rounded-[24px] bg-[#e4f5e9] p-4"><span className="grid h-[22px] w-[22px] place-items-center rounded bg-[#15803d] text-xs font-bold text-white">in</span><span className="font-semibold">LinkedIn</span></div>
        </div>
      </div>

      <InstagramSettings
        companyId={props.companyId}
        form={props.instagramForm}
        integration={props.instagramIntegration}
        instagramActivated={props.instagramActivated}
        instagramEnabled={props.instagramEnabled}
        connecting={props.connectingInstagram}
        toggling={props.togglingInstagram}
        unlinking={props.unlinkingInstagram}
        onConnect={props.onConnectInstagram}
        onToggleBot={props.onToggleInstagramBot}
        onUnlink={props.onUnlinkInstagram}
      />
      <WhatsAppSettings companyId={props.companyId || null} onActivationChange={props.onWhatsAppActivationChange} />
      <TikTokSettings companyId={props.companyId} setError={props.setError} setNotice={props.setNotice} />
      <LinkedInSettings companyId={props.companyId} onError={props.setError} onNotice={props.setNotice} />
    </section>
  );
}
