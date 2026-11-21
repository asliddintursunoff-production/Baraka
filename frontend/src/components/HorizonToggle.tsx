import { cn } from "@/lib/utils";

export const HORIZONS = [7, 30, 60, 90] as const;
export type Horizon = (typeof HORIZONS)[number];

export function HorizonToggle({
  value,
  onChange,
  large = false,
}: {
  value: Horizon;
  onChange: (h: Horizon) => void;
  large?: boolean;
}) {
  return (
    <div
      role="group"
      aria-label="Prognoz muddati"
      className={cn("flex gap-[2px] rounded-btn p-1", large ? "bg-[#E9ECF1]" : "bg-[#F2F4F7]")}
    >
      {HORIZONS.map((h) => (
        <button
          key={h}
          type="button"
          aria-pressed={h === value}
          onClick={() => onChange(h)}
          className={cn(
            "rounded-lg border-0 px-2 text-14",
            large ? "min-h-10 min-w-[60px]" : "min-h-9 min-w-[52px]",
            h === value
              ? "bg-surface font-bold text-ink shadow-[0_1px_2px_rgba(16,24,40,.1)]"
              : "bg-transparent font-semibold text-text-3",
          )}
        >
          {h} kun
        </button>
      ))}
    </div>
  );
}
