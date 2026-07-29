import type { ReactNode } from 'react';
import { cardClass } from '../../constants/styles';
import { Spinner } from '../ui/Spinner';

type SocialIntegrationLayoutProps = {
  icon: ReactNode;
  title: string;
  subtitle: string;
  connected: boolean;
  connectedLabel: string;
  disconnectedLabel: string;
  loading?: boolean;
  loadingLabel?: string;
  accountTitle: string;
  accountContent: ReactNode;
  actionsTitle: string;
  actions: ReactNode;
  messages?: ReactNode;
};

export function SocialIntegrationLayout({
  icon,
  title,
  subtitle,
  connected,
  connectedLabel,
  disconnectedLabel,
  loading = false,
  loadingLabel = '',
  accountTitle,
  accountContent,
  actionsTitle,
  actions,
  messages,
}: SocialIntegrationLayoutProps) {
  return (
    <section className="space-y-6">
      <div className={cardClass}>
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex items-start gap-4">
            <span className="rounded-[24px] bg-[#e4f5e9] p-4 text-[#15803d]">{icon}</span>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.3em] text-[#708078]">Sosial şəbəkə</p>
              <h2 className="mt-2 text-2xl font-light tracking-[-0.02em] text-[#18261d]">{title}</h2>
              <p className="mt-2 max-w-2xl text-sm leading-6 text-[#708078]">{subtitle}</p>
            </div>
          </div>
          <span className="rounded-full bg-[#e4f5e9] px-4 py-2 text-sm font-semibold text-[#18261d]">
            {connected ? connectedLabel : disconnectedLabel}
          </span>
        </div>
      </div>

      {messages}

      <div className={cardClass}>
        {loading ? (
          <Spinner label={loadingLabel} />
        ) : (
          <div className="grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="rounded-[24px] border border-[#e1ebe4] bg-white p-5">
              <h3 className="text-lg font-light text-[#18261d]">{accountTitle}</h3>
              <div className="mt-4">{accountContent}</div>
            </div>
            <div className="rounded-[24px] border border-[#e1ebe4] bg-white p-5">
              <h3 className="text-lg font-light text-[#18261d]">{actionsTitle}</h3>
              <div className="mt-4 grid gap-3">{actions}</div>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
