import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { Leaf, LogOut } from 'lucide-react';
import type { CurrentUser } from '../../api';
import { useI18n } from '../../i18n';

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
  subtitle,
  navItems,
  activeNav,
  onNavChange,
  children,
}: DashboardShellProps) {
  const { t } = useI18n();
  const activeLabel = navItems.find((item) => item.id === activeNav)?.label ?? title;

  return (
    <div className="min-h-screen bg-[#f3faf5] text-[#18261d]">
      <header className="sticky top-0 z-40 border-b border-[#e1ebe4] bg-white/95 backdrop-blur">
        <div className="mx-auto flex min-h-20 max-w-[1200px] items-center justify-between gap-4 px-4 sm:px-6">
          <div className="flex min-w-0 items-center gap-3">
            <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full bg-gradient-to-r from-[#15803d] to-[#4fbf73] text-white">
              <Leaf size={21} strokeWidth={1.8} />
            </span>
            <div className="min-w-0">
              <p className="truncate text-lg font-bold tracking-[-0.03em] text-[#18261d]">Codev</p>
              <p className="truncate text-xs font-medium text-[#708078]">{badge}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <div className="hidden text-right sm:block">
              <p className="max-w-64 truncate text-sm font-medium text-[#18261d]">{user.email}</p>
              <p className="text-xs text-[#708078]">{user.role === 'admin' ? t('role.admin') : t('role.company')}</p>
            </div>
            <button
              type="button"
              onClick={onLogout}
              aria-label={t('action.logout')}
              className="inline-flex h-11 items-center gap-2 rounded-full border border-[#e1ebe4] bg-white px-4 text-sm font-medium text-[#708078] transition-colors hover:border-[#15803d] hover:bg-[#e4f5e9] hover:text-[#18261d]"
            >
              <LogOut size={17} />
              <span className="hidden sm:inline">{t('action.logout')}</span>
            </button>
          </div>
        </div>

        <nav className="mx-auto flex max-w-[1200px] gap-2 overflow-x-auto px-4 pb-4 sm:px-6" aria-label="Workspace navigation">
          {navItems.map((item) => {
            const active = activeNav === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavChange(item.id)}
                className={`inline-flex min-h-10 shrink-0 items-center gap-2 rounded-full px-4 text-sm font-medium transition-colors ${
                  active
                    ? 'bg-gradient-to-r from-[#15803d] to-[#4fbf73] text-white'
                    : 'border border-[#e1ebe4] bg-white text-[#708078] hover:border-[#15803d] hover:bg-[#e4f5e9] hover:text-[#18261d]'
                }`}
              >
                <span className="shrink-0">{item.icon}</span>
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>
      </header>

      <main className="mx-auto max-w-[1200px] px-4 py-8 sm:px-6 sm:py-12">
        <motion.section
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          className="mb-6 rounded-[24px] border border-[#e1ebe4] bg-white p-6 sm:p-8"
        >
          <p className="eyebrow-label">Codev · {badge}</p>
          <h1 className="mt-3 text-4xl font-bold leading-tight tracking-[-0.035em] sm:text-[44px]">
            <span className="gradient-text">{activeLabel}</span>
          </h1>
          {subtitle && <p className="mt-4 max-w-2xl text-base leading-7 text-[#708078]">{subtitle}</p>}
        </motion.section>

        {children}
      </main>
    </div>
  );
}
