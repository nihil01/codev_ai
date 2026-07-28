import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { useI18n } from '../../i18n';

type AuthLayoutProps = {
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export function AuthLayout({ eyebrow, title, subtitle, children }: AuthLayoutProps) {
  const { t } = useI18n();
  const features = [t('auth.featuresAi'), t('auth.featuresDirect'), t('auth.featuresCrm')];

  return (
    <main className="min-h-screen bg-[#fcfcfc] px-4 py-8 text-[#020520] sm:px-6 lg:px-8">
      <div className="mx-auto grid min-h-[calc(100vh-4rem)] max-w-5xl items-center gap-12 lg:grid-cols-[1fr_1fr]">
        {/* Left: branding */}
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="space-y-8"
        >
          <div>
            <img src="/logo.svg" alt="Codev" className="mb-6 h-14 w-14 rounded-2xl" />
            <p className="mb-4 inline-flex rounded-full bg-[#f0f4fe] px-4 py-1.5 text-[11px] font-semibold uppercase tracking-[0.16em] text-[#145aff]">
              {eyebrow}
            </p>
            <h1 className="text-5xl font-semibold leading-[0.95] tracking-[-0.04em] sm:text-6xl">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-5 max-w-lg text-lg leading-7 text-[#696a72]">
                {subtitle}
              </p>
            )}
          </div>

          {/* Feature pills */}
          <div className="flex flex-wrap gap-3">
            {features.map((item, index) => (
              <motion.div
                key={item}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.12 + index * 0.05 }}
                className="rounded-xl border border-[#e2e4e9] bg-white px-4 py-2.5 text-sm font-medium text-[#020520]"
              >
                {item}
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Right: login form */}
        <motion.section
          initial={{ opacity: 0, scale: 0.98 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.4, delay: 0.06 }}
          className="rounded-2xl border border-[#e2e4e9] bg-white p-8"
        >
          {children}
        </motion.section>
      </div>
    </main>
  );
}
