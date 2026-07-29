import { useEffect, useMemo, useState } from 'react';
import type { FormEvent } from 'react';
import { motion } from 'framer-motion';
import {
  Bell,
  Building2,
  CheckCircle2,
  CameraIcon,
  KeyRound,
  MessageCircle,
  Send,
  Settings2,
  Store,
} from 'lucide-react';
import { api } from '../../api';
import type {
  AutomationSettings,
  BusinessSettings,
  BusinessType,
  Channel,
  TelegramStatus,
} from '../../api';
import { cardClass, inputClass, primaryButtonClass } from '../../constants/styles';
import { Field } from '../../components/ui/Field';
import { InfoRow } from '../../components/ui/InfoRow';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

const businessTypeValues: BusinessType[] = [
  'confectionery',
  'flower_shop',
  'cafe_restaurant',
  'other',
];

const defaultAutomationSettings: AutomationSettings = {
  tenant_id: '',
  client_reminder_enabled: false,
  client_reminder_delay_minutes: 120,
  client_reminder_message:
      'Здравствуйте! Хотели мягко напомнить о нашем диалоге. Если вопрос ещё актуален — напишите, мы рядом и поможем.',
  autoposting_enabled: false,
  instagram_comments_enabled: true,
  linkedin_connected: false,
  tiktok_connected: false,
  content_calendar_enabled: false,
  flower_price_adaptation_enabled: false,
  default_event_reminder_hours: 24,
};

