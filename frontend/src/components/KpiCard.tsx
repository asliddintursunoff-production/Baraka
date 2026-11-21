import type { Kpi } from "@/lib/types";
import { cn } from "@/lib/utils";

const NOTE_TONE: Record<Kpi["tone"], string> = {
  muted: "text-13 text-text-4",
  success: "text-13 font-semibold text-success",
  warning: "text-13 font-semibold text-warning",
  danger: "text-13 font-semibold text-danger",
};

export function KpiCard({ kpi }: { kpi: Kpi }) {
  return (
    <div className="flex flex-col gap-2 rounded-[14px] border border-border bg-surface px-5 py-[18px]">
      <span className="text-14 font-medium text-text-3">{kpi.label}</span>
      <span className="font-display text-30 font-bold">
        {kpi.value} <span className="text-17 font-semibold text-text-3">{kpi.unit}</span>
      </span>
      <span className={cn(NOTE_TONE[kpi.tone])}>{kpi.note}</span>
    </div>
  );
}
