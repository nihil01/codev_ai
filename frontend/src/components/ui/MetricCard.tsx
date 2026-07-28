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
      className="rounded-[8px] border border-[#e2e4e9] bg-[#fcfcfc] p-5 shadow-[0_1px_3px_rgba(0,0,0,0.04),0_1px_2px_rgba(0,0,0,0.02)] transition duration-200 hover:shadow-[0_4px_12px_rgba(0,0,0,0.06)]"
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[#696a72]">
        {label}
      </p>
      <p className="mt-3 break-words text-2xl font-semibold tracking-[-0.02em] text-[#020520]">
        {value}
      </p>
      {helper && (
        <p className="mt-2 break-words text-[13px] leading-5 text-[#696a72]">
          {helper}
        </p>
      )}
    </motion.div>
  );
}
