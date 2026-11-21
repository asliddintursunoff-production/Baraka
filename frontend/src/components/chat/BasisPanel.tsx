import type { ReactNode } from "react";

import type { Basis, BasisItem } from "@/lib/chatTypes";
import { cn } from "@/lib/utils";

import { RulesIcon, SegmentIcon, SheetsIcon } from "./icons";

const ICON: Record<BasisItem["icon"], ReactNode> = {
  sheets: <SheetsIcon />,
  rules: <RulesIcon />,
  segment: <SegmentIcon />,
};

const CONFIDENCE = {
  high: { text: "text-success", dot: "bg-success" },
  medium: { text: "text-warning", dot: "bg-warning" },
  low: { text: "text-danger", dot: "bg-danger" },
} as const;

/**
 * Right "Nimaga asoslandim" panel. It sits beside the chat when there is room (≥ 1080 px:
 * 240 sidebar + 560 chat + 280 panel) and wraps under it otherwise.
 */
export function BasisPanel({ basis }: { basis: Basis | null }) {
  const conf = basis?.confidence ?? null;
  const tone = conf ? (CONFIDENCE[conf.level] ?? CONFIDENCE.medium) : null;
  return (
    <aside
      aria-label="Javob manbalari"
      className="box-border flex min-w-0 flex-[1_1_280px] flex-col gap-[18px] border-t border-border bg-surface px-5 py-6 min-[1080px]:border-l min-[1080px]:border-t-0"
    >
      <h2 className="m-0 font-display text-17 font-bold">Nimaga asoslandim</h2>
      {(basis?.items ?? []).map((it, i) => (
        <div key={i} className="flex items-start gap-3">
          {ICON[it.icon] ?? <RulesIcon />}
          <span className="min-w-0 text-14 leading-normal [overflow-wrap:anywhere]">
            {it.title}
            {it.note && (
              <>
                <br />
                <span className="text-text-4">{it.note}</span>
              </>
            )}
          </span>
        </div>
      ))}
      {conf && tone && (
        <div className="flex flex-col gap-[6px] border-t border-border-subtle pt-4">
          <span className="text-13 font-semibold text-text-4">Javobga ishonch</span>
          <span className={cn("inline-flex items-center gap-2 text-16 font-bold", tone.text)}>
            <span className={cn("h-[10px] w-[10px] rounded-[5px]", tone.dot)} aria-hidden="true" />
            {conf.label}
          </span>
          {conf.note && <span className="text-13 leading-normal text-text-3">{conf.note}</span>}
        </div>
      )}
    </aside>
  );
}
