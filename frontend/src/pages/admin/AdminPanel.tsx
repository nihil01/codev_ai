import { useEffect, useState } from 'react';
import type { FormEvent } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { api } from '../../api';
import type { AdminBotPrompt, BusinessType, CommentPrompt, CompanySubscription, CreateCompanyUserResponse, CurrentUser, PackageCode, Tenant } from '../../api';
import { cardClass, inputClass, primaryButtonClass } from '../../constants/styles';
import { DashboardShell } from '../../components/layout/DashboardShell';
import { Alert } from '../../components/ui/Alert';
import { Field } from '../../components/ui/Field';
import { InfoRow } from '../../components/ui/InfoRow';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

type AdminPanelProps = {
  user: CurrentUser;
  onLogout: () => void;
};

const businessTypeValues: BusinessType[] = ['confectionery', 'flower_shop', 'cafe_restaurant'];

export function AdminPanel({ user, onLogout }: AdminPanelProps) {
  const { t } = useI18n();
  const businessTypeHelper = (value: BusinessType) => t(`admin.business.${value}.helper`);
  const [formData, setFormData] = useState({ email: '', instagram_account_name: '', temporary_password: '', business_type: 'confectionery' as BusinessType, package_code: 'basic' as PackageCode });
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [createdUser, setCreatedUser] = useState<CreateCompanyUserResponse | null>(null);

  const [tenants, setTenants] = useState<Tenant[]>([]);
  const [selectedTenantId, setSelectedTenantId] = useState('');
  const [subscription, setSubscription] = useState<CompanySubscription | null>(null);
  const [subscriptionDraft, setSubscriptionDraft] = useState({ package_code: 'basic' as PackageCode, access_locked: false, locked_reason: '' });
  const [savingSubscription, setSavingSubscription] = useState(false);
  const [promptRecord, setPromptRecord] = useState<AdminBotPrompt | null>(null);
  const [promptDraft, setPromptDraft] = useState('');
  const [promptTitle, setPromptTitle] = useState('CRM prompt');
  const [commentPromptRecord, setCommentPromptRecord] = useState<CommentPrompt | null>(null);
  const [commentPromptDraft, setCommentPromptDraft] = useState('');
  const [commentPromptTitle, setCommentPromptTitle] = useState('Instagram comment prompt');
  const [loadingPrompt, setLoadingPrompt] = useState(false);
  const [savingPrompt, setSavingPrompt] = useState(false);
  const [promptNotice, setPromptNotice] = useState('');
  const [promptError, setPromptError] = useState('');

  useEffect(() => {
    let cancelled = false;

    async function loadTenants() {
      try {
        const rows = await api.tenants();
        if (cancelled) return;
        setTenants(rows);
        setSelectedTenantId((current) => current || rows[0]?.id || '');
      } catch (err) {
        if (!cancelled) setPromptError(err instanceof Error ? err.message : String(err));
      }
    }

    loadTenants();

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function loadPrompt() {
      if (!selectedTenantId) {
        setPromptRecord(null);
        setPromptDraft('');
        setCommentPromptRecord(null);
        setCommentPromptDraft('');
        setSubscription(null);
        return;
      }

      setLoadingPrompt(true);
      setPromptError('');
      setPromptNotice('');

      try {
        const [prompt, commentPrompt, subscriptionInfo] = await Promise.all([
          api.adminBotPrompt(selectedTenantId),
          api.commentPrompt(selectedTenantId),
          api.companySubscription(selectedTenantId),
        ]);
        if (cancelled) return;
        setPromptRecord(prompt);
        setPromptDraft(prompt.system_prompt);
        setPromptTitle(prompt.title || 'CRM prompt');
        setCommentPromptRecord(commentPrompt);
        setCommentPromptDraft(commentPrompt.system_prompt);
        setCommentPromptTitle(commentPrompt.title || 'Instagram comment prompt');
        setSubscription(subscriptionInfo);
        setSubscriptionDraft({
          package_code: subscriptionInfo.package_code,
          access_locked: subscriptionInfo.access_locked,
          locked_reason: subscriptionInfo.locked_reason || '',
        });
      } catch (err) {
        if (!cancelled) setPromptError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoadingPrompt(false);
      }
    }

    loadPrompt();

    return () => {
      cancelled = true;
    };
  }, [selectedTenantId]);

  async function handleCreateCompanyUser(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError('');
    setSuccess('');

    try {
      const result = await api.createCompanyUser(
        formData.email.trim(),
        formData.instagram_account_name.trim(),
        formData.temporary_password,
        formData.business_type,
        formData.package_code,
      );
      setCreatedUser(result);
      setSuccess(t('admin.createdNotice'));
      setFormData({ email: '', instagram_account_name: '', temporary_password: '', business_type: 'confectionery', package_code: 'basic' });

      const rows = await api.tenants();
      setTenants(rows);
      if (result.company_id) {
        setSelectedTenantId(result.company_id);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function saveSubscription(event: FormEvent) {
    event.preventDefault();
    if (!selectedTenantId) return;
    setSavingSubscription(true);
    setPromptError('');
    setPromptNotice('');
    try {
      const saved = await api.updateCompanySubscription(selectedTenantId, {
        package_code: subscriptionDraft.package_code,
        access_locked: subscriptionDraft.access_locked,
        locked_reason: subscriptionDraft.access_locked ? subscriptionDraft.locked_reason.trim() || null : null,
      });
      setSubscription(saved);
      setSubscriptionDraft({ package_code: saved.package_code, access_locked: saved.access_locked, locked_reason: saved.locked_reason || '' });
      const rows = await api.tenants();
      setTenants(rows);
      setPromptNotice('Package/access updated');
    } catch (err) {
      setPromptError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingSubscription(false);
    }
  }

  async function savePrompt(event: FormEvent) {
    event.preventDefault();
    if (!selectedTenantId) return;

    setSavingPrompt(true);
    setPromptError('');
    setPromptNotice('');

    try {
      const [saved, savedComment] = await Promise.all([
        api.updateAdminBotPrompt(selectedTenantId, {
          title: promptTitle.trim() || 'CRM prompt',
          system_prompt: promptDraft.trim(),
        }),
        api.updateCommentPrompt(selectedTenantId, {
          title: commentPromptTitle.trim() || 'Instagram comment prompt',
          system_prompt: commentPromptDraft.trim(),
        }),
      ]);
      setPromptRecord(saved);
      setPromptDraft(saved.system_prompt);
      setPromptTitle(saved.title);
      setCommentPromptRecord(savedComment);
      setCommentPromptDraft(savedComment.system_prompt);
      setCommentPromptTitle(savedComment.title);
      setPromptNotice(t('admin.promptSaved'));
    } catch (err) {
      setPromptError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingPrompt(false);
    }
  }

  return (
    <DashboardShell
      user={user}
      onLogout={onLogout}
      badge={t('admin.badge')}
      title={t('admin.title')}
      subtitle={t('admin.subtitle')}
      navItems={[]}
      activeNav=""
      onNavChange={() => {}}
    >
      <div className="space-y-6">
        <div className="grid gap-6 lg:grid-cols-[0.8fr_1.2fr]">
          <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={cardClass}>
            <h2 className="text-xl font-light text-[#0f3e17]">Administrator</h2>
            <div className="mt-5 space-y-3 text-sm">
              <InfoRow label="Email" value={user.email} />
              <InfoRow label="Rol" value="Administrator" />
              <InfoRow label="Route" value="/admin/login" />
            </div>
          </motion.section>

          <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.06 }} className={cardClass}>
            <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <h2 className="text-xl font-light text-[#0f3e17]">{t('admin.createCompany')}</h2>
                <p className="mt-1 text-sm text-[#222222]">{t('admin.createCompanyHint')}</p>
              </div>
            </div>

            <form onSubmit={handleCreateCompanyUser} className="grid gap-4">
              {error && <Alert type="error">{error}</Alert>}
              {success && <Alert type="success">{success}</Alert>}

              <Field label={t('admin.companyEmail')}>
                <input className={inputClass} type="email" value={formData.email} onChange={(event) => setFormData({ ...formData, email: event.target.value })} placeholder="company@example.com" required />
              </Field>

              <Field label={t('admin.instagramAccount')}>
                <input className={inputClass} type="text" value={formData.instagram_account_name} onChange={(event) => setFormData({ ...formData, instagram_account_name: event.target.value })} placeholder="example_company" required />
              </Field>

              <Field label={t('admin.tempPassword')}>
                <input className={inputClass} type="text" value={formData.temporary_password} onChange={(event) => setFormData({ ...formData, temporary_password: event.target.value })} placeholder={t('admin.tempPasswordPlaceholder')} required />
              </Field>

              <Field label={t('companyInfo.businessType')}>
                <select
                  className={inputClass}
                  value={formData.business_type}
                  onChange={(event) => setFormData({ ...formData, business_type: event.target.value as BusinessType })}
                  required
                >
                  {businessTypeValues.map((value) => (
                    <option key={value} value={value}>{t(`business.${value}`)}</option>
                  ))}
                </select>
                <p className="mt-2 text-xs font-semibold text-[#222222]">
                  {businessTypeHelper(formData.business_type)}
                </p>
              </Field>

              <Field label="Package">
                <select
                  className={inputClass}
                  value={formData.package_code}
                  onChange={(event) => setFormData({ ...formData, package_code: event.target.value as PackageCode })}
                >
                  <option value="basic">Basic — 4000 text + 1000 voice, no autoposting</option>
                  <option value="full">Full — all features, 50 AI videos/month</option>
                </select>
              </Field>

              <button className={primaryButtonClass} type="submit" disabled={loading}>
                {loading ? <Spinner label={t('admin.creating')} /> : t('admin.createUser')}
              </button>
            </form>

            <AnimatePresence>
              {createdUser && (
                <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -8 }} className="mt-6 rounded-[14px] border border-[#cfe7d3] bg-[#e1f4df] p-5 text-sm text-[#0f3e17]">
                  <h3 className="text-lg font-light text-[#0f3e17]">{t('admin.companyCreated')}</h3>
                  <div className="mt-4 grid gap-2">
                    <InfoRow label="User ID" value={createdUser.user_id} />
                    <InfoRow label="Email" value={createdUser.email} />
                    <InfoRow label="Company ID" value={createdUser.company_id || t('admin.oauthAfter')} />
                    <InfoRow label="Company Name" value={createdUser.company_name} />
                    <InfoRow label="Business Type" value={createdUser.business_type_label} />
                    <InfoRow label="Temporary Password" value={createdUser.temporary_password} mono />
                  </div>
                  <p className="mt-4 font-semibold text-[#0f3e17]">{t('admin.saveAndSend')}</p>
                </motion.div>
              )}
            </AnimatePresence>
          </motion.section>
        </div>

        <motion.section initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 0.1 }} className={cardClass}>
          <div className="mb-5 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-[#0f3e17]">AI Prompts</p>
              <h2 className="mt-2 text-xl font-light text-[#0f3e17]">Client AI Settings</h2>
              <p className="mt-1 text-sm text-[#222222]">{t('admin.promptHint')}</p>
            </div>
          </div>

          <div className="grid gap-5 lg:grid-cols-[0.8fr_1.2fr]">
            <div className="space-y-4">
              {promptError && <Alert type="error">{promptError}</Alert>}
              {promptNotice && <Alert type="success">{promptNotice}</Alert>}

              <Field label={t('admin.selectClient')}>
                <select
                  className={inputClass}
                  value={selectedTenantId}
                  onChange={(event) => setSelectedTenantId(event.target.value)}
                >
                  {tenants.length === 0 ? (
                    <option value="">{t('admin.noCompany')}</option>
                  ) : (
                    tenants.map((tenant) => (
                      <option key={tenant.id} value={tenant.id}>
                        {tenant.name} / {tenant.slug}
                      </option>
                    ))
                  )}
                </select>
              </Field>

              {promptRecord && (
                <div className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-4 text-sm">
                  <InfoRow label="Company" value={promptRecord.company_name} />
                  <InfoRow label="Username" value={promptRecord.username || '—'} />
                  <InfoRow label="Version" value={String(promptRecord.version)} />
                </div>
              )}

              {subscription && (
                <form onSubmit={saveSubscription} className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-4 text-sm">
                  <h3 className="text-base font-light text-[#0f3e17]">Package and access</h3>
                  <div className="mt-4 grid gap-3">
                    <Field label="Package">
                      <select className={inputClass} value={subscriptionDraft.package_code} onChange={(event) => setSubscriptionDraft({ ...subscriptionDraft, package_code: event.target.value as PackageCode })}>
                        <option value="basic">Basic — 4000 text + 1000 voice, no autoposting</option>
                        <option value="full">Full — all features, 50 AI videos/month</option>
                      </select>
                    </Field>
                    <label className="flex items-center gap-3 rounded-[14px] border border-[#efeeeb] bg-[#fffefc] px-4 py-3 font-semibold text-[#0f3e17]">
                      <input type="checkbox" checked={subscriptionDraft.access_locked} onChange={(event) => setSubscriptionDraft({ ...subscriptionDraft, access_locked: event.target.checked })} />
                      Lock client access
                    </label>
                    <input className={inputClass} placeholder="Lock reason" value={subscriptionDraft.locked_reason} onChange={(event) => setSubscriptionDraft({ ...subscriptionDraft, locked_reason: event.target.value })} />
                    <div className="grid gap-2 rounded-[14px] bg-[#fffefc] p-3">
                      <InfoRow label="Text messages" value={`${subscription.text_messages_used} / ${subscription.monthly_text_messages_limit ?? '∞'}`} />
                      <InfoRow label="Voice messages" value={`${subscription.voice_messages_used} / ${subscription.monthly_voice_messages_limit ?? '∞'}`} />
                      <InfoRow label="AI videos" value={`${subscription.ai_videos_used} / ${subscription.monthly_ai_videos_limit ?? '∞'}`} />
                      <InfoRow label="Autoposting" value={subscription.autoposting_enabled ? 'enabled' : 'disabled'} />
                      <InfoRow label="Period" value={subscription.usage_period} />
                    </div>
                    <button type="submit" className={primaryButtonClass} disabled={savingSubscription}>{savingSubscription ? <Spinner label="Saving package..." /> : 'Save package/access'}</button>
                  </div>
                </form>
              )}
            </div>

            <form onSubmit={savePrompt} className="space-y-4">
              {loadingPrompt ? (
                <div className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-5 text-[#222222]">
                  <Spinner label={t('admin.promptLoading')} />
                </div>
              ) : (
                <>
                  <Field label="Prompt title">
                    <input className={inputClass} value={promptTitle} onChange={(event) => setPromptTitle(event.target.value)} maxLength={255} />
                  </Field>

                  <Field label="Current system prompt">
                    <textarea
                      className={`${inputClass} min-h-72 resize-y leading-6`}
                      value={promptDraft}
                      onChange={(event) => setPromptDraft(event.target.value)}
                      maxLength={3000}
                      required
                    />
                  </Field>

                  <div className="rounded-[14px] border border-[#efeeeb] bg-[#e1f4df] p-4">
                    <div className="mb-4 flex items-center justify-between gap-3">
                      <div>
                        <p className="text-xs font-semibold uppercase tracking-[0.2em] text-[#0f3e17]">Instagram Comments</p>
                        <h3 className="text-base font-light text-[#0f3e17]">Comment system prompt</h3>
                      </div>
                      {commentPromptRecord && <span className="rounded-[14px] bg-[#fffefc] border border-[#efeeeb] px-3 py-1 text-xs font-semibold text-[#222222]">v{commentPromptRecord.version}</span>}
                    </div>
                    <div className="space-y-4">
                      <Field label="Comment prompt title">
                        <input className={inputClass} value={commentPromptTitle} onChange={(event) => setCommentPromptTitle(event.target.value)} maxLength={255} />
                      </Field>
                      <Field label="Comment system prompt">
                        <textarea
                          className={`${inputClass} min-h-56 resize-y leading-6`}
                          value={commentPromptDraft}
                          onChange={(event) => setCommentPromptDraft(event.target.value)}
                          maxLength={3000}
                          required
                        />
                      </Field>
                    </div>
                  </div>

                  <button className={primaryButtonClass} type="submit" disabled={savingPrompt || !selectedTenantId}>
                    {savingPrompt ? <Spinner label={t('admin.promptSaving')} /> : t('admin.promptSave')}
                  </button>
                </>
              )}
            </form>
          </div>
        </motion.section>
      </div>
    </DashboardShell>
  );
}
