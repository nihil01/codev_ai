type InfoRowProps = {
  label: string;
  value?: string | number | null;
  mono?: boolean;
};

export function InfoRow({ label, value, mono = false }: InfoRowProps) {
  return (
    <div className="flex flex-col gap-1 rounded-lg border border-[#e2e4e9] bg-[#fcfcfc] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#696a72]">
        {label}
      </span>
      <span
        className={`${mono ? "font-mono" : "font-medium"} break-all text-[13px] text-[#020520]`}
      >
        {value || "—"}
      </span>
    </div>
  );
}
