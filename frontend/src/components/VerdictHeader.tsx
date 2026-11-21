import { Check, TriangleAlert, X } from "lucide-react";

import type { Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

const STYLE: Record<Verdict | "info", { color: string; Icon: typeof Check; bg: string }> = {
  yes: { color: "text-success", bg: "bg-success-bg", Icon: Check },
  risky: { color: "text-warning", bg: "bg-warning-bg", Icon: TriangleAlert },
  no: { color: "text-danger", bg: "bg-danger-bg", Icon: X },
  info: { color: "text-primary", bg: "bg-primary-soft", Icon: Check },
};

export function VerdictHeader({ status, headline, reason }: { status: Verdict | "info"; headline: string; reason?: string }) {
  const s = STYLE[status];
  return (
    <div className="flex items-start gap-3">
      <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-inner", s.bg, s.color)}>
        <s.Icon size={22} strokeWidth={2.6} aria-hidden="true" />
      </span>
      <div className="flex flex-col gap-1">
        <p className={cn("m-0 font-display text-24 font-bold leading-tight", s.color)}>{headline}</p>
        {reason && <p className="m-0 text-16 leading-normal text-text-2">{reason}</p>}
      </div>
    </div>
  );
}
