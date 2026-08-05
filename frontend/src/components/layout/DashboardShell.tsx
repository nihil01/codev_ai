import { useEffect, useRef, useState, type ReactNode } from 'react';
import { motion } from 'framer-motion';
import { ChevronLeft, ChevronRight, Menu, X } from 'lucide-react';
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
        <div className="flex h-16 items-center gap-3 border-b border-[#e1ebe4] px-4">
          <img src={codevLogo} alt="Codev" className={`h-auto shrink-0 ${compact ? 'w-9 object-cover object-left' : 'w-[120px]'}`} />
          {mobile && <button data-autofocus type="button" onClick={closeMobileMenu} className="ml-auto rounded-xl p-2 hover:bg-[#e4f5e9]" aria-label="Menyunu bağla"><X size={20} /></button>}
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
                className={`flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-all ${compact ? 'justify-center' : ''} ${active ? 'bg-[#15803d] text-white shadow-sm shadow-[#15803d]/20' : 'text-[#708078] hover:bg-[#e4f5e9] hover:text-[#18261d]'}`}
              >
                <span className="shrink-0">{item.icon}</span>
                {!compact && <span className="truncate">{item.label}</span>}
              </button>
            );
          })}
        </nav>

        <div className="border-t border-[#e1ebe4] p-3">
          {!mobile && onToggleCollapse && (
            <button type="button" onClick={onToggleCollapse} aria-label={compact ? 'Genişləndir' : 'Yığ'}
              className="flex w-full items-center justify-center rounded-xl px-3 py-2 text-[#708078] hover:bg-[#e4f5e9]">
              {compact ? <ChevronRight size={18} /> : <ChevronLeft size={18} />}
            </button>
          )}
          <button type="button" onClick={onLogout} aria-label={t('action.logout')}
            className={`mt-2 flex w-full items-center gap-2.5 rounded-xl px-3 py-2.5 text-sm font-medium text-[#708078] transition hover:bg-red-50 hover:text-red-600 ${compact ? 'justify-center' : ''}`}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
              <polyline points="16 17 21 12 16 7" />
              <line x1="21" y1="12" x2="9" y2="12" />
            </svg>
            {!compact && <span>Çıxış</span>}
          </button>
        </div>
      </>
    );
  }

  return (
    <div className="min-h-screen bg-[#f3faf5] text-[#18261d] lg:flex">
      {navItems.length > 0 && (
        <aside className={`sticky top-0 hidden h-screen shrink-0 flex-col border-r border-[#e1ebe4] bg-white transition-[width] duration-200 lg:flex ${collapsed ? 'w-[72px]' : 'w-[240px]'}`}>
          <Navigation compact={collapsed} />
        </aside>
      )}

      {mobileOpen && navItems.length > 0 && (
        <div className="fixed inset-0 z-50 bg-[#18261d]/40 lg:hidden" onMouseDown={(event) => { if (event.target === event.currentTarget) closeMobileMenu(); }}>
          <motion.aside ref={mobileDialogRef} role="dialog" aria-modal="true" aria-label="Əsas menyu" tabIndex={-1} initial={{ x: -300 }} animate={{ x: 0 }} className="flex h-full w-[min(88vw,300px)] flex-col bg-white">
            <Navigation compact={false} mobile />
          </motion.aside>
        </div>
      )}

      <main aria-hidden={mobileOpen || undefined} className="min-w-0 flex-1 overflow-x-hidden">
        <header className="sticky top-0 z-40 flex h-14 items-center gap-3 border-b border-[#e1ebe4] bg-white/95 px-4 backdrop-blur lg:hidden">
          {navItems.length > 0 && <button ref={mobileTriggerRef} type="button" onClick={() => setMobileOpen(true)} aria-label="Menyunu aç" aria-expanded={mobileOpen} className="rounded-xl border border-[#e1ebe4] p-2 text-[#18261d]"><Menu size={20} /></button>}
          <img src={codevLogo} alt="Codev" className="h-auto w-[96px]" />
          <span className="min-w-0 truncate text-sm font-semibold">{activeLabel}</span>
        </header>

        <div className="mx-auto w-full max-w-[1400px] p-3 sm:p-5 lg:p-6">
          {!hidePageHeader && (
            <motion.section initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="mb-5 rounded-[24px] border border-[#e1ebe4] bg-white px-5 py-5 sm:px-7 sm:py-6">
              <h1 className="text-[26px] font-bold tracking-[-0.03em] text-[#18261d] sm:text-3xl">{activeLabel}</h1>
              {subtitle && <p className="mt-2 max-w-2xl text-sm leading-6 text-[#708078]">{subtitle}</p>}
            </motion.section>
          )}
          {children}
        </div>
      </main>
    </div>
  );
}
