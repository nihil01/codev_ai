/* ─── SOUL.md Design Tokens ─────────────────────────────────────── */

// Card styles
export const cardClass =
  'bg-white rounded-lg p-4 transition duration-200';

export const cardLargeClass =
  'bg-[#fcfcfc] rounded-[40px] p-12 transition duration-200';

// Input styles
export const inputClass =
  'w-full border border-[#e2e4e9] rounded-xl px-4 py-3 text-sm text-[#020520] bg-white outline-none transition focus:border-[#145aff] focus:ring-3 focus:ring-[rgba(20,90,255,0.08)] disabled:bg-[#f5f5f5] disabled:text-[#696a72]';

export const labelClass = 'block mb-2 text-[13px] font-semibold text-[#696a72] tracking-[0.01em]';

// Button styles
export const primaryButtonClass =
  'inline-flex items-center justify-center gap-2 bg-gradient-to-b from-[#3b82f6] to-[#145aff] text-white border-none rounded-xl px-5 py-3 text-sm font-semibold cursor-pointer transition duration-200 hover:opacity-92 hover:-translate-y-px active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50';

export const secondaryButtonClass =
  'inline-flex items-center justify-center gap-2 bg-white border border-[#e2e4e9] text-[#020520] rounded-xl px-5 py-3 text-sm font-semibold cursor-pointer transition duration-200 hover:border-[#145aff] hover:text-[#145aff] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50';

export const dangerButtonClass =
  'inline-flex items-center justify-center gap-2 bg-[#fff5f5] border border-[#fecaca] text-[#b91c1c] rounded-xl px-5 py-3 text-sm font-semibold cursor-pointer transition duration-200 hover:bg-[#fef2f2] hover:border-[#f87171] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50';

export const ghostButtonClass =
  'inline-flex items-center justify-center gap-2 bg-transparent border border-transparent text-[#696a72] rounded-xl px-5 py-3 text-sm font-semibold cursor-pointer transition duration-200 hover:bg-[#f0f4fe] hover:text-[#145aff] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50';

// Outlined button (SOUL.md primary outlined)
export const outlinedButtonClass =
  'inline-flex items-center justify-center gap-2 bg-transparent border border-[#0f1f3d] text-[#0f1f3d] rounded-xl px-5 py-3 text-sm font-semibold cursor-pointer transition duration-200 hover:bg-[rgba(15,31,61,0.04)] active:translate-y-0 disabled:cursor-not-allowed disabled:opacity-50';

// Surface colors
export const surfacePrimary = 'bg-[#fcfcfc]';
export const surfaceSecondary = 'bg-[#f0f4fe]';
export const surfaceCard = 'bg-white';

// Text colors
export const textPrimary = 'text-[#020520]';
export const textSecondary = 'text-[#696a72]';
export const textAccent = 'text-[#145aff]';

// Border
export const borderSubtle = 'border border-[#e2e4e9]';
