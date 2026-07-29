import { motion } from 'framer-motion';
import type { InstagramIntegration } from '../../api';
import { cardClass, dangerButtonClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
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

  const profileName = integration?.display_name || form.display_name || null;
  const profileUsername = integration?.username || null;
  const profileUserId = integration?.user_id || form.external_account_id || null;
  const accountLabel = profileName || profileUsername || profileUserId || t('instagram.notConnected');
  const statusText = !instagramActivated
    ? t('instagram.notConnected')
    : instagramEnabled
      ? t('instagram.statusConnectedActive')
      : t('instagram.statusConnectedOff');

  return (
    <motion.section
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.05 }}
      className={cardClass}
    >
      <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h2 className="text-xl font-light text-[#18261d]">{t('instagram.title')}</h2>
        </div>

        <div className="flex flex-wrap gap-2">
          <span
            className={`w-fit rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] ${
              instagramActivated ? 'bg-[#e4f5e9] text-[#18261d]' : 'bg-[#ffffff] text-[#18261d]'
            }`}
          >
            {instagramActivated ? t('instagram.connected') : t('instagram.notConnected')}
          </span>

          <span
            className={`w-fit rounded-full px-4 py-1.5 text-xs font-semibold uppercase tracking-[0.08em] ${
              !instagramActivated
                ? 'bg-[#e4f5e9] text-[#18261d]'
                : instagramEnabled
                  ? 'bg-[#d8e8dd] text-[#18261d]'
                  : 'bg-[#e4f5e9] text-[#18261d]'
            }`}
          >
            {!instagramActivated ? t('instagram.botUnavailable') : instagramEnabled ? t('instagram.botActive') : t('instagram.botOff')}
          </span>
        </div>
      </div>

      <div className="mt-5 rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5">
        <div className="grid gap-3 text-sm text-[#18261d] sm:grid-cols-3">

          <div>
            <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#18261d]">{t('common.status')}</span>
            <span className="mt-1 block font-semibold text-[#18261d]">{statusText}</span>
          </div>

          <div>
            <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#18261d]">{t('instagram.account')}</span>
            <span className="mt-1 block break-all font-semibold text-[#18261d]">{accountLabel}</span>
          </div>

          <div>
            <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#18261d]">{t('instagram.profileId')}</span>
            <span className="mt-1 block break-all font-semibold text-[#18261d]">{profileUserId || '—'}</span>
          </div>
        </div>

        {instagramActivated && (
          <div className="mt-5 flex flex-col gap-4 rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-4 sm:flex-row sm:items-center">
            {integration?.profile_picture_url && (
              <img
                src={integration.profile_picture_url}
                alt={profileUsername ? `@${profileUsername}` : t('instagram.profileName')}
                className="h-16 w-16 rounded-[24px] object-cover ring-1 ring-[#e1ebe4]"
              />
            )}

            <div className="grid flex-1 gap-3 text-sm sm:grid-cols-3">
              <div>
                <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#18261d]">{t('instagram.profileName')}</span>
                <span className="mt-1 block break-all font-semibold text-[#18261d]">{profileName || '—'}</span>
              </div>

              <div>
                <span className="block text-xs font-semibold uppercase tracking-[0.06em] text-[#18261d]">Username</span>
                <span className="mt-1 block break-all font-semibold text-[#18261d]">
                  {profileUsername ? `@${profileUsername}` : '—'}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>

      {!instagramActivated && (
        <div className="mt-5 rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5 text-[#18261d]">
          <h3 className="text-lg font-light">{t('instagram.missingTitle')}</h3>

          <button
            type="button"
            className={`${primaryButtonClass} mt-4`}
            onClick={onConnect}
            disabled={busy || !companyId}
          >
            {connecting ? <Spinner label={t('instagram.prepareLink')} /> : t('instagram.connect')}
          </button>

          {!companyId && (
            <p className="mt-3 text-xs font-semibold text-[#18261d]">{t('instagram.noCompany')}</p>
          )}
        </div>
      )}

      {instagramActivated && (
        <div className="mt-5 grid gap-4 rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5 md:grid-cols-[1fr_auto] md:items-center">
          <div>
            <h3 className="text-lg font-light text-[#18261d]">{t('instagram.manageTitle')}</h3>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row md:flex-col">
            <button type="button" className={secondaryButtonClass} onClick={onToggleBot} disabled={busy}>
              {toggling ? <Spinner label={t('instagram.statusChanging')} /> : instagramEnabled ? t('instagram.disableBot') : t('instagram.enableBot')}
            </button>

            <button type="button" className={dangerButtonClass} onClick={onUnlink} disabled={busy}>
              {unlinking ? <Spinner label={t('instagram.unlinking')} /> : t('instagram.unlink')}
            </button>
          </div>
        </div>
      )}
    </motion.section>
  );
}
