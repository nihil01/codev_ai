import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight, Mail, Lock } from 'lucide-react';
import { api } from '../../api';
import type { CurrentUser } from '../../api';
import { Alert } from '../../components/ui/Alert';
import { Spinner } from '../../components/ui/Spinner';
import { clearSession, saveCurrentUser, saveSession } from '../../services/session';
import { navigate } from '../../services/navigation';
import { useI18n } from '../../i18n';

type LoginFormProps = {
  onLogin: (user: CurrentUser) => void;
};

export function LoginForm({ onLogin }: LoginFormProps) {
  const { t } = useI18n();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  async function handleLogin(event: FormEvent) {
    event.preventDefault();

    setLoading(true);
    setError('');

    try {
      const response = await api.login(email.trim(), password);

      saveSession(response);

      const current = await api.getCurrentUser();
      const currentUser = {
        ...current,
        company_id: current.company_id ?? response.company_id,
        ig_activated: current.ig_activated ?? false,
        wp_activated: current.wp_activated ?? false,
        ig_enabled: current.ig_enabled ?? false,
        wp_enabled: current.wp_enabled ?? false,
      };

      saveCurrentUser(currentUser);
      onLogin(currentUser);

      navigate('/');
    } catch (err) {
      clearSession();
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <form onSubmit={handleLogin} className="space-y-7">
      <div>
        <h2 className="text-[28px] font-bold tracking-[-0.03em] text-[#18261d]">
          {t('auth.companyLogin')}
        </h2>
        <p className="mt-2.5 text-sm leading-relaxed text-[#708078]">
          {t('auth.companyFormHint')}
        </p>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      <div className="space-y-4">
        <div className="relative">
          <Mail className="absolute left-4 top-1/2 -translate-y-1/2 text-[#9ca8a2]" size={18} />
          <input
            className="w-full rounded-2xl border border-[#e1ebe4] bg-[#f8faf9] py-3.5 pl-12 pr-4 text-sm text-[#18261d] outline-none transition-all placeholder:text-[#9ca8a2] focus:border-[#15803d] focus:bg-white focus:ring-2 focus:ring-[#15803d]/10"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="email@example.com"
            required
            autoComplete="email"
          />
        </div>

        <div className="relative">
          <Lock className="absolute left-4 top-1/2 -translate-y-1/2 text-[#9ca8a2]" size={18} />
          <input
            className="w-full rounded-2xl border border-[#e1ebe4] bg-[#f8faf9] py-3.5 pl-12 pr-4 text-sm text-[#18261d] outline-none transition-all placeholder:text-[#9ca8a2] focus:border-[#15803d] focus:bg-white focus:ring-2 focus:ring-[#15803d]/10"
            type="password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            placeholder="••••••••"
            required
            autoComplete="current-password"
          />
        </div>
      </div>

      <button
        className="flex w-full items-center justify-center gap-2 rounded-2xl bg-gradient-to-r from-[#15803d] to-[#1a9e44] py-3.5 text-sm font-semibold text-white shadow-lg shadow-[#15803d]/20 transition-all hover:shadow-xl hover:shadow-[#15803d]/25 disabled:opacity-60"
        type="submit"
        disabled={loading}
      >
        {loading ? (
          <Spinner label={t('auth.signingIn')} />
        ) : (
          <>
            {t('auth.signIn')}
            <ArrowRight size={16} />
          </>
        )}
      </button>
    </form>
  );
}
