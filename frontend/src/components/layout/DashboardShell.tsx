import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import {
  LayoutDashboard,
  BarChart3,
  ShoppingCart,
  MessageSquare,
  Phone,
  BookOpen,
  Users,
  MessagesSquare,
  Settings,
  LogOut,
  ChevronLeft,
  ChevronRight,
} from 'lucide-react';
import type { CurrentUser } from '../../api';
import { useI18n } from '../../i18n';
import { WhatsAppIcon, InstagramIcon, TikTokIcon } from '../ui/SocialIcons';

export type NavItem = {
  id: string;
  label: string;
  icon: ReactNode;
};

type DashboardShellProps = {
  user: CurrentUser;
  onLogout: () => void;
  badge: string;
  title: string;
  subtitle?: string;
  navItems: NavItem[];
  activeNav: string;
  onNavChange: (id: string) => void;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  children: ReactNode;
};

export function DashboardShell({
  user,
  onLogout,
  badge,
  title,
  navItems,
  activeNav,
  onNavChange,
  collapsed = false,
  onToggleCollapse,
  children,
}: DashboardShellProps) {
  const { t } = useI18n();

  return (
    <div className="flex min-h-screen bg-[#fcfcfc]">
      {/* ─── Sidebar ────────────────────────────────────────── */}
      <motion.aside
        initial={{ opacity: 0, x: -12 }}
        animate={{ opacity: 1, x: 0 }}
        className={`sticky top-0 flex h-screen flex-col border-r border-[#e2e4e9] bg-white transition-all duration-200 ${
          collapsed ? 'w-[72px]' : 'w-[240px]'
        }`}
      >
        {/* Logo */}
        <div className="flex h-16 items-center gap-3 border-b border-[#e2e4e9] px-4">
          <img src="/logo.svg" alt="Codev" className="h-9 w-9 shrink-0 rounded-xl" />
          {!collapsed && (
            <div className="min-w-0">
              <p className="truncate text-[11px] font-semibold uppercase tracking-[0.12em] text-[#145aff]">
                {badge}
              </p>
              <h1 className="truncate text-sm font-semibold text-[#020520]">{title}</h1>
            </div>
          )}
        </div>

        {/* Navigation */}
        <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {navItems.map((item) => {
            const active = activeNav === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavChange(item.id)}
                title={collapsed ? item.label : undefined}
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition duration-150 ${
                  active
                    ? 'bg-[#f0f4fe] text-[#145aff]'
                    : 'text-[#696a72] hover:bg-[#f5f5f5] hover:text-[#020520]'
                } ${collapsed ? 'justify-center' : ''}`}
              >
                <span className="shrink-0">{item.icon}</span>
                {!collapsed && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        {/* Bottom section */}
        <div className="border-t border-[#e2e4e9] p-3">
          {/* Collapse toggle */}
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="flex w-full items-center justify-center gap-2 rounded-xl px-3 py-2 text-sm font-medium text-[#696a72] transition hover:bg-[#f5f5f5] hover:text-[#020520]"
            >
              {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
              {!collapsed && <span>Свернуть</span>}
            </button>
          )}

          {/* User info */}
          {!collapsed && (
            <div className="mt-2 rounded-xl border border-[#e2e4e9] p-3">
              <span className="block truncate text-sm font-semibold text-[#020520]">
                {user.email}
              </span>
              <span className="mt-0.5 block text-xs text-[#696a72]">
                {user.role === 'admin' ? t('role.admin') : t('role.company')}
              </span>
            </div>
          )}

          {/* Logout */}
          <button
            type="button"
            onClick={onLogout}
            className={`mt-2 flex w-full items-center gap-2 rounded-xl border border-[#e2e4e9] px-3 py-2.5 text-sm font-medium text-[#696a72] transition hover:border-[#145aff] hover:text-[#145aff] ${
              collapsed ? 'justify-center' : ''
            }`}
          >
            <LogOut size={18} />
            {!collapsed && <span>{t('action.logout')}</span>}
          </button>
        </div>
      </motion.aside>

      {/* ─── Main content ───────────────────────────────────── */}
      <main className="flex-1 overflow-auto">
        <div className="mx-auto max-w-[1400px] p-6">
          {/* Header */}
          <motion.header
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-6 rounded-2xl border border-[#e2e4e9] bg-white px-6 py-5"
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#145aff]">
                  Codev
                </p>
                <h2 className="mt-1 text-xl font-semibold tracking-[-0.02em] text-[#020520]">
                  {navItems.find((n) => n.id === activeNav)?.label ?? title}
                </h2>
              </div>
            </div>
          </motion.header>

          {children}
        </div>
      </main>
    </div>
  );
}
