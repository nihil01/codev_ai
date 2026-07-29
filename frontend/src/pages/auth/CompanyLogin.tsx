import type { CurrentUser } from '../../api';
import { AuthLayout } from '../../components/layout/AuthLayout';
import { useI18n } from '../../i18n';
import { LoginForm } from './LoginForm';

type CompanyLoginProps = {
  onLogin: (user: CurrentUser) => void;
};

export function CompanyLogin({ onLogin }: CompanyLoginProps) {
  const { t } = useI18n();

  return (
    <AuthLayout
      title={t('auth.companyTitle')}
    >
      <LoginForm onLogin={onLogin} />
    </AuthLayout>
  );
}
