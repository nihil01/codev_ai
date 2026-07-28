import { useCallback, useEffect, useState } from 'react';
import { api } from '../../api';
import type { Manager } from '../../api';
import { cardClass } from '../../constants/styles';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

type ManagersProps = {
  companyId: string | null;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
};

function formatManagerMeta(manager: Manager): string {
  const parts = [];
  if (manager.telegram_username) parts.push(`@${manager.telegram_username}`);
  if (manager.telegram_user_id) parts.push(`ID ${manager.telegram_user_id}`);
  if (manager.registered_at) parts.push(new Date(manager.registered_at).toLocaleString());
  return parts.join(' · ');
}

/**
 * Managers are created by the Telegram webhook after a person opens the
 * Telegram deep link and presses Start. This component deliberately does not
 * call api.createManager(), because no Telegram chat ID can be trusted or
 * entered manually in the CRM.
 *
 * Existing API methods used here:
 * - api.managers(tenantId)
 * - api.updateManager(tenantId, managerId, payload)
 * - api.deleteManager(tenantId, managerId)
 */
export function ManagersAndBroadcasts({
                                        companyId,
                                        setError,
                                        setNotice,
                                      }: ManagersProps) {
  const { t } = useI18n();
  const [managers, setManagers] = useState<Manager[]>([]);
  const [loading, setLoading] = useState(false);
  const [openingTelegram, setOpeningTelegram] = useState(false);
  const [updatingManagerId, setUpdatingManagerId] = useState<string | null>(null);
  const [deletingManagerId, setDeletingManagerId] = useState<string | null>(null);

  const loadManagers = useCallback(async () => {
    if (!companyId) {
      setManagers([]);
      return;
    }

    setLoading(true);
    setError('');

    try {
      const nextManagers = await api.managers(companyId);
      setManagers(nextManagers);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }, [companyId, setError]);

  useEffect(() => {
    void loadManagers();
  }, [loadManagers]);

  /*
   * When the manager returns from Telegram to the CRM, refresh the list:
   * the Telegram webhook may have created the manager while the tab was hidden.
   */
  useEffect(() => {
    function refreshAfterTelegram() {
      if (document.visibilityState !== 'visible') return;

      setOpeningTelegram(false);
      void loadManagers();
    }

    document.addEventListener('visibilitychange', refreshAfterTelegram);
    window.addEventListener('focus', refreshAfterTelegram);

    return () => {
      document.removeEventListener('visibilitychange', refreshAfterTelegram);
      window.removeEventListener('focus', refreshAfterTelegram);
    };
  }, [loadManagers]);

  async function addManagerViaTelegram() {
    if (!companyId) return;

    setError('');
    setNotice('');
    setOpeningTelegram(true);

    try {
      const { connect_url } = await api.createTelegramManagerConnectLink(companyId);
      window.location.assign(connect_url);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
      setOpeningTelegram(false);
    }
  }

  async function toggleManager(manager: Manager) {
    if (!companyId) return;

    setUpdatingManagerId(manager.id);
    setError('');
    setNotice('');

    try {
      /*
       * Your current updateManager contract requires every field below.
       * Keep recipient_id and display_name unchanged; only switch is_active.
       */
      const updated = await api.updateManager(companyId, manager.id, {
        recipient_id: manager.recipient_id,
        display_name: manager.display_name,
        is_active: !manager.is_active,
      });

      setManagers((current) =>
          current.map((item) => (item.id === updated.id ? updated : item)),
      );

      setNotice(
          updated.is_active
              ? t('managers.enabledNotice')
              : t('managers.disabledNotice'),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUpdatingManagerId(null);
    }
  }

  async function removeManager(manager: Manager) {
    if (!companyId) return;

    const confirmed = window.confirm(
        `${t('managers.confirmDeletePrefix')} "${manager.display_name}"? ${t('managers.confirmDeleteSuffix')}`,
    );
    if (!confirmed) return;

    setDeletingManagerId(manager.id);
    setError('');
    setNotice('');

    try {
      await api.deleteManager(companyId, manager.id);
      setManagers((current) => current.filter((item) => item.id !== manager.id));
      setNotice(t('managers.deletedNotice'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setDeletingManagerId(null);
    }
  }

  if (loading) {
    return (
        <section className={`${cardClass} text-[#696a72]`}>
          <Spinner label={t('managers.loading')} />
        </section>
    );
  }

  return (
      <section className={`${cardClass} space-y-6`}>
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-2xl">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-[#145aff]">
              {t('managers.eyebrow')}
            </p>
            <h2 className="mt-2 text-2xl font-semibold text-[#020520]">
              {t('managers.title')}
            </h2>
          </div>

          <div className="flex flex-wrap gap-3">
            <button
                type="button"
                onClick={() => void loadManagers()}
                disabled={!companyId || loading || openingTelegram}
                className="rounded-xl border border-[#e2e4e9] bg-white px-5 py-3 text-sm font-semibold text-[#696a72] transition hover:bg-[#f5f5f5] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {t('managers.refresh')}
            </button>

            <button
                type="button"
                onClick={addManagerViaTelegram}
                disabled={!companyId || openingTelegram}
                className="rounded-xl bg-[#145aff] px-5 py-3 text-sm font-semibold text-white transition hover:bg-[#1249e0] disabled:cursor-not-allowed disabled:opacity-60"
            >
              {openingTelegram ? t('managers.opening') : t('managers.addViaTelegram')}
            </button>
          </div>
        </div>

        {!companyId && (
            <div className="rounded-lg border border-[#e2e4e9] bg-[#fffbeb] p-4 text-sm leading-6 text-[#020520]">
              {t('managers.noCompany')}
            </div>
        )}

        {managers.length === 0 ? (
            <div className="rounded-lg border border-dashed border-[#e2e4e9] bg-white p-6 text-sm leading-6 text-[#696a72]">
              {t('managers.empty')}
            </div>
        ) : (
            <div className="space-y-3">
              {managers.map((manager) => {
                const isUpdating = updatingManagerId === manager.id;
                const isDeleting = deletingManagerId === manager.id;

                return (
                    <article
                        key={manager.id}
                        className="rounded-lg border border-[#e2e4e9] bg-white p-4"
                    >
                      <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <h3 className="text-base font-semibold text-[#020520]">
                              {manager.display_name}
                            </h3>
                            <span className="rounded-full bg-[#eff6ff] px-3 py-1 text-xs font-semibold text-[#145aff]">
                        Telegram
                      </span>
                            <span
                                className={`rounded-full px-3 py-1 text-xs font-semibold ${
                                    manager.is_active
                                        ? 'bg-[#f0fdf4] text-[#16a34a]'
                                        : 'bg-[#f5f5f5] text-[#696a72]'
                                }`}
                            >
                        {manager.is_active
                            ? t('managers.active')
                                                            : t('managers.inactive')}
                      </span>
                          </div>

                          {/*
                     * recipient_id is the Telegram chat ID stored by the
                     * webhook. It is intentionally not displayed in the UI.
                     */}
                          <p className="mt-2 text-sm text-[#696a72]">
                            {t('managers.connected')}
                          </p>
                          {formatManagerMeta(manager) && (
                            <p className="mt-1 break-all text-xs font-semibold text-[#696a72]">
                              {formatManagerMeta(manager)}
                            </p>
                          )}
                        </div>

                        <div className="flex flex-wrap gap-2">
                          <button
                              type="button"
                              onClick={() => void toggleManager(manager)}
                              disabled={isUpdating || isDeleting}
                              className="rounded-xl border border-[#e2e4e9] px-4 py-2 text-xs font-semibold text-[#696a72] transition hover:bg-[#f5f5f5] disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isUpdating
                                ? t('managers.updating')
                                : manager.is_active
                                    ? t('managers.disable')
                                    : t('managers.enable')}
                          </button>

                          <button
                              type="button"
                              onClick={() => void removeManager(manager)}
                              disabled={isUpdating || isDeleting}
                              className="rounded-xl border border-[#fecaca] px-4 py-2 text-xs font-semibold text-[#b91c1c] transition hover:bg-[#fef2f2] disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {isDeleting ? t('managers.removing') : t('managers.remove')}
                          </button>
                        </div>
                      </div>
                    </article>
                );
              })}
            </div>
        )}
      </section>
  );
}
