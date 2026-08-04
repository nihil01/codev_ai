import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import {
  Settings,
  GraduationCap,
  MessageSquare,
  BookOpen,
  Users,
  MessagesSquare,
  Send,
  LayoutDashboard,
  Link2,
} from 'lucide-react';

import { DashboardOverview } from '../../components/charts/DashboardCharts';
import { api } from '../../api';
import type { CurrentUser, InstagramIntegration } from '../../api';
import { DashboardShell } from '../../components/layout/DashboardShell';
import type { NavItem } from '../../components/layout/DashboardShell';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { useCompany } from '../../hooks/useCompany';
import { ChatExplorer } from './ChatExplorer';
import { ContactsPanel } from './ContactsPanel';
import { CustomerOrders } from './CustomerOrders';
import { CompanyInfo } from './CompanyInfo';
import { BotPromptSettings } from './BotPromptSettings';
import { InstagramComments } from './InstagramComments';

import { KnowledgeBase } from './KnowledgeBase';

import { ManagersAndBroadcasts } from './ManagersAndBroadcasts';
import { PostsSchedulerPanel } from './PostsSchedulerPanel';
import { SocialConnectionsPage } from './SocialConnectionsPage';
import type { InstagramFormState } from './InstagramSettings';
import { useI18n } from '../../i18n';

type CompanyDashboardProps = {
  user: CurrentUser;
  onUserChange: (user: CurrentUser) => void;
  onLogout: () => void;
};

type CompanySection = 'overview' | 'contacts' | 'orders' | 'comments' | 'integrations' | 'posts' | 'knowledge' | 'managers' | 'conversations' | 'settings';

