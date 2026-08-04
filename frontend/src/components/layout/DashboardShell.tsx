import { useEffect, useRef, useState, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, LogOut, Menu, X } from 'lucide-react';
import codevLogo from '../../assets/codev-logo.png';
import type { CurrentUser } from '../../api';
import { useI18n } from '../../i18n';

export type NavItem = { id: string; label: string; icon: ReactNode };

type DashboardShellProps = {
  user: CurrentUser;
  onLogout: () => void;
  title: string;
  subtitle?: string;
  navItems: NavItem[];
  activeNav: string;
  onNavChange: (id: string) => void;
  hidePageHeader?: boolean;
  collapsed?: boolean;
  onToggleCollapse?: () => void;
  children: ReactNode;
};

export function DashboardShell({
  user,
  onLogout,
  title,
  subtitle,
  navItems,
  activeNav,
  onNavChange,
  hidePageHeader = false,
  collapsed = false,
  onToggleCollapse,
  children,
}: DashboardShellProps) {
  const { t } = useI18n();
  const [mobileOpen, setMobileOpen] = useState(false);
  const mobileDialogRef = useRef<HTMLElement>(null);
  const mobileTriggerRef = useRef<HTMLButtonElement>(null);
  const activeLabel = navItems.find((item) => item.id === activeNav)?.label ?? title;

  function closeMobileMenu() {
    setMobileOpen(false);
  }

  useEffect(() => {
    if (!mobileOpen) return;
    const dialog = mobileDialogRef.current;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    dialog?.querySelector<HTMLElement>('[data-autofocus]')?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') closeMobileMenu();
      if (event.key !== 'Tab' || !dialog) return;
      const focusable = Array.from(dialog.querySelectorAll<HTMLElement>('button:not(:disabled), a[href], [tabindex]:not([tabindex="-1"])'));
      if (!focusable.length) return;
      const first = focusable[0];
      const last = focusable[focusable.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.style.overflow = previousOverflow;
      mobileTriggerRef.current?.focus();
    };
  }, [mobileOpen]);

  function Navigation({ compact, mobile = false }: { compact: boolean; mobile?: boolean }) {
    return (
      <>
        <div className="flex h-20 items-center gap-3 border-b border-[#e1ebe4] px-4">
          <img src={codevLogo} alt="Codev" className={`h-auto shrink-0 ${compact ? 'w-10 object-cover object-left' : 'w-[132px]'}`} />
          {mobile && <button data-autofocus type="button" onClick={closeMobileMenu} className="ml-auto rounded-full p-2 hover:bg-[#e4f5e9]" aria-label="Menyunu bağla"><X size={20} /></button>}
        </div>
        <nav aria-label="Əsas naviqasiya" className="flex-1 space-y-1 overflow-y-auto px-3 py-4">
          {navItems.map((item) => {
            const active = activeNav === item.id;
            return (
              <button
                key={item.id}
                type="button"
                title={compact ? item.label : undefined}
                onClick={() => { onNavChange(item.id); closeMobileMenu(); }}
                className={`flex w-full items-center gap-3 rounded-full px-3 py-2.5 text-sm font-medium transition-colors ${compact ? 'justify-center' : ''} ${active ? 'bg-gradient-to-r from-[#15803d] to-[#4fbf73] text-white' : 'text-[#708078] hover:bg-[#e4f5e9] hover:text-[#18261d]'}`}
              >
                <span className="shrink-0">{item.icon}</span>
                {!compact && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>
        <div className="border-t border-[#e1ebe4] p-3">
          {!mobile && onToggleCollapse && (
            <button type="button" onClick={onToggleCollapse} aria-label={compact ? 'Menyunu genişləndir' : 'Menyunu yığ'} className="flex w-full items-center justify-center gap-2 rounded-full px-3 py-2 text-sm font-medium text-[#708078] hover:bg-[#e4f5e9]">
              {compact ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}{!compact && <span>Yığ</span>}
            </button>
          )}
          {!compact && <div className="mt-2 rounded-[24px] border border-[#e1ebe4] p-3"><span className="block truncate text-sm font-medium text-[#18261d]">{user.email}</span><span className="block text-xs text-[#708078]">{user.role === 'admin' ? t('role.admin') : t('role.company')}</span></div>}
          <button type="button" onClick={onLogout} aria-label={t('action.logout')} className={`mt-2 flex w-full items-center gap-2 rounded-full border border-[#e1ebe4] px-3 py-2.5 text-sm font-medium text-[#708078] hover:border-[#15803d] hover:text-[#18261d] ${compact ? 'justify-center' : ''}`}>
            <LogOut size={18} />{!compact && <span>{t('action.logout')}</span>}
          </button>
        </div>
      </>
    );
  }

  return (
    <div className="min-h-screen bg-[#f3faf5] text-[#18261d] lg:flex">
      {navItems.length > 0 && (
        <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-[#e1ebe4] bg-white transition-[width] duration-200 lg:flex ${collapsed ? 'w-[76px]' : 'w-[250px]'}`}>
          <Navigation compact={collapsed} />
        </aside>
      )}

      {mobileOpen && navItems.length > 0 && (
        <div className="fixed inset-0 z-50 bg-[#18261d]/40 lg:hidden" onMouseDown={(event) => { if (event.target === event.currentTarget) closeMobileMenu(); }}>
          <motion.aside ref={mobileDialogRef} role="dialog" aria-modal="true" aria-label="Əsas menyu" tabIndex={-1} initial={{ x: -300 }} animate={{ x: 0 }} className="flex h-full w-[min(88vw,320px)] flex-col bg-white">
            <Navigation compact={false} mobile />
          </motion.aside>
        </div>
      )}

      <main aria-hidden={mobileOpen || undefined} className="min-w-0 flex-1 overflow-x-hidden">
        <header className="sticky top-0 z-40 flex h-16 items-center gap-3 border-b border-[#e1ebe4] bg-white/95 px-4 backdrop-blur lg:hidden">
          {navItems.length > 0 && <button ref={mobileTriggerRef} type="button" onClick={() => setMobileOpen(true)} aria-label="Menyunu aç" aria-expanded={mobileOpen} className="rounded-full border border-[#e1ebe4] p-2 text-[#18261d]"><Menu size={21} /></button>}
          <img src={codevLogo} alt="Codev" className="h-auto w-[104px]" />
          <span className="min-w-0 truncate text-sm font-semibold">{activeLabel}</span>
        </header>

        <div className="mx-auto w-full max-w-[1500px] p-3 sm:p-5 lg:p-7">
          {!hidePageHeader && (
            <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-5 rounded-[28px] border border-[#e1ebe4] bg-white px-5 py-6 sm:px-8 sm:py-8">
              <h1 className="text-3xl font-bold tracking-[-0.035em] sm:text-4xl"><span className="gradient-text">{activeLabel}</span></h1>
              {subtitle && <p className="mt-3 max-w-2xl text-sm leading-6 text-[#708078]">{subtitle}</p>}
            </motion.section>
          )}
          {children}
        </div>
      </main>
    </div>
  );
}
