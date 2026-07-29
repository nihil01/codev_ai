import type { ReactNode } from 'react';

type AlertType = 'error' | 'success' | 'info';

type AlertProps = {
  type: AlertType;
  children: ReactNode;
};

const alertPalette: Record<AlertType, string> = {
  error: 'border-[#d8e8dd] bg-[#d8e8dd] text-[#116932]',
  success: 'border-[#e4f5e9] bg-[#e4f5e9] text-[#18261d]',
  info: 'border-[#e4f5e9] bg-[#e4f5e9] text-[#116932]',
};

export function Alert({ type, children }: AlertProps) {
  return (
    <div
      className={`rounded-[24px] border px-4 py-3 text-sm font-medium ${alertPalette[type]}`}
    >
      {children}
    </div>
  );
}
