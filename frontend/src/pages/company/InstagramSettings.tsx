import { Camera } from 'lucide-react';
import type { InstagramIntegration } from '../../api';
import { dangerButtonClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { SocialIntegrationLayout } from '../../components/social/SocialIntegrationLayout';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

export type InstagramFormState = {
  external_account_id: string;
  display_name: string;
};

type InstagramSettingsProps = {
  companyId?: string | null;
  form: InstagramFormState;
  integration: InstagramIntegration | null;
  instagramActivated: boolean;
  instagramEnabled: boolean;
  connecting: boolean;
  toggling: boolean;
  unlinking: boolean;
  onConnect: () => void;
  onToggleBot: () => void;
  onUnlink: () => void;
};

export function InstagramSettings({
  companyId,
  form,
  integration,
  instagramActivated,
  instagramEnabled,
  connecting,
  toggling,
  unlinking,
  onConnect,
  onToggleBot,
  onUnlink,
}: InstagramSettingsProps) {
  const { t } = useI18n();
  const busy = connecting || toggling || unlinking;
  const profileName = instagramActivated ? integration?.display_name || form.display_name || null : null;
  const profileUsername = instagramActivated ? integration?.username || null : null;
  const profileUserId = instagramActivated ? integration?.user_id || form.external_account_id || null : null;
  const accountLabel = profileName || profileUsername || profileUserId || t('instagram.notConnected');
  const botStatus = !instagramActivated
    ? t('instagram.botUnavailable')
    : instagramEnabled
      ? t('instagram.botActive')
      : t('instagram.botOff');

  const accountContent = (
    <div className="space-y-4">
      {integration?.profile_picture_url && (
        <div className="flex items-center gap-4">
          <img
            src={integration.profile_picture_url}
            alt={profileUsername ? `@${profileUsername}` : t('instagram.profileName')}
            className="h-16 w-16 rounded-[24px] object-cover ring-1 ring-[#e1ebe4]"
          />
          <div>
            <p className="font-semibold text-[#18261d]">{accountLabel}</p>
            {profileUsername && <p className="mt-1 text-sm text-[#708078]">@{profileUsername}</p>}
          </div>
        </div>
      )}
      <div className="grid gap-3 text-sm sm:grid-cols-2">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">{t('instagram.account')}</p>
          <p className="mt-1 break-all font-semibold text-[#18261d]">{accountLabel}</p>
        </div>
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">Bot</p>
          <p className="mt-1 font-semibold text-[#18261d]">{botStatus}</p>
        </div>
        {instagramActivated && (
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#708078]">{t('instagram.profileId')}</p>
            <p className="mt-1 break-all font-semibold text-[#18261d]">{profileUserId || '—'}</p>
          </div>
        )}
      </div>
    </div>
  );

  const actions = instagramActivated ? (
    <>
      <button type="button" className={secondaryButtonClass} onClick={onToggleBot} disabled={busy}>
        {toggling ? <Spinner label={t('instagram.statusChanging')} /> : instagramEnabled ? t('instagram.disableBot') : t('instagram.enableBot')}
      </button>
      <button type="button" className={dangerButtonClass} onClick={onUnlink} disabled={busy}>
        {unlinking ? <Spinner label={t('instagram.unlinking')} /> : t('instagram.unlink')}
      </button>
    </>
  ) : (
    <>
      <button type="button" className={primaryButtonClass} onClick={onConnect} disabled={busy || !companyId}>
        {connecting ? <Spinner label={t('instagram.prepareLink')} /> : t('instagram.connect')}
      </button>
      {!companyId && <p className="text-xs font-semibold text-[#18261d]">{t('instagram.noCompany')}</p>}
    </>
  );

  return (
    <SocialIntegrationLayout
      icon={<Camera size={28} />}
      title="Instagram"
      subtitle={t('instagram.subtitle')}
      connected={instagramActivated}
      connectedLabel={t('instagram.connected')}
      disconnectedLabel={t('instagram.notConnected')}
      accountTitle={t('instagram.account')}
      accountContent={accountContent}
      actionsTitle={instagramActivated ? t('instagram.manageTitle') : t('instagram.missingTitle')}
      actions={actions}
    />
  );
}
