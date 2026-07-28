type InfoRowProps = {
  label: string;
  value?: string | number | null;
  mono?: boolean;
};

export function InfoRow({ label, value, mono = false }: InfoRowProps) {
  return (
    <div className="flex flex-col gap-1 rounded-[14px] border border-[#efeeeb] bg-[#fffefc] px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
      <span className="text-[11px] font-semibold uppercase tracking-[0.12em] text-[#222222]">
        {label}
      </span>
      <span
        className={`${mono ? "font-mono" : "font-medium"} break-all text-[13px] text-[#0f3e17]`}
      >
        {value || "—"}
      </span>
    </div>
  );
}
