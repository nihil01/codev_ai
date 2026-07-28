import { useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { api } from '../../api';
import type { Conversation } from '../../api';
import { cardClass, inputClass, primaryButtonClass, secondaryButtonClass } from '../../constants/styles';
import { Alert } from '../../components/ui/Alert';
import { Field } from '../../components/ui/Field';
import { Spinner } from '../../components/ui/Spinner';
import { useI18n } from '../../i18n';

type ChatExplorerProps = {
  companyId: string | null;
  conversations: Conversation[];
  setConversations: (conversations: Conversation[]) => void;
  setError: (message: string) => void;
};

function formatDate(value?: string | null) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return new Intl.DateTimeFormat('az-AZ', {
    day: '2-digit',
    month: '2-digit',
    year: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  }).format(date);
}

function customerLabel(conversation: Conversation) {
  return (
    conversation.customer_username ||
    conversation.customer_phone ||
    conversation.customer_whatsapp_id ||
    conversation.customer_instagram_id ||
    conversation.external_conversation_id
  );
}

function customerSearchText(conversation: Conversation) {
  return [
    conversation.customer_username,
    conversation.customer_phone,
    conversation.customer_whatsapp_id,
    conversation.customer_instagram_id,
    conversation.external_conversation_id,
    conversation.id,
  ]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();
}

function channelLabel(channel: Conversation['channel']) {
  return channel === 'whatsapp' ? 'WhatsApp' : 'Instagram';
}

function channelBadgeClass(channel: Conversation['channel']) {
  return channel === 'whatsapp' ? 'bg-[#e1f4df] text-[#0f3e17]' : 'bg-fuchsia-50 text-fuchsia-700';
}

function modeLabel(mode: Conversation['mode']) {
  const labels = { bot: 'BOT', human: 'HUMAN', paused: 'PAUSED', closed: 'CLOSED' } as const;
  return labels[mode] ?? mode;
}

function modeBadgeClass(mode: Conversation['mode']) {
  if (mode === 'human') return 'bg-[#b1dbb8] text-[#0f3e17]';
  if (mode === 'paused') return 'bg-[#b1dbb8] text-[#0f3e17]';
  if (mode === 'closed') return 'bg-[#b6ced5] text-[#222222]';
  return 'bg-sky-50 text-sky-700';
}

function computeWindowLeft(value: string | null | undefined, closedLabel: string, hourLabel: string, minuteLabel: string) {
  if (!value) return '—';
  const expires = new Date(value).getTime();
  if (Number.isNaN(expires)) return '—';
  const ms = expires - Date.now();
  if (ms <= 0) return closedLabel;
  const totalMinutes = Math.floor(ms / 60000);
  const hours = Math.floor(totalMinutes / 60);
  const minutes = totalMinutes % 60;
  return `${hours}${hourLabel} ${minutes}${minuteLabel}`;
}

function isMessagingWindowOpen(value: string | null | undefined) {
  if (!value) return false;
  const expires = new Date(value).getTime();
  return !Number.isNaN(expires) && expires > Date.now();
}

type ChannelFilter = 'all' | Conversation['channel'];

