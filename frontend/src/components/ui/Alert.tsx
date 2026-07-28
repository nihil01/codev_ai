import type { ReactNode } from 'react';

type AlertType = 'error' | 'success' | 'info';

type AlertProps = {
  type: AlertType;
  children: ReactNode;
};

const alertPalette: Record<AlertType, string> = {
  error: 'border-[#fde8e8] bg-[#fef6f6] text-[#b42318]',
  success: 'border-[#d1fadf] bg-[#f0fdf4] text-[#166534]',
  info: 'border-[#d0e0ff] bg-[#f0f5ff] text-[#0040b3]',
};

export function Alert({ type, children }: AlertProps) {
  return (
    <div
      className={`rounded-lg border px-4 py-3 text-sm font-medium ${alertPalette[type]}`}
    >
      {children}
    </div>
  );
}
