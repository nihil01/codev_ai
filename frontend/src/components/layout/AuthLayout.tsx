import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Leaf, MessagesSquare } from 'lucide-react';
import codevLogo from '../../assets/codev-logo.png';
import { useI18n } from '../../i18n';

type AuthLayoutProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  const { t } = useI18n();
  const features = [
    { label: t('auth.featuresAi'), icon: MessagesSquare },
    { label: t('auth.featuresDirect'), icon: BookOpen },
    { label: t('auth.featuresCrm'), icon: Leaf },
  ];

  return (
    <main className="min-h-screen bg-[#f3faf5] px-4 py-4 text-[#18261d] sm:px-6 sm:py-6 lg:px-10 lg:py-10">
      <div className="mx-auto grid min-h-[calc(100vh-80px)] max-w-[1200px] gap-5 lg:grid-cols-[1.1fr_0.9fr]">
        {/* Left panel - branding */}
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="flex min-h-[460px] flex-col justify-between rounded-[32px] bg-gradient-to-br from-[#e4f5e9] via-[#d4edda] to-[#c8e6cf] p-8 sm:p-10 lg:p-14"
        >
          <div>
            <div className="flex items-center gap-4">
              <img src={codevLogo} alt="Codev" className="h-auto w-[160px] sm:w-[180px]" />
              <span className="hidden h-10 w-px bg-[#b8d4bf] sm:block" aria-hidden="true" />
              <p className="hidden max-w-[140px] text-sm font-medium leading-tight text-[#5a7a62] sm:block">
                Kurs idarəetmə platforması
              </p>
            </div>
          </div>

          <div className="my-12 max-w-[580px]">
            <h1 className="text-[38px] font-bold leading-[1.1] tracking-[-0.04em] text-[#18261d] sm:text-[52px] lg:text-[58px]">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-5 max-w-xl text-[15px] font-light leading-[1.7] text-[#3d5a44]">
                {subtitle}
              </p>
            )}
          </div>

          <div className="grid gap-3 sm:grid-cols-3">
            {features.map(({ label, icon: Icon }, index) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 + index * 0.08 }}
                className="flex items-center gap-3 rounded-2xl bg-white/80 backdrop-blur-sm px-4 py-3.5 text-sm font-medium text-[#18261d] shadow-sm"
              >
                <div className="flex h-8 w-8 items-center justify-center rounded-xl bg-[#e4f5e9] text-[#15803d]">
                  <Icon size={16} strokeWidth={1.8} />
                </div>
                <span>{label}</span>
              </motion.div>
            ))}
          </div>
        </motion.section>

        {/* Right panel - login form */}
        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.08 }}
          className="flex items-center justify-center rounded-[32px] bg-[#d8e8dd] p-3 sm:p-5 lg:p-6"
        >
          <div className="w-full rounded-[28px] bg-white p-7 shadow-sm sm:p-10 lg:p-12">
            {children}
          </div>
        </motion.section>
      </div>
    </main>
  );
}
