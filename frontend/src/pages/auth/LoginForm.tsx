import { useState } from 'react';
import type { FormEvent } from 'react';
import { api } from '../../api';
import type { CurrentUser } from '../../api';
import { inputClass, primaryButtonClass } from '../../constants/styles';
import { Alert } from '../../components/ui/Alert';
import { Field } from '../../components/ui/Field';
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
        <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-[#0f3e17]">
          {t('auth.companyFormEyebrow')}
        </p>

        <h2 className="mt-3 text-3xl font-light tracking-tight text-[#0f3e17]">
          {t('auth.companyLogin')}
        </h2>

        <p className="mt-2 text-sm leading-6 text-[#222222]">
          {t('auth.companyFormHint')}
        </p>
      </div>

      {error && <Alert type="error">{error}</Alert>}

      <Field label="Email">
        <input
          className={inputClass}
          type="email"
          value={email}
          onChange={(event) => setEmail(event.target.value)}
          placeholder="email@example.com"
          required
          autoComplete="email"
        />
      </Field>

      <Field label={t('auth.password')}>
        <input
          className={inputClass}
          type="password"
          value={password}
          onChange={(event) => setPassword(event.target.value)}
          placeholder="••••••••"
          required
          autoComplete="current-password"
        />
      </Field>

      <button className={`${primaryButtonClass} w-full`} type="submit" disabled={loading}>
        {loading ? <Spinner label={t('auth.signingIn')} /> : t('auth.signIn')}
      </button>
    </form>
  );
}
