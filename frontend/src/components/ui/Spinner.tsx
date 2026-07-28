type SpinnerProps = {
  label?: string;
};

export function Spinner({ label = 'Loading' }: SpinnerProps) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-[#696a72]">
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-[#e2e4e9] border-t-[#145aff]"
        style={{ borderTopColor: '#145aff' }}
      />
      <span>{label}</span>
    </span>
  );
}
