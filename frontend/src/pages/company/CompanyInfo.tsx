import { useState } from 'react';
import type { FormEvent } from 'react';
import { motion } from 'framer-motion';
import { Building2, CheckCircle2, KeyRound, Settings2 } from 'lucide-react';
import { api } from '../../api';
import type { BusinessSettings, Channel } from '../../api';
import { cardClass, inputClass, primaryButtonClass } from '../../constants/styles';
import { Field } from '../../components/ui/Field';
import { InfoRow } from '../../components/ui/InfoRow';
import { useI18n } from '../../i18n';

type CompanyInfoProps = {
  companyId?: string | null;
  email: string;
  instagramChannel?: Channel;
  businessSettings?: BusinessSettings | null;
  onError?: (message: string) => void;
  onNotice?: (message: string) => void;
};

export function CompanyInfo({
  companyId,
  email,
  instagramChannel,
  businessSettings,
  onError,
  onNotice,
}: CompanyInfoProps) {
  const { t } = useI18n();
  const [currentPassword, setCurrentPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [changingPassword, setChangingPassword] = useState(false);

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
    } catch (error) {
      onError?.(error instanceof Error ? error.message : String(error));
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
                Управляйте профилем компании и безопасностью аккаунта.
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
    </section>
  );
}
