import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Leaf, LogOut } from 'lucide-react';
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
  collapsed = false,
  onToggleCollapse,
  children,
}: DashboardShellProps) {
  const { t } = useI18n();
  const activeLabel = navItems.find((item) => item.id === activeNav)?.label ?? title;

  return (
    <div className="flex min-h-screen gap-[14px] bg-[#fffefc] p-[14px] text-[#222222] lg:p-[21px]">
      <motion.aside
        initial={{ opacity: 0, x: -12 }}
        animate={{ opacity: 1, x: 0 }}
        className={`sticky top-[14px] flex h-[calc(100vh-28px)] shrink-0 flex-col overflow-hidden rounded-[14px] bg-[#e1f4df] transition-[width] duration-200 lg:top-[21px] lg:h-[calc(100vh-42px)] ${
          collapsed ? 'w-[72px]' : 'w-[72px] lg:w-[252px]'
        }`}
      >
        <div className="flex min-h-[84px] items-center gap-[14px] border-b border-[#fffefc] px-[14px] lg:px-[18px]">
          <span className="grid h-11 w-11 shrink-0 place-items-center rounded-[14px] bg-[#0f3e17] text-[#fffefc]">
            <Leaf size={22} strokeWidth={1.6} />
          </span>
          {!collapsed && (
            <div className="hidden min-w-0 lg:block">
              <p className="eyebrow-label truncate">{badge}</p>
              <h1 className="mt-1 truncate text-[23px] leading-none text-[#0f3e17]">Codev</h1>
            </div>
          )}
        </div>

        <nav className="flex-1 space-y-[7px] overflow-y-auto p-[9px] lg:p-[14px]">
          {navItems.map((item) => {
            const active = activeNav === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => onNavChange(item.id)}
                title={collapsed ? item.label : undefined}
                className={`flex min-h-12 w-full items-center gap-[14px] rounded-[14px] px-[14px] text-sm transition-colors ${
                  active
                    ? 'bg-[#0f3e17] text-[#fffefc]'
                    : 'text-[#0f3e17] hover:bg-[#fffefc]'
                } ${collapsed ? 'justify-center' : 'justify-center lg:justify-start'}`}
              >
                <span className="shrink-0">{item.icon}</span>
                {!collapsed && <span className="hidden truncate lg:block">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-[#fffefc] p-[9px] lg:p-[14px]">
          {onToggleCollapse && (
            <button
              type="button"
              onClick={onToggleCollapse}
              className="hidden min-h-11 w-full items-center justify-center gap-[9px] rounded-[14px] px-[14px] text-sm text-[#222222] transition-colors hover:bg-[#fffefc] hover:text-[#0f3e17] lg:flex"
            >
              {collapsed ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
              {!collapsed && <span>{t('action.collapse')}</span>}
            </button>
          )}

          {!collapsed && (
            <div className="mt-[9px] hidden rounded-[14px] bg-[#fffefc] p-[14px] lg:block">
              <span className="block truncate text-sm font-normal text-[#0f3e17]">{user.email}</span>
              <span className="mt-1 block text-[10px] uppercase tracking-[0.08em] text-[#222222]">
                {user.role === 'admin' ? t('role.admin') : t('role.company')}
              </span>
            </div>
          )}

          <button
            type="button"
            onClick={onLogout}
            className={`mt-[9px] flex min-h-11 w-full items-center gap-[9px] rounded-[14px] px-[14px] text-sm text-[#222222] transition-colors hover:bg-[#fffefc] hover:text-[#0f3e17] ${
              collapsed ? 'justify-center' : 'justify-center lg:justify-start'
            }`}
          >
            <LogOut size={18} />
            {!collapsed && <span className="hidden lg:block">{t('action.logout')}</span>}
          </button>
        </div>
      </motion.aside>

      <main className="min-w-0 flex-1 overflow-auto">
        <div className="mx-auto max-w-[1200px] pb-[42px]">
          <motion.header
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            className="mb-[14px] rounded-[14px] bg-[#cfe7d3] p-7 lg:p-[42px]"
          >
            <div className="max-w-3xl">
              <p className="eyebrow-label">Codev · {badge}</p>
              <h2 className="mt-[11px] text-[40px] leading-[1.1] tracking-[-0.01em] text-[#0f3e17] lg:text-[56px] lg:tracking-[-0.03em]">
                {activeLabel}
              </h2>
              {subtitle && <p className="mt-[14px] max-w-2xl text-sm font-light leading-6 text-[#222222]">{subtitle}</p>}
            </div>
          </motion.header>

          {children}
        </div>
      </main>
    </div>
  );
}
