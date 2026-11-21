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

/** "1. 10-dekabr …" from the backend/LLM would show the index twice: drop the text's own number. */
export function stripLeadingIndex(text: string): string {
  return text.replace(/^\s*\d{1,2}[.)]\s+/, "");
}

/**
 * The round step number. It is its own element followed by a real space, and screen readers and
 * copy/paste get "1. " — so "1" + "10-dekabr" can never read or paste as "110-dekabr".
 */
export function StepBadge({ n, className }: { n: number; className?: string }) {
  return (
    <>
      <span
        className={cn(
          "flex h-[26px] w-[26px] shrink-0 select-none items-center justify-center rounded-[13px] text-13 font-bold tabular-nums",
          className,
        )}
      >
        {n}
        <span className="sr-only">.</span>
      </span>{" "}
    </>
  );
}

/** Numbered 1-2-3 steps, coloured by severity, date label + one sentence (DESIGN.md). */
export function ActionSteps({ items, compact = false }: { items: StepItem[]; compact?: boolean }) {
  return (
    <ol className="m-0 flex list-none flex-col gap-[10px] p-0">
      {items.map((s, i) => {
        const tone = TONE[s.severity ?? "success"] ?? TONE.success; // unknown severity: neutral, never crash
        return (
          <li
            key={i}
            className={cn(
              "flex gap-3 rounded-inner p-[14px]",
              s.severity ? tone.bg : "bg-bg",
              compact && "p-3",
            )}
          >
            <StepBadge
              n={i + 1}
              className={cn("text-white", s.severity ? tone.dot : "bg-primary")}
            />
            <div className="flex min-w-0 flex-col gap-[3px]">
              {s.label && <span className={cn("text-13 font-bold", tone.label)}>{s.label}</span>}
              <span className="text-15 leading-[1.45]">{stripLeadingIndex(s.text)}</span>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
