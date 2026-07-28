import { useEffect, useMemo, useState } from 'react';
import { api } from '../api';
import type { BotSettings, BusinessAnalytics, BusinessSettings, Channel, Conversation, KnowledgeEntry } from '../api';

export function useCompany(companyId?: string | null) {
  const [settings, setSettings] = useState<BotSettings | null>(null);
  const [channels, setChannels] = useState<Channel[]>([]);
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [knowledgeEntries, setKnowledgeEntries] = useState<KnowledgeEntry[]>([]);
  const [businessSettings, setBusinessSettings] = useState<BusinessSettings | null>(null);
  const [businessAnalytics, setBusinessAnalytics] = useState<BusinessAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const instagramChannel = channels.find((channel) => channel.platform === 'instagram');

  const stats = useMemo(() => {
    const messages = conversations.reduce(
      (total, conversation) => total + conversation.messages.length,
      0,
    );

    const inbound = conversations.reduce(
      (total, conversation) =>
        total + conversation.messages.filter((message) => message.direction === 'inbound').length,
      0,
    );

    return {
      conversations: conversations.length,
      messages,
      inbound,
    };
  }, [conversations]);

  useEffect(() => {
    let cancelled = false;

    async function loadCompany() {
      if (!companyId) {
        setSettings(null);
        setChannels([]);
        setConversations([]);
        setKnowledgeEntries([]);
        setBusinessSettings(null);
        setBusinessAnalytics(null);
        setError('');
        setLoading(false);
        return;
      }

      setLoading(true);
      setError('');

      try {
        const [botSettings, channelList, conversationList, knowledgeList, businessSettingsRow, analyticsRow] = await Promise.all([
          api.botSettings(companyId),
          api.channels(companyId),
          api.conversations(companyId).catch(() => [] as Conversation[]),
          api.knowledgeEntries(companyId).catch(() => [] as KnowledgeEntry[]),
          api.businessSettings(companyId).catch(() => null),
          api.businessAnalytics(companyId).catch(() => null),
        ]);

        if (cancelled) return;

        setSettings(botSettings);
        setChannels(channelList);
        setConversations(conversationList);
        setKnowledgeEntries(knowledgeList);
        setBusinessSettings(businessSettingsRow);
        setBusinessAnalytics(analyticsRow);
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }

    loadCompany();

    return () => {
      cancelled = true;
    };
  }, [companyId]);

  async function refreshBusinessAnalytics() {
    if (!companyId) {
      setBusinessAnalytics(null);
      return;
    }
    setBusinessAnalytics(await api.businessAnalytics(companyId).catch(() => null));
  }

  return {
    settings,
    setSettings,
    channels,
    setChannels,
    conversations,
    setConversations,
    knowledgeEntries,
    setKnowledgeEntries,
    loading,
    error,
    setError,
    instagramChannel,
    stats,
    businessSettings,
    setBusinessSettings,
    businessAnalytics,
    refreshBusinessAnalytics,
  };
}
