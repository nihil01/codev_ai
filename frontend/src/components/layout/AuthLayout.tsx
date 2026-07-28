import type { ReactNode } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, Leaf, MessagesSquare } from 'lucide-react';
import { useI18n } from '../../i18n';

type AuthLayoutProps = {
  eyebrow: string;
  title: string;
  subtitle?: string;
  children: ReactNode;
};

export function AuthLayout({ eyebrow, title, subtitle, children }: AuthLayoutProps) {
  const { t } = useI18n();
  const features = [
    { label: t('auth.featuresAi'), icon: MessagesSquare },
    { label: t('auth.featuresDirect'), icon: BookOpen },
    { label: t('auth.featuresCrm'), icon: Leaf },
  ];

  return (
    <main className="min-h-screen bg-[#fffefc] px-4 py-4 text-[#222222] sm:px-7 sm:py-7 lg:px-[42px] lg:py-[42px]">
      <div className="mx-auto grid min-h-[calc(100vh-84px)] max-w-[1200px] gap-[14px] lg:grid-cols-[1.05fr_0.95fr]">
        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45 }}
          className="flex min-h-[440px] flex-col justify-between rounded-[14px] bg-[#e1f4df] p-7 sm:p-[42px] lg:p-14"
        >
          <div className="flex items-center gap-[14px]">
            <span className="grid h-12 w-12 place-items-center rounded-[14px] bg-[#fffefc] text-[#0f3e17]">
              <Leaf size={24} strokeWidth={1.6} />
            </span>
            <div>
              <p className="eyebrow-label">Codev</p>
              <p className="mt-1 text-sm font-light text-[#222222]">Kurs idarəetmə platforması</p>
            </div>
          </div>

          <div className="my-14 max-w-[620px]">
            <p className="eyebrow-label mb-[18px]">{eyebrow}</p>
            <h1 className="text-[42px] leading-[1.08] tracking-[-0.03em] text-[#0f3e17] sm:text-[56px] lg:text-[64px]">
              {title}
            </h1>
            {subtitle && (
              <p className="mt-[21px] max-w-xl text-[15px] font-light leading-7 text-[#222222]">
                {subtitle}
              </p>
            )}
          </div>

          <div className="grid gap-[9px] sm:grid-cols-3">
            {features.map(({ label, icon: Icon }, index) => (
              <motion.div
                key={label}
                initial={{ opacity: 0, y: 8 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.14 + index * 0.06 }}
                className="flex items-center gap-[11px] rounded-[14px] bg-[#fffefc] px-[14px] py-[14px] text-sm font-normal text-[#0f3e17]"
              >
                <Icon size={17} strokeWidth={1.6} />
                <span>{label}</span>
              </motion.div>
            ))}
          </div>
        </motion.section>

        <motion.section
          initial={{ opacity: 0, y: 14 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.45, delay: 0.06 }}
          className="flex items-center rounded-[14px] bg-[#b6ced5] p-[14px] sm:p-7 lg:p-[42px]"
        >
          <div className="w-full rounded-[14px] bg-[#fffefc] p-7 sm:p-[42px]">
            <div className="mb-7 flex items-center justify-between border-b border-[#efeeeb] pb-[21px]">
              <div>
                <p className="eyebrow-label">Təhlükəsiz giriş</p>
                <p className="mt-2 text-sm font-light text-[#222222]">Şəxsi iş məkanınız</p>
              </div>
              <span className="rounded-full bg-[#e1f4df] px-[14px] py-[9px] text-xs text-[#0f3e17]">AZ</span>
            </div>
            {children}
          </div>
        </motion.section>
      </div>
    </main>
  );
}
