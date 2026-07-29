import React from "react";

type FieldProps = {
  label: string;
  children: React.ReactNode;
};

export function Field({ label, children }: FieldProps) {
  return (
    <label className="block space-y-2">
      <span className="block text-[13px] font-semibold text-[#18261d]">
        {label}
      </span>
      {children}
    </label>
  );
}
