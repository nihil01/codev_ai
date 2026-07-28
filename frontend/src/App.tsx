import { useEffect, useState } from 'react';
import { api } from './api';
import type { CurrentUser } from './api';
import { cardClass } from './constants/styles';
import { Spinner } from './components/ui/Spinner';
import { CompanyLogin } from './pages/auth/CompanyLogin';
import { AdminPanel } from './pages/admin/AdminPanel';
import { CompanyDashboard } from './pages/company/CompanyDashboard';
import { resolveAppView } from './services/routePolicy';
import { clearSession, hasStoredToken, loadStoredUser, saveCurrentUser } from './services/session';
import { navigate } from './services/navigation';
import { useI18n } from './i18n';

export default function App() {
  const { t } = useI18n();
  const [route, setRoute] = useState(window.location.pathname);
  const [user, setUser] = useState<CurrentUser | null>(() => loadStoredUser());
  const [booting, setBooting] = useState(true);

  useEffect(() => {
    function handleRouteChange() {
      setRoute(window.location.pathname);
    }

    window.addEventListener('popstate', handleRouteChange);
    return () => window.removeEventListener('popstate', handleRouteChange);
  }, []);

  useEffect(() => {
    let cancelled = false;

    async function verifySession() {
      if (!hasStoredToken()) {
        setBooting(false);
        return;
      }

      try {
        const current = await api.getCurrentUser();
        if (!cancelled) {
          const stored = loadStoredUser();
          const verifiedUser = {
            ...current,
            company_id: current.company_id ?? stored?.company_id ?? null,
            ig_activated: current.ig_activated ?? stored?.ig_activated ?? false,
            wp_activated: current.wp_activated ?? stored?.wp_activated ?? false,
            ig_enabled: current.ig_enabled ?? stored?.ig_enabled ?? false,
            wp_enabled: current.wp_enabled ?? stored?.wp_enabled ?? false,
          };
          saveCurrentUser(verifiedUser);
          setUser(verifiedUser);
        }
      } catch {
        clearSession();
        if (!cancelled) setUser(null);
      } finally {
        if (!cancelled) setBooting(false);
      }
    }

    verifySession();
    return () => { cancelled = true; };
  }, []);

  function handleUserChange(nextUser: CurrentUser) {
    saveCurrentUser(nextUser);
    setUser(nextUser);
  }

  function handleLogout() {
    clearSession();
    setUser(null);
    navigate('/');
  }

  if (booting) {
    return (
      <main className="grid min-h-screen place-items-center bg-[#fcfcfc]">
        <div className="rounded-2xl border border-[#e2e4e9] bg-white p-8">
          <Spinner label={t('app.loadingSession')} />
        </div>
      </main>
    );
  }

  const view = resolveAppView(route, user?.role ?? null);

  if (view === 'login' || !user) {
    return <CompanyLogin onLogin={handleUserChange} />;
  }

  return user.role === 'admin'
    ? <AdminPanel user={user} onLogout={handleLogout} />
    : <CompanyDashboard user={user} onUserChange={handleUserChange} onLogout={handleLogout} />;
}
