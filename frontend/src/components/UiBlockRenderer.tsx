/**
 * The single renderer for backend `ui_blocks` (spec §5.4): used inside the chat AnswerCard
 * and on the Live right-hand panel. The LLM never creates blocks; the backend builds them
 * from tool results.
 */
import { lazy, Suspense } from "react";

import type { SeriesPoint, Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

import { ActionSteps } from "./ActionSteps";
import { CompareBars, type CompareRow } from "./CompareBars";
import { KpiCard } from "./KpiCard";
import { RichText } from "./RichText";
import { VerdictHeader } from "./VerdictHeader";
import { BlockBoundary } from "@/components/ErrorFallbacks";

const ForecastChart = lazy(() => import("./ForecastChart"));

export type UiBlock =
  | { id: string; type: "verdict"; status: Verdict | "info"; headline: string; reason?: string }
  | { id: string; type: "compare_bars"; title: string; rows: CompareRow[] }
  | { id: string; type: "steps"; items: (string | { text: string; label?: string; severity?: "success" | "warning" | "danger" })[] }
  | { id: string; type: "kpi"; label: string; value: string; unit: string; note?: string }
  | {
      id: string;
      type: "forecast_chart";
      series: SeriesPoint[];
      days: number;
      safe_min: string;
      safe_label: string;
      lowest_index: number;
      callout_title: string;
      callout_text: string;
      aria_label: string;
    }
  | {
      id: string;
      type: "day_breakdown";
      title: string;
      rows: { label: string; value: string; tone: "plain" | "success" | "danger"; badge?: string }[];
      closing: string;
    }
  | { id: string; type: "approval"; plan_id: string; summary: string; approve_label: string; alt_label?: string };

export interface BlockHandlers {
  onApprove?: (planId: string) => void;
  onAlternative?: () => void;
  approved?: Set<string>;
  dark?: boolean;
}

export function UiBlockView({ block, handlers = {} }: { block: UiBlock; handlers?: BlockHandlers }) {
  const dark = handlers.dark ?? false;
  switch (block.type) {
    case "verdict":
      return <VerdictHeader status={block.status} headline={block.headline} reason={block.reason} />;
    case "compare_bars":
      return <CompareBars title={block.title} rows={block.rows} dark={dark} />;
    case "steps":
      return (
        <ChatSteps
          items={block.items.map((it) => (typeof it === "string" ? { text: it } : it))}
          dark={dark}
        />
      );
    case "kpi":
      return (
        <KpiCard
          kpi={{ id: block.id, label: block.label, value: block.value, unit: block.unit, note: block.note ?? "", tone: "muted" }}
        />
      );
    case "forecast_chart":
      return (
        <Suspense fallback={<div className="h-48" />}>
          <ForecastChart
            series={block.series}
            days={block.days}
            safeMin={block.safe_min}
            safeLabel={block.safe_label}
            lowestIndex={block.lowest_index}
            calloutTitle={block.callout_title}
            calloutText={block.callout_text}
            ariaLabel={block.aria_label}
          />
        </Suspense>
      );
    case "day_breakdown":
      return (
        <div className="flex flex-col text-15">
          <span className="pb-2 text-14 font-bold">{block.title}</span>
          {block.rows.map((r, i) => (
            <div key={i} className="flex justify-between border-b border-border-subtle py-[10px]">
              <span className={r.tone === "plain" ? "text-text-3" : ""}>
                {r.label}{" "}
                {r.badge && <span className="text-12 font-bold text-danger">{r.badge}</span>}
              </span>
              <strong className={r.tone === "success" ? "text-success" : r.tone === "danger" ? "text-danger" : ""}>
                {r.value}
              </strong>
            </div>
          ))}
          <div className="flex justify-between py-3">
            <span className="font-bold">Kun oxirida qoladi</span>
            <strong className="text-[18px]">{block.closing}</strong>
          </div>
        </div>
      );
    case "approval": {
      const done = handlers.approved?.has(block.plan_id);
      return (
        <div className="flex flex-wrap gap-[10px] pt-[6px]">
          <button
            type="button"
            disabled={done}
            onClick={() => handlers.onApprove?.(block.plan_id)}
            className="min-h-12 rounded-btn-lg border-0 bg-primary px-[22px] text-16 font-semibold text-white hover:bg-primary-hover disabled:bg-success"
          >
            {done ? "Tasdiqlandi" : block.approve_label}
          </button>
          {block.alt_label && !done && (
            <button
              type="button"
              onClick={() => handlers.onAlternative?.()}
              className="min-h-12 rounded-btn-lg border border-border-input bg-surface px-5 text-16 font-semibold text-text-2"
            >
              {block.alt_label}
            </button>
          )}
        </div>
      );
    }
    default:
      return null;
  }
}

export function ChatSteps({
  items,
  dark = false,
}: {
  items: { text: string; label?: string; severity?: "success" | "warning" | "danger" }[];
  dark?: boolean;
}) {
  if (items.some((i) => i.label)) return <ActionSteps items={items} />;
  return (
    <ol className="m-0 flex list-none flex-col gap-[10px] p-0">
      {items.map((it, i) => (
        <li key={i} className={cn("flex items-start gap-3 text-16 leading-normal", dark && "text-white")}>
          <span
            className={cn(
              "flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-[13px] text-13 font-bold",
              dark ? "bg-white text-ink" : "bg-ink text-white",
            )}
          >
            {i + 1}
          </span>
          <span>
            <RichText text={it.text} />
          </span>
        </li>
      ))}
    </ol>
  );
}

export function UiBlockRenderer({ blocks, handlers }: { blocks: UiBlock[]; handlers?: BlockHandlers }) {
  return (
    <div className="flex flex-col gap-4">
      {blocks.map((b) => (
        <BlockBoundary key={b.id}>
          <UiBlockView block={b} handlers={handlers} />
        </BlockBoundary>
      ))}
    </div>
  );
}
