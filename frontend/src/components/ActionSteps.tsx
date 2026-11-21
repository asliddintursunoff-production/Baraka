import type { Severity } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface StepItem {
  severity?: Severity;
  label?: string;
  text: string;
}

const TONE: Record<Severity, { bg: string; dot: string; label: string }> = {
  success: { bg: "bg-bg", dot: "bg-success", label: "text-success" },
  warning: { bg: "bg-warning-bg", dot: "bg-warning", label: "text-warning" },
  danger: { bg: "bg-danger-bg", dot: "bg-danger", label: "text-danger" },
};

/** Numbered 1-2-3 steps, coloured by severity, date label + one sentence (DESIGN.md). */
export function ActionSteps({ items, compact = false }: { items: StepItem[]; compact?: boolean }) {
  return (
    <ol className="m-0 flex list-none flex-col gap-[10px] p-0">
      {items.map((s, i) => {
        const tone = TONE[s.severity ?? "success"] ?? TONE.success; // unknown severity: neutral, never crash
        return (
          <li
            key={i}
            className={cn("flex gap-3 rounded-inner p-[14px]", s.severity ? tone.bg : "bg-bg", compact && "p-3")}
          >
            <span
              className={cn(
                "flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-[13px] text-13 font-bold text-white",
                s.severity ? tone.dot : "bg-primary",
              )}
            >
              {i + 1}
            </span>
            <div className="flex flex-col gap-[3px]">
              {s.label && <span className={cn("text-13 font-bold", tone.label)}>{s.label}</span>}
              <span className="text-15 leading-[1.45]">{s.text}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
