import { motion } from 'framer-motion';

type MetricCardProps = {
  label: string;
  value: string | number;
  helper?: string;
};

export function MetricCard({ label, value, helper }: MetricCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-[24px] border border-[#e1ebe4] bg-[#ffffff] p-5  transition duration-200 "
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#18261d]">
        {label}
      </p>
      <p className="mt-3 break-words text-2xl font-semibold tracking-[-0.02em] text-[#18261d]">
        {value}
      </p>
      {helper && (
        <p className="mt-2 break-words text-[13px] leading-5 text-[#18261d]">
          {helper}
        </p>
      )}
    </motion.div>
  );
}
