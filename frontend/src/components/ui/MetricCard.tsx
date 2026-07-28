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
      className="rounded-[14px] border border-[#efeeeb] bg-[#fffefc] p-5  transition duration-200 "
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#222222]">
        {label}
      </p>
      <p className="mt-3 break-words text-2xl font-semibold tracking-[-0.02em] text-[#0f3e17]">
        {value}
      </p>
      {helper && (
        <p className="mt-2 break-words text-[13px] leading-5 text-[#222222]">
          {helper}
        </p>
      )}
    </motion.div>
  );
}
