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
import type { PaybackPoint, PaybackSeries } from "./PaybackChart";
import { RichText } from "./RichText";
import { VerdictHeader } from "./VerdictHeader";

const ForecastChart = lazy(() => import("./ForecastChart"));
const PaybackChart = lazy(() => import("./PaybackChart"));

/** Tones of the advisor blocks (docs/API_ADVISOR.md). */
export type BlockTone = "info" | "success" | "warn" | "danger" | "muted";

export interface TimelineStep {
  when: string;
  action: string;
  amount?: string | null;
  tone?: BlockTone;
}

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
  | { id: string; type: "approval"; plan_id: string; summary: string; approve_label: string; alt_label?: string }
  | { id: string; type: "plan_timeline"; title?: string; steps: TimelineStep[] }
  | {
      id: string;
      type: "payback_chart";
      title?: string;
      points: PaybackPoint[];
      break_even_index?: number | null;
      break_even_label?: string;
      series?: PaybackSeries[] | null;
    }
  | {
      id: string;
      type: "scenario_table";
      title?: string;
      columns: string[];
      rows: { label: string; values: string[] }[];
      highlight?: number | null;
    }
  | {
      id: string;
      type: "debt_list";
      title?: string;
      items: { counterparty: string; amount: string; due?: string | null; note?: string | null; tone?: BlockTone }[];
      total?: string | null;
    }
  | {
      id: string;
      type: "metric_grid";
      title?: string;
      items: { label: string; value: string; note?: string | null; tone?: BlockTone }[];
    };

const TONE_TEXT: Record<BlockTone, string> = {
  info: "text-primary",
  success: "text-success",
  warn: "text-warning",
  danger: "text-danger",
  muted: "text-text-3",
};

const TONE_DOT: Record<BlockTone, string> = {
  info: "bg-primary",
  success: "bg-success",
  warn: "bg-warning",
  danger: "bg-danger",
  muted: "bg-text-4",
};

const toneText = (t: BlockTone | undefined, fallback = ""): string => (t ? (TONE_TEXT[t] ?? fallback) : fallback);

function BlockTitle({ title }: { title?: string }) {
  return title ? <span className="pb-2 text-14 font-bold">{title}</span> : null;
}

/** Vertical dated timeline: when · action · amount (advisor plans and `plan_timeline`). */
export function PlanTimeline({ steps, title }: { steps: TimelineStep[]; title?: string }) {
  return (
    <div className="flex flex-col">
      <BlockTitle title={title} />
      <ol className="m-0 flex list-none flex-col p-0">
        {steps.map((s, i) => (
          <li key={i} className="relative flex gap-3 pb-[14px] last:pb-0">
            {i < steps.length - 1 && (
              <span className="absolute bottom-0 left-[6px] top-[18px] w-[2px] bg-border" aria-hidden="true" />
            )}
            <span
              className={cn("mt-[5px] h-[14px] w-[14px] shrink-0 rounded-[7px]", TONE_DOT[s.tone ?? "info"] ?? "bg-primary")}
              aria-hidden="true"
            />
            <div className="flex min-w-0 flex-1 flex-wrap items-baseline justify-between gap-x-3 gap-y-[2px]">
              <div className="flex min-w-0 flex-col gap-[2px]">
                <span className={cn("text-13 font-bold", toneText(s.tone, "text-primary"))}>{s.when}</span>
                <span className="text-15 leading-[1.45]">
                  <RichText text={s.action} />
                </span>
              </div>
              {s.amount && <strong className="shrink-0 whitespace-nowrap text-15">{s.amount}</strong>}
            </div>
          </li>
        ))}
      </ol>
    </div>
  );
}

function ScenarioTable({ block }: { block: Extract<UiBlock, { type: "scenario_table" }> }) {
  const hl = block.highlight;
  return (
    <div className="flex flex-col">
      <BlockTitle title={block.title} />
      <div className="overflow-x-auto rounded-inner border border-border-subtle">
        <table className="w-full border-collapse text-14">
          <thead>
            <tr className="bg-surface-muted">
              <th className="px-3 py-[10px] text-left font-semibold text-text-3" />
              {block.columns.map((c, i) => (
                <th
                  key={i}
                  scope="col"
                  className={cn(
                    "whitespace-nowrap px-3 py-[10px] text-right font-semibold text-text-3",
                    i === hl && "bg-primary-soft font-bold text-primary",
                  )}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {block.rows.map((r, ri) => (
              <tr key={ri} className="border-t border-border-subtle">
                <th scope="row" className="min-w-[120px] px-3 py-[10px] text-left font-medium text-text-2">
                  {r.label}
                </th>
                {r.values.map((v, i) => (
                  <td
                    key={i}
                    className={cn("whitespace-nowrap px-3 py-[10px] text-right font-semibold", i === hl && "bg-primary-soft text-ink")}
                  >
                    {v}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function DebtList({ block }: { block: Extract<UiBlock, { type: "debt_list" }> }) {
  return (
    <div className="flex flex-col text-15">
      <BlockTitle title={block.title} />
      {block.items.map((d, i) => (
        <div key={i} className="flex items-start justify-between gap-3 border-b border-border-subtle py-[10px]">
          <div className="flex min-w-0 flex-col gap-[2px]">
            <span className="font-semibold">{d.counterparty}</span>
            {d.note && <span className="text-13 text-text-4">{d.note}</span>}
          </div>
          <div className="flex shrink-0 flex-col items-end gap-[2px]">
            <strong className="whitespace-nowrap">{d.amount}</strong>
            {d.due && <span className={cn("text-13 font-semibold", toneText(d.tone, "text-text-3"))}>{d.due}</span>}
          </div>
        </div>
      ))}
      {block.total && (
        <div className="flex justify-between py-3">
          <span className="font-bold">Jami</span>
          <strong className="text-[18px]">{block.total}</strong>
        </div>
      )}
    </div>
  );
}

function MetricGrid({ block }: { block: Extract<UiBlock, { type: "metric_grid" }> }) {
  const n = block.items.length;
  return (
    <div className="flex flex-col">
      <BlockTitle title={block.title} />
      <div className={cn("grid grid-cols-2 gap-3", n === 3 && "lg:grid-cols-3", n >= 4 && "lg:grid-cols-4")}>
        {block.items.map((m, i) => (
          <div key={i} className="flex min-w-0 flex-col gap-1 rounded-inner bg-bg p-[14px]">
            <span className="text-13 font-medium text-text-3">{m.label}</span>
            <span className={cn("font-display text-22 font-bold", m.tone !== "muted" && toneText(m.tone))}>{m.value}</span>
            {m.note && <span className="text-13 text-text-4">{m.note}</span>}
          </div>
        ))}
      </div>
    </div>
  );
}

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
    case "plan_timeline":
      return <PlanTimeline steps={block.steps ?? []} title={block.title} />;
    case "payback_chart":
      return (
        <div className="flex flex-col">
          <BlockTitle title={block.title} />
          <Suspense fallback={<div className="h-[220px]" />}>
            <PaybackChart
              points={block.points ?? []}
              breakEvenIndex={block.break_even_index}
              breakEvenLabel={block.break_even_label}
              series={block.series}
            />
          </Suspense>
        </div>
      );
    case "scenario_table":
      return <ScenarioTable block={block} />;
    case "debt_list":
      return <DebtList block={block} />;
    case "metric_grid":
      return <MetricGrid block={block} />;
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
        <UiBlockView key={b.id} block={b} handlers={handlers} />
      ))}
    </div>
  );
}
