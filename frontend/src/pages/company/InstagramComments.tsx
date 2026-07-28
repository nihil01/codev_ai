import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { api } from '../../api';
import type { CommentThread, InstagramComment } from '../../api';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

function commenterLabel(comment: InstagramComment) {
  return comment.author_username || comment.author_name || comment.author_id;
}

function formatDate(value?: string | null) {
  if (!value) return '—';
  return new Intl.DateTimeFormat('ru-RU', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(value));
}

type InstagramCommentsProps = {
  companyId?: string | null;
  setError: (message: string) => void;
  setNotice: (message: string) => void;
};

export function InstagramComments({ companyId, setError, setNotice }: InstagramCommentsProps) {
  const { t } = useI18n();

  const [threads, setThreads] = useState<CommentThread[]>([]);
  const [loading, setLoading] = useState(false);
  const [localError, setLocalError] = useState('');
  const [replyingTo, setReplyingTo] = useState<string | null>(null);
  const [replyText, setReplyText] = useState('');
  const [sending, setSending] = useState(false);
  const [autoReplyEnabled, setAutoReplyEnabled] = useState(false);
  const [loadingAutoReply, setLoadingAutoReply] = useState(false);

  async function load() {
    if (!companyId) return;
    setLoading(true);
    setLocalError('');
    try {
      const [threadRows, autoReplySettings] = await Promise.all([
        api.commentThreads(companyId),
        api.getAutoReplySettings(companyId),
      ]);
      setThreads(threadRows);
      setAutoReplyEnabled(autoReplySettings.enabled);
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      setLocalError(message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }

  async function toggleAutoReply() {
    if (!companyId) return;
    setLoadingAutoReply(true);
    try {
      const result = await api.updateAutoReplySettings(companyId, !autoReplyEnabled);
      setAutoReplyEnabled(result.enabled);
      setNotice(result.enabled ? t('comments.autoReplyEnabled') : t('comments.autoReplyDisabled'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoadingAutoReply(false);
    }
  }

  useEffect(() => {
    load();
  }, [companyId]);

  const flatComments = useMemo(() => threads.flatMap((thread) => thread.comments), [threads]);

  async function sendReply(comment: InstagramComment) {
    if (!companyId || !replyText.trim()) return;

    setSending(true);
    try {
      await api.sendCommentPrivateReply(companyId, comment.id, replyText.trim());

      setNotice(`${t('comments.replySent')}: @${commenterLabel(comment)}`);
      setReplyingTo(null);
      setReplyText('');
    } catch (err) {
      const error = err instanceof Error ? err.message : String(err);
      // Handle specific Zernio error for already replied comments
      if (error.includes('already been sent') || error.includes('already been replied') || error.includes('platform_api_error')) {
        setError(t('comments.errorAlreadyReplied'));
      } else {
        setError(error);
      }
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="space-y-6">
      {localError && <Alert type="error">{localError}</Alert>}

      {/* Header */}
      <section className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc] px-6 py-5">
        <div className="flex items-center justify-between">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#0f3e17]">Instagram</p>
            <h2 className="mt-1 text-xl font-light text-[#0f3e17]">{t('comments.title')}</h2>
          </div>
          <div className="flex items-center gap-6">
            {/* Auto-reply toggle */}
            <div className="flex items-center gap-3">
              <span className="text-sm font-medium text-[#222222]">{t('comments.autoReply')}</span>
              <button
                type="button"
                onClick={toggleAutoReply}
                disabled={loadingAutoReply}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                  autoReplyEnabled ? 'bg-[#0f3e17]' : 'bg-[#efeeeb]'
                } ${loadingAutoReply ? 'opacity-50' : ''}`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-[#fffefc] transition ${
                    autoReplyEnabled ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
            </div>
            <div className="text-right">
              <p className="text-2xl font-semibold text-[#0f3e17]">{flatComments.length}</p>
              <p className="text-xs text-[#222222]">{t('comments.totalComments')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* Comments list */}
      <section className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc]">
        {loading ? (
          <div className="p-8"><Spinner label={t('comments.loading')} /></div>
        ) : flatComments.length === 0 ? (
          <div className="p-8"><Alert type="info">{t('comments.empty')}</Alert></div>
        ) : (
          <div className="divide-y divide-[#efeeeb]">
            {threads.map((thread) => (
              <div key={thread.id} className="p-6">
                {/* Thread header */}
                <div className="mb-4 flex items-center gap-2 text-xs text-[#222222]">
                  <span className="font-medium">{t('comments.post')}:</span>
                  <span className="truncate">{thread.zernio_post_id || thread.platform_post_id}</span>
                  <span>·</span>
                  <span>{thread.comment_count} {t('comments.commentsCount')}</span>
                </div>

                {/* Comments */}
                <div className="space-y-4">
                  {thread.comments.map((comment) => (
                    <article key={comment.id} className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-4">
                      {/* Comment header */}
                      <div className="flex items-center justify-between">
                        <div className="flex items-center gap-2">
                          <div className="flex h-8 w-8 items-center justify-center rounded-full bg-[#e1f4df] text-xs font-semibold text-[#0f3e17]">
                            {commenterLabel(comment).charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[#0f3e17]">@{commenterLabel(comment)}</p>
                            <p className="text-xs text-[#222222]">{formatDate(comment.created_at)}</p>
                          </div>
                        </div>
                        {comment.status === 'new' && (
                          <button
                            type="button"
                            onClick={() => setReplyingTo(replyingTo === comment.id ? null : comment.id)}
                            className="rounded-[14px] bg-[#0f3e17] px-4 py-2 text-xs font-semibold text-[#fffefc] transition-colors hover:bg-[#0c2f10]"
                          >
                            {t('comments.replyDm')}
                          </button>
                        )}
                        {comment.status === 'replied' && (
                          <span className="rounded-full bg-[#e1f4df] px-3 py-1 text-xs font-medium text-[#0f3e17]">
                            {t('comments.status.replied')}
                          </span>
                        )}
                      </div>

                      {/* Comment text */}
                      <p className="mt-3 whitespace-pre-wrap text-sm leading-6 text-[#222222]">{comment.text || '—'}</p>

                      {/* AI suggested reply */}
                      {comment.ai_suggested_reply && (
                        <div className="mt-3 rounded-[14px] border border-[#efeeeb] bg-[#e1f4df] p-3">
                          <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-[#0f3e17]">{t('comments.aiDraft')}</p>
                          <p className="mt-1 whitespace-pre-wrap text-sm text-[#0f3e17]">{comment.ai_suggested_reply}</p>
                          <button
                            type="button"
                            onClick={() => { setReplyText(comment.ai_suggested_reply || ''); setReplyingTo(comment.id); }}
                            className="mt-2 text-xs font-semibold text-[#0f3e17] hover:underline"
                          >
                            {t('comments.useDraft')}
                          </button>
                        </div>
                      )}

                      {/* Reply form */}
                      {replyingTo === comment.id && (
                        <motion.div
                          initial={{ opacity: 0, height: 0 }}
                          animate={{ opacity: 1, height: 'auto' }}
                          className="mt-4 border-t border-[#efeeeb] pt-4"
                        >
                          <p className="mb-2 text-xs font-semibold text-[#222222]">
                            {t('comments.replyTo')} @{commenterLabel(comment)}
                          </p>
                          <textarea
                            value={replyText}
                            onChange={(e) => setReplyText(e.target.value)}
                            placeholder={t('comments.replyPlaceholder')}
                            className="w-full rounded-[14px] border border-[#efeeeb] bg-[#fffefc] px-4 py-3 text-sm text-[#0f3e17] outline-none transition focus:border-[#0f3e17] focus:ring-3 focus:ring-[rgba(20,90,255,0.08)]"
                            rows={3}
                          />
                          <div className="mt-3 flex gap-2">
                            <button
                              type="button"
                              onClick={() => sendReply(comment)}
                              disabled={sending || !replyText.trim()}
                              className="rounded-[14px] bg-[#0f3e17] px-5 py-2.5 text-sm font-semibold text-[#fffefc] transition-colors hover:bg-[#0c2f10] disabled:cursor-not-allowed disabled:opacity-50"
                            >
                              {sending ? t('comments.sending') : t('comments.sendDm')}
                            </button>
                            <button
                              type="button"
                              onClick={() => { setReplyingTo(null); setReplyText(''); }}
                              className="rounded-[14px] border border-[#efeeeb] px-5 py-2.5 text-sm font-semibold text-[#222222] transition hover:bg-[#e1f4df]"
                            >
                              {t('common.cancel')}
                            </button>
                          </div>
                        </motion.div>
                      )}
                    </article>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
