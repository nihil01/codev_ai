type SpinnerProps = {
  label?: string;
};

export function Spinner({ label = 'Loading' }: SpinnerProps) {
  return (
    <span className="inline-flex items-center gap-2 text-[13px] text-[#18261d]">
      <span
        className="h-4 w-4 animate-spin rounded-full border-2 border-[#e1ebe4] border-t-[#18261d]"
        style={{ borderTopColor: '#18261d' }}
      />
      <span>{label}</span>
    </span>
  );
}