export function CompanyDashboard({ user, onUserChange, onLogout }: CompanyDashboardProps) {
  const { t } = useI18n();
  const companyId = user.company_id;

  const {
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
    businessSettings,
    setBusinessSettings,
    refreshBusinessAnalytics,
  } = useCompany(companyId);

  const [activeSection, setActiveSection] = useState<CompanySection>('contacts');
  const [notice, setNotice] = useState('');
  const [collapsed, setCollapsed] = useState(false);

  const [togglingBot, setTogglingBot] = useState(false);
  const [connectingInstagram, setConnectingInstagram] = useState(false);
  const [unlinkingInstagram, setUnlinkingInstagram] = useState(false);
  const [loadingIntegration, setLoadingIntegration] = useState(Boolean(companyId));

  const [instagramIntegration, setInstagramIntegration] = useState<InstagramIntegration | null>(null);

  const [instagramForm, setInstagramForm] = useState<InstagramFormState>({
    external_account_id: '',
    display_name: '',
  });

  const instagramActivated = instagramIntegration?.ig_activated ?? user.ig_activated ?? false;
  const instagramEnabled = instagramIntegration?.ig_enabled ?? user.ig_enabled ?? false;
  const whatsappActivated = instagramIntegration?.wp_activated ?? user.wp_activated ?? false;
  const hasActiveBot = instagramActivated || whatsappActivated;

  const navItems = useMemo<NavItem[]>(() => {
    const items: NavItem[] = [
      { id: 'overview', label: t('tabs.overview'), icon: <LayoutDashboard size={18} /> },
      { id: 'contacts', label: t('tabs.contacts'), icon: <Users size={18} /> },
      { id: 'orders', label: t('tabs.orders'), icon: <GraduationCap size={18} /> },
      { id: 'comments', label: t('tabs.comments'), icon: <MessageSquare size={18} /> },
      { id: 'integrations', label: 'Bağlantılar', icon: <Link2 size={18} /> },
      { id: 'posts', label: t('tabs.posts'), icon: <Send size={18} /> },
      { id: 'knowledge', label: t('tabs.knowledge'), icon: <BookOpen size={18} /> },
      { id: 'managers', label: t('tabs.managers'), icon: <Users size={18} /> },
      { id: 'conversations', label: t('tabs.conversations'), icon: <MessagesSquare size={18} /> },
      { id: 'settings', label: t('tabs.settings'), icon: <Settings size={18} /> },
    ];

    if (!hasActiveBot) {
      return items.filter((item) =>
        item.id === 'contacts' ||
        item.id === 'integrations' ||
        item.id === 'posts' ||
        item.id === 'settings',
      );
    }

    return items;
  }, [hasActiveBot, t]);

  useEffect(() => {
    let cancelled = false;

    async function loadInstagramIntegration() {
      if (!companyId) {
        setLoadingIntegration(false);
        return;
      }
      setLoadingIntegration(true);
      try {
        const integration = await api.instagramIntegration(companyId);
        if (cancelled) return;
        const normalizedIntegration: InstagramIntegration = {
          ...integration,
          ig_activated: Boolean(user.ig_activated || integration.ig_activated),
          wp_activated: Boolean(user.wp_activated || integration.wp_activated),
          ig_enabled: Boolean(integration.ig_enabled),
          wp_enabled: Boolean(integration.wp_enabled),
        };
        setInstagramIntegration(normalizedIntegration);
        onUserChange({
          ...user,
          ig_activated: normalizedIntegration.ig_activated,
          wp_activated: normalizedIntegration.wp_activated,
          ig_enabled: normalizedIntegration.ig_enabled,
          wp_enabled: normalizedIntegration.wp_enabled,
        });
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : String(err));
      } finally {
        if (!cancelled) setLoadingIntegration(false);
      }
    }

    loadInstagramIntegration();
    return () => { cancelled = true; };
  }, [companyId]);

  const dashboardReady = !loading && !loadingIntegration;

  useEffect(() => {
    const instagram = channels.find((channel) => channel.platform === 'instagram');
    setInstagramForm({
      external_account_id: instagram?.external_account_id ?? '',
      display_name: instagram?.display_name ?? '',
    });
  }, [channels]);

  useEffect(() => {
    if (!navItems.some((item) => item.id === activeSection)) {
      setActiveSection('contacts');
    }
  }, [activeSection, navItems]);

  function applyInstagramIntegration(integration: InstagramIntegration) {
    setInstagramIntegration(integration);
    onUserChange({
      ...user,
      ig_activated: integration.ig_activated,
      wp_activated: integration.wp_activated,
      ig_enabled: integration.ig_enabled,
      wp_enabled: integration.wp_enabled,
    });
    setChannels((current) =>
      current.map((channel) =>
        channel.platform === 'instagram'
          ? { ...channel, is_enabled: integration.ig_enabled }
          : channel,
      ),
    );
    if (!integration.ig_activated) {
      setInstagramForm({ external_account_id: '', display_name: '' });
    }
  }

  function applyWhatsAppActivation(activated: boolean) {
    setInstagramIntegration((current) => current ? {
      ...current,
      wp_activated: activated,
      wp_enabled: activated ? true : current.wp_enabled,
    } : current);
    onUserChange({
      ...user,
      wp_activated: activated,
      wp_enabled: activated ? true : user.wp_enabled,
    });
  }

  async function connectInstagram() {
    if (!companyId) return;
    let oauthWindow: Window | null = null;
    try {
      oauthWindow = window.open('', '_blank');
      if (oauthWindow) {
        oauthWindow.document.write(`<p style="font-family: system-ui, sans-serif; padding: 24px;">${t('dashboard.connectionPreparing')}</p>`);
      }
    } catch { oauthWindow = null; }

    setConnectingInstagram(true);
    setError('');
    setNotice('');

    try {
      const { auth_url } = await api.connectInstagram(companyId);
      if (!auth_url) throw new Error(t('dashboard.emptyOAuthUrl'));
      if (oauthWindow) oauthWindow.location.href = auth_url;
      else window.location.assign(auth_url);
      setNotice(t('dashboard.instagramOAuthOpened'));
    } catch (err) {
      if (oauthWindow && !oauthWindow.closed) oauthWindow.close();
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setConnectingInstagram(false);
    }
  }

  async function toggleInstagramBot() {
    if (!companyId) return;
    if (!instagramActivated) { setError(t('dashboard.connectInstagramFirst')); return; }
    setTogglingBot(true);
    setError('');
    setNotice('');
    try {
      const integration = await api.updateInstagramBotStatus(companyId, !instagramEnabled);
      applyInstagramIntegration(integration);
      setNotice(integration.ig_enabled ? t('dashboard.instagramBotEnabled') : t('dashboard.instagramBotDisabled'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setTogglingBot(false);
    }
  }

  async function unlinkInstagram() {
    if (!companyId) return;
    if (!window.confirm(t('dashboard.confirmUnlinkInstagram'))) return;
    setUnlinkingInstagram(true);
    setError('');
    setNotice('');
    try {
      const integration = await api.deauthorizeInstagram(companyId);
      applyInstagramIntegration(integration);
      const current = await api.getCurrentUser();
      onUserChange(current);
      setInstagramIntegration(null);
      setChannels([]);
      setConversations([]);
      setNotice(t('dashboard.instagramUnlinked'));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setUnlinkingInstagram(false);
    }
  }

  function renderContent() {
    switch (activeSection) {
      case 'overview':
        return (
          <DashboardOverview
            companyId={companyId}
            igActivated={instagramActivated}
            wpActivated={whatsappActivated}
          />
        );
      case 'contacts':
        return <ContactsPanel companyId={companyId} onError={setError} onNotice={setNotice} />;

      case 'orders':
        return <CustomerOrders companyId={companyId} setError={setError} setNotice={setNotice} onAnalyticsChange={refreshBusinessAnalytics} />;
      case 'comments':
        return <InstagramComments companyId={companyId} setError={setError} setNotice={setNotice} />;
      case 'integrations':
        return (
          <SocialConnectionsPage
            companyId={companyId}
            instagramForm={instagramForm}
            instagramIntegration={instagramIntegration}
            instagramActivated={instagramActivated}
            instagramEnabled={instagramEnabled}
            connectingInstagram={connectingInstagram}
            togglingInstagram={togglingBot}
            unlinkingInstagram={unlinkingInstagram}
            onConnectInstagram={connectInstagram}
            onToggleInstagramBot={toggleInstagramBot}
            onUnlinkInstagram={unlinkInstagram}
            onWhatsAppActivationChange={applyWhatsAppActivation}
            setError={setError}
            setNotice={setNotice}
          />
        );
      case 'posts':
        return <PostsSchedulerPanel companyId={companyId} onError={setError} onNotice={setNotice} />;
      case 'knowledge':
        return (
          <KnowledgeBase
            companyId={companyId}
            entries={knowledgeEntries}
            setEntries={setKnowledgeEntries}
            loading={loading}
            setError={setError}
            setNotice={setNotice}
          />
        );
      case 'managers':
        return <ManagersAndBroadcasts companyId={companyId} setError={setError} setNotice={setNotice} />;
      case 'conversations':
        return <ChatExplorer companyId={companyId} conversations={conversations} setConversations={setConversations} setError={setError} />;
      case 'settings':
        return (
          <div className="space-y-6">
            <CompanyInfo
              companyId={companyId}
              email={user.email}
              instagramChannel={instagramChannel}
              businessSettings={businessSettings}
              onError={setError}
              onNotice={setNotice}
            />
            <BotPromptSettings companyId={companyId} onError={setError} onNotice={setNotice} />
          </div>
        );
    }
  }

  return (
    <DashboardShell
      user={user}
      onLogout={onLogout}
      title={t('company.title')}
      navItems={navItems}
      activeNav={activeSection}
      onNavChange={(id) => setActiveSection(id as CompanySection)}
      hidePageHeader={activeSection === 'overview'}
      collapsed={collapsed}
      onToggleCollapse={() => setCollapsed(!collapsed)}
    >
      {!dashboardReady ? (
        <div className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-8">
          <div className="flex flex-col gap-5 sm:flex-row sm:items-center sm:justify-between">
            <Spinner label={t('company.loading')} />
            <div className="grid flex-1 gap-3 sm:grid-cols-3">
              <div className="h-12 rounded-[24px] bg-[#e4f5e9]" />
              <div className="h-12 rounded-[24px] bg-[#e4f5e9]/60" />
              <div className="h-12 rounded-[24px] bg-[#e4f5e9]/30" />
            </div>
          </div>
        </div>
      ) : (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-6">
          {error && <Alert type="error">{error}</Alert>}
          {notice && <Alert type="success">{notice}</Alert>}

          <AnimatePresence mode="wait">
            <motion.div
              key={activeSection}
              initial={{ opacity: 0, y: 8 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -6 }}
              transition={{ duration: 0.18 }}
            >
              {renderContent()}
            </motion.div>
          </AnimatePresence>
        </motion.div>
      )}
    </DashboardShell>
  );
}