export function ChatExplorer({ companyId, conversations, setConversations, setError }: ChatExplorerProps) {
  const { t } = useI18n();
  const windowClosedLabel = t('chat.windowClosed');
  const windowLeftLabel = (value?: string | null) => computeWindowLeft(value, windowClosedLabel, t('chat.hourShort'), t('chat.minuteShort'));
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [customer, setCustomer] = useState('');
  const [channel, setChannel] = useState<ChannelFilter>('all');
  const [selectedId, setSelectedId] = useState<string | null>(conversations[0]?.id ?? null);
  const [loading, setLoading] = useState(false);
  const [draftMessage, setDraftMessage] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);

  const filteredConversations = useMemo(() => {
    const customerNeedle = customer.trim().toLowerCase();
    const fromTime = from ? new Date(`${from}T00:00:00`).getTime() : null;
    const toTime = to ? new Date(`${to}T23:59:59`).getTime() : null;

    return conversations.filter((conversation) => {
      const searchableCustomer = customerSearchText(conversation);
      const lastMessageAt = conversation.last_message_at || conversation.created_at;
      const time = lastMessageAt ? new Date(lastMessageAt).getTime() : 0;

      if (customerNeedle && !searchableCustomer.includes(customerNeedle)) return false;
      if (channel !== 'all' && conversation.channel !== channel) return false;
      if (fromTime !== null && time < fromTime) return false;
      if (toTime !== null && time > toTime) return false;
      return true;
    });
  }, [conversations, customer, channel, from, to]);

  const selectedConversation = useMemo(() => {
    return filteredConversations.find((conversation) => conversation.id === selectedId) ?? filteredConversations[0] ?? null;
  }, [filteredConversations, selectedId]);

  const totalMessages = useMemo(
    () => filteredConversations.reduce((sum, conversation) => sum + conversation.messages.length, 0),
    [filteredConversations],
  );

  async function loadChats() {
    if (!companyId) return;

    setLoading(true);
    setError('');

    try {
      const result = await api.conversations(companyId, {
        from: from || undefined,
        to: to || undefined,
        customer: customer.trim() || undefined,
        channel,
      });
      setConversations(result);
      setSelectedId(result[0]?.id ?? null);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function applyConversationAction(action: 'human' | 'bot') {
    if (!companyId || !selectedConversation) return;
    setLoading(true);
    setError('');
    try {
      const updated = action === 'human'
        ? await api.takeConversation(companyId, selectedConversation.channel, selectedConversation.id)
        : await api.returnConversationToBot(companyId, selectedConversation.channel, selectedConversation.id);

      setConversations(conversations.map((conversation) => (
        conversation.id === selectedConversation.id
          ? {
              ...conversation,
              mode: updated.mode,
              assigned_manager_id: updated.assigned_manager_id,
              bot_paused_at: updated.bot_paused_at,
              bot_paused_reason: updated.bot_paused_reason,
              messaging_window_expires_at: updated.messaging_window_expires_at,
              status: updated.status,
              priority: updated.priority,
            }
          : conversation
      )));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  async function sendManualMessage() {
    if (!companyId || !selectedConversation) return;
    const messageText = draftMessage.trim();
    if (!messageText) return;

    if (!isMessagingWindowOpen(selectedConversation.messaging_window_expires_at)) {
      window.alert(t('chat.sendWindowClosed'));
      return;
    }

    setSendingMessage(true);
    setError('');
    try {
      const result = await api.sendConversationMessage(companyId, selectedConversation.channel, selectedConversation.id, messageText);
      setConversations(conversations.map((conversation) => (
        conversation.id === selectedConversation.id
          ? {
              ...conversation,
              mode: result.conversation.mode,
              assigned_manager_id: result.conversation.assigned_manager_id,
              bot_paused_at: result.conversation.bot_paused_at,
              bot_paused_reason: result.conversation.bot_paused_reason,
              messaging_window_expires_at: result.conversation.messaging_window_expires_at,
              status: result.conversation.status,
              priority: result.conversation.priority,
              last_message_at: result.message.created_at ?? conversation.last_message_at,
              messages: [...conversation.messages, result.message],
            }
          : conversation
      )));
      setDraftMessage('');
    } catch (err) {
      const message = err instanceof Error ? err.message : String(err);
      if (message.includes('24-hour messaging window is closed')) {
        window.alert(t('chat.sendWindowClosed'));
      }
      setError(message);
    } finally {
      setSendingMessage(false);
    }
  }

  function resetFilters() {
    setFrom('');
    setTo('');
    setCustomer('');
    setChannel('all');
  }

  return (
    <section className="space-y-6">
      <motion.div initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} className={`${cardClass} space-y-5`}>
        <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.25em] text-[#0f3e17]">{t('chat.eyebrow')}</p>
            <h2 className="mt-2 text-2xl font-light text-[#0f3e17]">{t('chat.title')}</h2>
          </div>
          <div className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc] px-4 py-3 text-sm font-semibold text-[#222222]">
            {filteredConversations.length} {t('chat.summaryChats')} / {totalMessages} {t('chat.summaryMessages')}
          </div>
        </div>

        <div className="grid gap-4 lg:grid-cols-[1fr_1fr_1fr_1.2fr_auto_auto] lg:items-end">
          <Field label={t('chat.fromDate')}>
            <input className={inputClass} type="date" value={from} onChange={(event) => setFrom(event.target.value)} />
          </Field>
          <Field label={t('chat.toDate')}>
            <input className={inputClass} type="date" value={to} onChange={(event) => setTo(event.target.value)} />
          </Field>
          <Field label={t('chat.channel')}>
            <select
              className={inputClass}
              value={channel}
              onChange={(event) => setChannel(event.target.value as ChannelFilter)}
            >
              <option value="all">{t('chat.all')}</option>
              <option value="instagram">Instagram</option>
              <option value="whatsapp">WhatsApp</option>
            </select>
          </Field>
          <Field label={t('chat.customerFilter')}>
            <input
              className={inputClass}
              value={customer}
              onChange={(event) => setCustomer(event.target.value)}
              placeholder={t('chat.customerPlaceholder')}
            />
          </Field>
          <button type="button" className={primaryButtonClass} onClick={loadChats} disabled={loading || !companyId}>
            {loading ? <Spinner label={t('chat.loading')} /> : t('chat.filter')}
          </button>
          <button type="button" className={secondaryButtonClass} onClick={resetFilters} disabled={loading}>
            {t('chat.reset')}
          </button>
        </div>
      </motion.div>

      <div className="grid gap-6 xl:grid-cols-[0.9fr_1.3fr]">
        <motion.div initial={{ opacity: 0, x: -12 }} animate={{ opacity: 1, x: 0 }} className={`${cardClass} max-h-[720px] overflow-auto`}>
          {loading ? (
            <Spinner label={t('chat.loadingChats')} />
          ) : filteredConversations.length === 0 ? (
            <Alert type="info">{t('chat.notFound')}</Alert>
          ) : (
            <div className="space-y-3">
              {filteredConversations.map((conversation) => {
                const active = selectedConversation?.id === conversation.id;
                const lastMessage = conversation.messages[conversation.messages.length - 1];
                return (
                  <button
                    key={conversation.id}
                    type="button"
                    onClick={() => setSelectedId(conversation.id)}
                    className={`w-full rounded-[14px] border p-4 text-left transition duration-200 ${
                      active
                        ? 'border-[#0f3e17] bg-[#e1f4df]'
                        : 'border-[#efeeeb] bg-[#fffefc] hover:border-[#0f3e17]/40 hover:bg-[#e1f4df]/50'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="truncate font-semibold text-[#0f3e17]">{customerLabel(conversation)}</p>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${channelBadgeClass(conversation.channel)}`}>
                            {channelLabel(conversation.channel)}
                          </span>
                          <span className={`rounded-full px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${modeBadgeClass(conversation.mode)}`}>
                            {modeLabel(conversation.mode)}
                          </span>
                        </div>
                        <p className="mt-1 truncate text-xs text-[#222222]">{conversation.external_conversation_id}</p>
                      </div>
                      <span className="rounded-full bg-[#e1f4df] px-3 py-1 text-xs font-semibold text-[#222222]">
                        {conversation.messages.length}
                      </span>
                    </div>
                    <p className="mt-3 line-clamp-2 text-sm leading-6 text-[#222222]">
                      {lastMessage?.text || t('chat.noMessages')}
                    </p>
                    <p className="mt-3 text-xs font-medium text-[#222222]">{formatDate(conversation.last_message_at || conversation.created_at)} · {t('chat.window')}: {windowLeftLabel(conversation.messaging_window_expires_at)}</p>
                  </button>
                );
              })}
            </div>
          )}
        </motion.div>

        <motion.div initial={{ opacity: 0, x: 12 }} animate={{ opacity: 1, x: 0 }} className={`${cardClass} min-h-[520px]`}>
          {!selectedConversation ? (
            <Alert type="info">{t('chat.selectChat')}</Alert>
          ) : (
            <div className="flex h-full flex-col">
              <div className="border-b border-[#efeeeb] pb-4">
                <div className="flex flex-wrap items-center gap-2">
                  <h3 className="text-xl font-light text-[#0f3e17]">{customerLabel(selectedConversation)}</h3>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${channelBadgeClass(selectedConversation.channel)}`}>
                    {channelLabel(selectedConversation.channel)}
                  </span>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold uppercase tracking-[0.14em] ${modeBadgeClass(selectedConversation.mode)}`}>
                    {modeLabel(selectedConversation.mode)}
                  </span>
                </div>
                <p className="mt-1 text-sm text-[#222222]">
                  {t('chat.lastActivity')}: {formatDate(selectedConversation.last_message_at || selectedConversation.created_at)} · 24h {t('chat.window')}: {windowLeftLabel(selectedConversation.messaging_window_expires_at)}
                </p>
                {windowLeftLabel(selectedConversation.messaging_window_expires_at) === windowClosedLabel && (
                  <Alert type="info">{t('chat.windowClosedWarning')}</Alert>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  {selectedConversation.mode === 'bot' ? (
                    <button
                      type="button"
                      className={secondaryButtonClass}
                      onClick={() => applyConversationAction('human')}
                      disabled={loading || !companyId}
                    >
                      {t('chat.switchHuman')}
                    </button>
                  ) : (
                    <button
                      type="button"
                      className={primaryButtonClass}
                      onClick={() => applyConversationAction('bot')}
                      disabled={loading || !companyId || selectedConversation.mode === 'closed'}
                    >
                      {t('chat.switchBot')}
                    </button>
                  )}
                </div>
              </div>

              <div className="mt-5 max-h-[620px] space-y-3 overflow-auto pr-2">
                <AnimatePresence initial={false}>
                  {selectedConversation.messages.map((message) => {
                    const outbound = message.direction === 'outbound';
                    return (
                      <motion.div
                        key={message.id}
                        initial={{ opacity: 0, y: 8 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: -8 }}
                        className={`flex ${outbound ? 'justify-end' : 'justify-start'}`}
                      >
                        <div
                          className={`max-w-[78%] rounded-[14px] px-4 py-3 text-sm leading-6 ${
                            outbound
                              ? 'bg-[#0f3e17] text-[#fffefc]'
                              : 'border border-[#efeeeb] bg-[#fffefc] text-[#0f3e17]'
                          }`}
                        >
                          <p className="whitespace-pre-wrap">{message.text || '—'}</p>
                          <p className={`mt-2 text-[11px] font-medium ${outbound ? 'text-[#222222]' : 'text-[#222222]'}`}>
                            {message.sender_type === 'manager' ? t('chat.manager') : outbound ? 'Bot' : t('chat.customer')} · {formatDate(message.created_at)}{message.intent ? ` · ${message.intent}` : ''}
                          </p>
                        </div>
                      </motion.div>
                    );
                  })}
                </AnimatePresence>
              </div>

              <form
                className="mt-5 rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  void sendManualMessage();
                }}
              >
                <label className="text-xs font-semibold uppercase tracking-[0.16em] text-[#222222]" htmlFor="manual-chat-message">
                  {t('chat.replyLabel')}
                </label>
                <textarea
                  id="manual-chat-message"
                  className={`${inputClass} mt-2 min-h-24 resize-y`}
                  value={draftMessage}
                  onChange={(event) => setDraftMessage(event.target.value)}
                  placeholder={t('chat.replyPlaceholder')}
                  disabled={sendingMessage || selectedConversation.mode === 'closed'}
                />
                <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <p className="text-xs font-medium text-[#222222]">
                    {isMessagingWindowOpen(selectedConversation.messaging_window_expires_at)
                      ? t('chat.replyWindowHint')
                      : t('chat.replyWindowClosedHint')}
                  </p>
                  <button
                    type="submit"
                    className={primaryButtonClass}
                    disabled={sendingMessage || !companyId || !draftMessage.trim() || selectedConversation.mode === 'closed'}
                  >
                    {sendingMessage ? <Spinner label={t('chat.sending')} /> : t('chat.send')}
                  </button>
                </div>
              </form>
            </div>
          )}
        </motion.div>
      </div>
    </section>
  );
}
