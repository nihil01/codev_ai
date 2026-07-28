type SpinnerProps = {
  label?: string;
};

export function Spinner({ label = 'Loading' }: SpinnerProps) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-[#222222]">
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-[#efeeeb] border-t-[#0f3e17]"
        style={{ borderTopColor: '#0f3e17' }}
      />
      <span>{label}</span>
    </span>
  );
}
