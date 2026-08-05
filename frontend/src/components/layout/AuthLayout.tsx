import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import codevLogo from '../../assets/codev-logo.png';
import { useI18n } from '../../i18n';

type AuthLayoutProps = {
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export function AuthLayout({ title, subtitle, children }: AuthLayoutProps) {
  const { t } = useI18n();

  return (
    <main className="min-h-screen bg-white text-[#18261d]">
      <div className="flex min-h-screen">
        {/* Left panel - branding */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.6 }}
          className="relative hidden w-[52%] overflow-hidden bg-[#15803d] lg:flex lg:flex-col lg:justify-between"
        >
          {/* Background pattern */}
          <div className="absolute inset-0 opacity-[0.07]">
            <div className="absolute -left-20 -top-20 h-[500px] w-[500px] rounded-full border border-white/40" />
            <div className="absolute -bottom-32 -right-32 h-[600px] w-[600px] rounded-full border border-white/40" />
            <div className="absolute left-1/3 top-1/4 h-[300px] w-[300px] rounded-full border border-white/30" />
          </div>

          {/* Content */}
          <div className="relative z-10 p-12">
            <img src={codevLogo} alt="Codev" className="h-10 w-auto brightness-0 invert" />
          </div>

          <div className="relative z-10 px-12 pb-16">
            <h1 className="text-[52px] font-bold leading-[1.1] tracking-[-0.03em] text-white lg:text-[64px]">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-5 max-w-md text-[16px] font-light leading-[1.7] text-white/80">
                {subtitle}
              </p>
            )}
          </div>

          <div className="relative z-10 px-12 pb-12">
            <div className="flex items-center gap-6 text-sm text-white/60">
              <span>© 2026 Codev</span>
              <span className="h-4 w-px bg-white/20" />
              <span>Bütün hüquqlar qorunur</span>
            </div>
          </div>
        </motion.div>

        {/* Right panel - login form */}
        <motion.div
          initial={{ opacity: 0, x: 20 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="flex flex-1 flex-col items-center justify-center px-6 py-12 sm:px-12 lg:px-16"
        >
          <div className="w-full max-w-[400px]">
            {/* Mobile logo */}
            <div className="mb-10 lg:hidden">
              <img src={codevLogo} alt="Codev" className="h-9 w-auto" />
            </div>

            {children}

            <p className="mt-8 text-center text-xs text-[#9ca8a2]">
              © 2026 Codev. Bütün hüquqlar qorunur.
            </p>
          </div>
        </motion.div>
      </div>
    </main>
  );
}