type CompanyInfoProps = {
  companyId?: string | null;
  email: string;
  instagramChannel?: Channel;
  businessSettings?: BusinessSettings | null;
  onBusinessSettingsChange?: (settings: BusinessSettings) => void;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

export function CompanyInfo({
                              companyId,
                              email,
                              instagramChannel,
                              businessSettings,
                              onBusinessSettingsChange,
                              onError,
                              onNotice,
                            }: CompanyInfoProps) {
  const { t } = useI18n();

  const [businessType, setBusinessType] = useState<BusinessType>('other');
  const [autoDiscountEnabled, setAutoDiscountEnabled] = useState(false);
  const [shelfLifeHours, setShelfLifeHours] = useState('');
  const [discountAfterHours, setDiscountAfterHours] = useState('');
  const [discountPercent, setDiscountPercent] = useState('0');
  const [savingPreferences, setSavingPreferences] = useState(false);

  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

  const [telegramStatus, setTelegramStatus] = useState<TelegramStatus | null>(null);
  const [telegramLoading, setTelegramLoading] = useState(false);

  const [automationSettings, setAutomationSettings] = useState<AutomationSettings>(defaultAutomationSettings);
  const [automationLoading, setAutomationLoading] = useState(false);
  const [savingAutomation, setSavingAutomation] = useState(false);

  const supportsPerishableInventory = useMemo(
      () => ['confectionery', 'flower_shop', 'cafe_restaurant'].includes(businessType),
      [businessType],
  );

  const telegramConnected = Boolean(
      telegramStatus &&
      typeof telegramStatus === 'object' &&
      'connected' in telegramStatus &&
      (telegramStatus as { connected?: unknown }).connected,
  );

  useEffect(() => {
    let cancelled = false;

    api.telegramStatus()
        .then((status) => {
          if (!cancelled) setTelegramStatus(status);
        })
        .catch(() => {
          if (!cancelled) setTelegramStatus(null);
        });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!businessSettings) return;

    setBusinessType(businessSettings.business_type);
    setAutoDiscountEnabled(Boolean(businessSettings.auto_discount_enabled));
    setShelfLifeHours(businessSettings.default_shelf_life_hours?.toString() ?? '');
    setDiscountAfterHours(businessSettings.default_discount_after_hours?.toString() ?? '');
    setDiscountPercent(businessSettings.default_discount_percent ?? '0');
  }, [businessSettings]);

  useEffect(() => {
    if (!companyId) return;

    let cancelled = false;
    setAutomationLoading(true);

    api.automationSettings(companyId)
        .then((settings) => {
          if (!cancelled) setAutomationSettings(settings);
        })
        .catch((err) => {
          if (!cancelled) onError?.(err instanceof Error ? err.message : String(err));
        })
        .finally(() => {
          if (!cancelled) setAutomationLoading(false);
        });

    return () => {
      cancelled = true;
    };
  }, [companyId, onError]);

  function parseOptionalNumber(value: string) {
    const trimmed = value.trim();
    if (!trimmed) return null;

    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function updateAutomationSettings(patch: Partial<AutomationSettings>) {
    setAutomationSettings((current) => ({ ...current, ...patch }));
  }

  async function connectTelegram() {
    setTelegramLoading(true);
    onError?.('');

    try {
      const { connect_url } = await api.createTelegramConnectLink();
      window.open(connect_url, '_blank', 'noopener,noreferrer');
      onNotice?.(t('companyInfo.telegramConnectNotice'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
    } finally {
      setTelegramLoading(false);
    }
  }

  async function disconnectTelegram() {
    setTelegramLoading(true);
    onError?.('');

    try {
      const status = await api.disconnectTelegram();
      setTelegramStatus(status);
      onNotice?.(t('companyInfo.telegramDisconnectNotice'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
    } finally {
      setTelegramLoading(false);
    }
  }

  async function savePreferences() {
    if (!companyId) return;

    setSavingPreferences(true);
    onError?.('');
    onNotice?.('');

    try {
      const updated = await api.updateBusinessSettings(companyId, {
        business_type: businessType,
        auto_discount_enabled: supportsPerishableInventory ? autoDiscountEnabled : false,
        default_shelf_life_hours: parseOptionalNumber(shelfLifeHours),
        default_discount_after_hours: parseOptionalNumber(discountAfterHours),
        default_discount_percent: discountPercent.trim() || '0',
      });

      onBusinessSettingsChange?.(updated);
      onNotice?.(t('companyInfo.saved'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingPreferences(false);
    }
  }

  async function saveAutomationSettings() {
    if (!companyId) return;

    setSavingAutomation(true);
    onError?.('');
    onNotice?.('');

    try {
      const updated = await api.updateAutomationSettings(companyId, automationSettings);
      setAutomationSettings(updated);
      onNotice?.(t('automation.saved'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingAutomation(false);
    }
  }

  async function changePassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (newPassword !== confirmPassword) {
      onError?.(t('companyInfo.passwordMismatch'));
      return;
    }

    if (newPassword.length < 8) {
      onError?.(t('companyInfo.passwordTooShort'));
      return;
    }

    setChangingPassword(true);
    onError?.('');
    onNotice?.('');

    try {
      await api.changePassword({
        current_password: currentPassword,
        new_password: newPassword,
      });

      setCurrentPassword('');
      setNewPassword('');
      setConfirmPassword('');
      onNotice?.(t('companyInfo.passwordChanged'));
    } catch (err) {
      onError?.(err instanceof Error ? err.message : String(err));
    } finally {
      setChangingPassword(false);
    }
  }

  return (
      <section className="space-y-6">
        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            className={`${cardClass} overflow-hidden`}
        >
          <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div className="flex items-start gap-3">
            <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#18261d]">
              <Settings2 size={24} />
            </span>
              <div>
                <h1 className="text-xl font-light text-[#18261d]">{t('companyInfo.title')}</h1>
                <p className="mt-1 text-sm text-[#18261d]">
                  Управляйте профилем компании, безопасностью и автоматизациями в одном месте.
                </p>
              </div>
            </div>

            <div className="inline-flex items-center gap-2 self-start rounded-full border border-[#e4f5e9] bg-[#e4f5e9] px-3 py-1.5 text-xs font-semibold text-[#18261d] sm:self-auto">
              <CheckCircle2 size={15} />
              {companyId ? 'Компания подключена' : 'Компания не выбрана'}
            </div>
          </div>
        </motion.div>

        <div className="grid gap-6 xl:grid-cols-12">
          <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.03 }}
              className={`${cardClass} xl:col-span-5`}
          >
            <div className="flex items-start gap-3">
            <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#18261d]">
              <Building2 size={22} />
            </span>
              <div>
                <h2 className="text-xl font-light text-[#18261d]">{t('companyInfo.title')}</h2>
                <p className="mt-1 text-sm text-[#18261d]">Основные данные подключённой компании.</p>
              </div>
            </div>

            <div className="mt-5 divide-y divide-[#e1ebe4] text-sm">
              <InfoRow label="Email" value={email} />
              <InfoRow label="Instagram account id" value={instagramChannel?.external_account_id} mono />
              <InfoRow label="Display name" value={instagramChannel?.display_name} />
              <InfoRow label={t('companyInfo.businessType')} value={businessSettings?.business_type_label} />
            </div>
          </motion.div>

          <motion.form
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.06 }}
              onSubmit={changePassword}
              className={`${cardClass} space-y-5 xl:col-span-7`}
          >
            <div className="flex items-start gap-3">
            <span className="rounded-[24px] bg-[#ffffff] p-3 text-[#18261d]">
              <KeyRound size={22} />
            </span>
              <div>
                <h2 className="text-xl font-light text-[#18261d]">{t('companyInfo.passwordTitle')}</h2>
                <p className="mt-1 text-sm text-[#18261d]">Используйте пароль не короче 8 символов.</p>
              </div>
            </div>

            <div className="grid gap-4 md:grid-cols-3">
              <Field label={t('companyInfo.currentPassword')}>
                <input
                    type="password"
                    value={currentPassword}
                    onChange={(event) => setCurrentPassword(event.target.value)}
                    autoComplete="current-password"
                    required
                    className={inputClass}
                />
              </Field>

              <Field label={t('companyInfo.newPassword')}>
                <input
                    type="password"
                    value={newPassword}
                    onChange={(event) => setNewPassword(event.target.value)}
                    autoComplete="new-password"
                    minLength={8}
                    required
                    className={inputClass}
                />
              </Field>

              <Field label={t('companyInfo.confirmPassword')}>
                <input
                    type="password"
                    value={confirmPassword}
                    onChange={(event) => setConfirmPassword(event.target.value)}
                    autoComplete="new-password"
                    minLength={8}
                    required
                    className={inputClass}
                />
              </Field>
            </div>

            <button
                type="submit"
                disabled={changingPassword || !currentPassword || !newPassword || !confirmPassword}
                className={primaryButtonClass}
            >
              {changingPassword ? t('companyInfo.passwordSaving') : t('companyInfo.passwordSave')}
            </button>
          </motion.form>
        </div>

        <div className="grid gap-6 xl:grid-cols-12">
          <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.09 }}
              className={`${cardClass} space-y-5 xl:col-span-8`}
          >
            <div className="flex items-start gap-3">
            <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#18261d]">
              <Store size={22} />
            </span>
              <div>
                <h2 className="text-xl font-light text-[#18261d]">{t('companyInfo.preferencesTitle')}</h2>
                <p className="mt-1 text-sm text-[#18261d]">Настройте логику товаров и автоматических скидок.</p>
              </div>
            </div>

            <Field label={t('companyInfo.businessType')}>
              <select
                  value={businessType}
                  onChange={(event) => setBusinessType(event.target.value as BusinessType)}
                  className={inputClass}
              >
                {businessTypeValues.map((value) => (
                    <option key={value} value={value}>
                      {t(`business.${value}`)}
                    </option>
                ))}
              </select>
            </Field>

            <div className="grid gap-4 md:grid-cols-3">
              <Field label={t('companyInfo.shelfLife')}>
                <input
                    value={shelfLifeHours}
                    onChange={(event) => setShelfLifeHours(event.target.value)}
                    inputMode="numeric"
                    placeholder={t('common.example48')}
                    className={inputClass}
                />
              </Field>

              <Field label={t('companyInfo.discountAfter')}>
                <input
                    value={discountAfterHours}
                    onChange={(event) => setDiscountAfterHours(event.target.value)}
                    inputMode="numeric"
                    placeholder={t('common.example24')}
                    className={inputClass}
                />
              </Field>

              <Field label={t('companyInfo.discountPercent')}>
                <input
                    value={discountPercent}
                    onChange={(event) => setDiscountPercent(event.target.value)}
                    inputMode="decimal"
                    placeholder={t('common.example15')}
                    className={inputClass}
                />
              </Field>
            </div>

            <label
                className={`flex cursor-pointer items-center justify-between gap-4 rounded-[24px] border p-4 transition ${
                    supportsPerishableInventory
                        ? 'border-[#d8e8dd] bg-[#ffffff] hover:border-[#d8e8dd]'
                        : 'cursor-not-allowed border-[#e1ebe4] bg-[#ffffff] opacity-70'
                }`}
            >
            <span>
              <span className="block text-sm font-semibold text-[#18261d]">{t('companyInfo.enableAutoDiscount')}</span>
              <span className="mt-1 block text-xs text-[#18261d]">
                {supportsPerishableInventory
                    ? 'Автоматически применяет скидку к товарам с ограниченным сроком хранения.'
                    : 'Доступно для кондитерских, цветочных магазинов и кафе/ресторанов.'}
              </span>
            </span>
              <input
                  type="checkbox"
                  checked={supportsPerishableInventory && autoDiscountEnabled}
                  disabled={!supportsPerishableInventory}
                  onChange={(event) => setAutoDiscountEnabled(event.target.checked)}
                  className="h-5 w-5 rounded border-[#e1ebe4] accent-[#18261d]"
              />
            </label>

            <button
                type="button"
                onClick={savePreferences}
                disabled={savingPreferences || !companyId}
                className={primaryButtonClass}
            >
              {savingPreferences ? t('companyInfo.saving') : t('companyInfo.save')}
            </button>
          </motion.div>
        </div>

        <motion.div
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.15 }}
            className={`${cardClass} overflow-hidden`}
        >
          <div className="flex items-start gap-3">
          <span className="rounded-[24px] bg-[#e4f5e9] p-3 text-[#18261d]">
            <Bell size={22} />
          </span>
            <div>
              <h2 className="text-xl font-light text-[#18261d]">{t('automation.reminderTitle')}</h2>
              <p className="mt-1 text-sm text-[#18261d]">{t('automation.reminderHint')}</p>
            </div>
          </div>

          {automationLoading ? (
              <div className="mt-7 rounded-[24px] border border-dashed border-[#d8e8dd] p-7">
                <Spinner label={t('automation.loading')} />
              </div>
          ) : (
              <div className="mt-6 grid gap-6 xl:grid-cols-12">
                <div className="space-y-4 xl:col-span-7">
                  <label className="flex cursor-pointer items-center justify-between gap-4 rounded-[24px] border border-[#e1ebe4] p-4 transition hover:border-[#d8e8dd]">
                <span>
                  <span className="block text-sm font-semibold text-[#18261d]">{t('automation.enableReminder')}</span>
                  <span className="mt-1 block text-xs text-[#18261d]">
                    Отправит мягкое напоминание, если клиент не отвечает.
                  </span>
                </span>
                    <input
                        type="checkbox"
                        checked={automationSettings.client_reminder_enabled}
                        onChange={(event) => updateAutomationSettings({ client_reminder_enabled: event.target.checked })}
                        className="h-5 w-5 rounded border-[#e1ebe4] accent-[#18261d]"
                    />
                  </label>

                  <Field label={t('automation.reminderMessage')}>
                <textarea
                    className={`${inputClass} min-h-[152px] resize-y`}
                    value={automationSettings.client_reminder_message}
                    onChange={(event) => updateAutomationSettings({ client_reminder_message: event.target.value })}
                />
                  </Field>
                </div>

                <div className="space-y-4 xl:col-span-5">
                  <Field label={t('automation.delayMinutes')}>
                    <input
                        type="number"
                        min={1}
                        className={inputClass}
                        inputMode="numeric"
                        value={automationSettings.client_reminder_delay_minutes}
                        onChange={(event) => {
                          const nextValue = Number(event.target.value);
                          updateAutomationSettings({
                            client_reminder_delay_minutes: Number.isFinite(nextValue) && nextValue > 0 ? nextValue : 120,
                          });
                        }}
                    />
                  </Field>

                  <div className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-4">
                    <div className="flex items-start gap-3">
                  <span className="rounded-[24px] bg-[#ffffff] p-2 text-[#18261d] ">
                    <MessageCircle size={18} />
                  </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-[#18261d]">{t('automation.commentsTitle')}</p>
                        <p className="mt-1 text-xs leading-5 text-[#18261d]">{t('automation.commentsHint')}</p>
                      </div>
                    </div>

                    <label className="mt-4 flex cursor-pointer items-center justify-between gap-4 rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] px-3.5 py-3">
                  <span className="flex items-center gap-2 text-sm font-semibold text-[#18261d]">
                    <CameraIcon size={17} className="text-[#18261d]" />
                    {t('automation.enableInstagramComments')}
                  </span>
                      <input
                          type="checkbox"
                          checked={automationSettings.instagram_comments_enabled}
                          onChange={(event) => updateAutomationSettings({ instagram_comments_enabled: event.target.checked })}
                          className="h-5 w-5 rounded border-[#e1ebe4] accent-[#18261d]"
                      />
                    </label>

                    <p className="mt-3 text-xs font-medium text-[#18261d]">
                      {automationSettings.instagram_comments_enabled
                          ? t('automation.commentsOn')
                          : t('automation.commentsOff')}
                    </p>
                  </div>
                </div>
              </div>
          )}

          <div className="mt-6 flex justify-end border-t border-[#e1ebe4] pt-5">
            <button
                type="button"
                onClick={saveAutomationSettings}
                disabled={automationLoading || savingAutomation || !companyId}
                className={primaryButtonClass}
            >
              {savingAutomation ? t('automation.saving') : t('automation.saveAll')}
            </button>
          </div>
        </motion.div>
      </section>
  );
}
