import type { ReactNode } from 'react';

type AlertType = 'error' | 'success' | 'info';

type AlertProps = {
  type: AlertType;
  children: ReactNode;
};

const alertPalette: Record<AlertType, string> = {
  error: 'border-[#b6ced5] bg-[#b6ced5] text-[#0c2f10]',
  success: 'border-[#cfe7d3] bg-[#e1f4df] text-[#0f3e17]',
  info: 'border-[#cfe7d3] bg-[#e1f4df] text-[#0c2f10]',
};

export function Alert({ type, children }: AlertProps) {
  return (
    <div
      className={`rounded-[14px] border px-4 py-3 text-sm font-medium ${alertPalette[type]}`}
    >
      {children}
    </div>
  );
}
