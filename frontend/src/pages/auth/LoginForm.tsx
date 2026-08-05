import { useState } from 'react';
import type { FormEvent } from 'react';
import { ArrowRight } from 'lucide-react';
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
    <form onSubmit={handleLogin} className="space-y-6">
      <div>
        <h2 className="text-[26px] font-bold tracking-[-0.02em] text-[#18261d]">
          {t('auth.companyLogin')}
        </h2>
        <p className="mt-2 text-[14px] leading-relaxed text-[#708078]">
          {t('auth.companyFormHint')}
        </p>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      <div className="space-y-4">
        <div>
          <label className="mb-1.5 block text-[13px] font-semibold text-[#586b60]">Email</label>
          <input
            className="w-full rounded-xl border border-[#e1ebe4] bg-[#f8faf9] px-4 py-3 text-[14px] text-[#18261d] outline-none transition placeholder:text-[#b0beb5] focus:border-[#15803d] focus:bg-white"
            type="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="email@example.com"
            required
            autoComplete="email"
          />
        </div>

        <div>
          <label className="mb-1.5 block text-[13px] font-semibold text-[#586b60]">{t('auth.password')}</label>
          <input
            className="w-full rounded-xl border border-[#e1ebe4] bg-[#f8faf9] px-4 py-3 text-[14px] text-[#18261d] outline-none transition placeholder:text-[#b0beb5] focus:border-[#15803d] focus:bg-white"
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
        className="flex w-full items-center justify-center gap-2 rounded-xl bg-[#15803d] py-3 text-[14px] font-semibold text-white transition hover:bg-[#12702e] disabled:opacity-50"
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
