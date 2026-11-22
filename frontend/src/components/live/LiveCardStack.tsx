/** Right-hand Live panel (design/pages/Live.html): "Hozirgi kassa", then the cards from each
 * tool result as they arrive (newest at the bottom), and the voice-approvable plan card. */
import { Check, LoaderCircle } from "lucide-react";

import { MicIcon } from "@/components/chat/icons";
import { RichText } from "@/components/RichText";
import { UiBlockView, type BlockHandlers, type UiBlock } from "@/components/UiBlockRenderer";
import { cn } from "@/lib/utils";

export type LiveCard =
  | { kind: "blocks"; key: string; group: number; blocks: UiBlock[]; segments?: { cue: string; text: string }[]; full?: boolean }
  | { kind: "plan"; key: string; group: number; planId: number; summary: string; items: string[] };

export interface PlanState {
  status: "pending" | "done" | "error";
  summary?: string;
}

const ENTER =
  "motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-3 duration-[450ms] ease-out fill-mode-both";
/** The card the AI is talking about right now (Live.html: 3 px primary ring). */
const HIGHLIGHT = "shadow-[0_0_0_3px_#1D4ED8]";

/**
 * Blocks are rendered with `dark` handlers. Types that have a dark variant (compare bars,
 * plain steps) sit on the dark surface; the rest keep their light card so they stay legible.
 */
function blockSurface(b: UiBlock): string {
  switch (b.type) {
    case "compare_bars":
      return "rounded-inner"; // CompareBars dark draws its own live-surface panel
    case "kpi":
      return "rounded-[14px] text-ink"; // KpiCard is a white card itself
    case "steps":
      if (!b.items.some((it) => typeof it !== "string" && it.label)) {
        return "rounded-card border border-live-border bg-live-surface p-5";
      }
      return "rounded-card bg-surface p-5 text-ink";
    default:
      return "rounded-card bg-surface p-5 text-ink";
  }
}

function PlanCard({
  card,
  state,
  onApprove,
}: {
  card: Extract<LiveCard, { kind: "plan" }>;
  state: PlanState | undefined;
  onApprove: (planId: number) => void;
}) {
  const approved = state?.status === "done";
  const approving = state?.status === "pending";
  return (
    <article className={cn("flex flex-col gap-3 rounded-card bg-surface p-5 text-ink", ENTER)}>
      <span className="text-16 font-bold">Taklif: reja</span>
      <ol className="m-0 list-decimal pl-[22px] text-15 leading-[1.7] text-text-2 [&_strong]:text-ink">
        {card.items.map((text, i) => (
          <li key={i}>
            <RichText text={text} />
          </li>
        ))}
      </ol>
      <div className="flex flex-wrap items-center gap-3 rounded-btn bg-bg p-3">
        {approved ? (
          <Check size={20} strokeWidth={2.4} className="shrink-0 text-success" aria-hidden="true" />
        ) : (
          <MicIcon size={20} color="#1D4ED8" />
        )}
        <span className="flex-[1_1_160px] text-14 text-text-2">
          {approved ? (
            <span className="font-semibold text-success">{state?.summary || card.summary}</span>
          ) : state?.status === "error" ? (
            <span className="font-semibold text-danger">Tasdiqlab bo'lmadi. Qaytadan urinib ko'ring.</span>
          ) : (
            <>
              Tasdiqlash uchun <strong>"Ha"</strong> deng yoki tugmani bosing
            </>
          )}
        </span>
        <button
          type="button"
          onClick={() => {
            if (!approved && !approving) onApprove(card.planId);
          }}
          aria-disabled={approved || approving || undefined}
          aria-busy={approving || undefined}
          className={cn(
            "inline-flex min-h-tap items-center gap-2 rounded-btn border-0 px-[18px] text-15 font-semibold text-white",
            approved ? "cursor-default bg-success" : "bg-primary hover:bg-primary-hover",
            approving && "cursor-wait opacity-80",
          )}
        >
          {approved && <Check size={18} strokeWidth={2.6} aria-hidden="true" />}
          {approving && <LoaderCircle size={18} className="motion-safe:animate-spin" aria-hidden="true" />}
          {approved ? "Tasdiqlandi" : "Tasdiqlash"}
        </button>
      </div>
    </article>
  );
}

export function LiveCardStack({
  cash,
  cards,
  plans,
  onApprove,
  aiText = "",
}: {
  cash: { label: string; display: string } | null;
  cards: LiveCard[];
  plans: Record<number, PlanState>;
  onApprove: (planId: number) => void;
  /** What the AI has said so far in this turn: picks the report section being spoken. */
  aiText?: string;
}) {
  const newestGroup = cards.reduce((g, c) => (c.kind === "blocks" ? Math.max(g, c.group) : g), -1);
  const handlers: BlockHandlers = {
    dark: true,
    onApprove: (id) => onApprove(Number(id)),
    approved: new Set(
      Object.entries(plans)
        .filter(([, s]) => s.status === "done")
        .map(([id]) => id),
    ),
  };

  return (
    <section
      aria-label="AI ekranda ko'rsatayotganlari"
      aria-live="polite"
      className="flex min-w-0 flex-[1_1_420px] flex-col gap-4"
    >
      <div className="flex flex-wrap items-center justify-between gap-[10px]">
        <h2 className="m-0 text-14 font-bold uppercase tracking-[0.06em] text-[#98A2B3]">Gapirayotganda ko'rsatyapti</h2>
        <span className="text-13 text-[#98A2B3]">Keyin chatda saqlanadi</span>
      </div>

      {cash && (
        <article className="flex items-center justify-between gap-3 rounded-card border border-live-border bg-live-surface px-5 py-4">
          <span className="text-14 text-[#D0D5DD]">{cash.label}</span>
          <strong className="text-17 text-white">{cash.display}</strong>
        </article>
      )}

      {cards.map((card) =>
        card.kind === "plan" ? (
          <PlanCard key={card.key} card={card} state={plans[card.planId]} onApprove={onApprove} />
        ) : (
          card.blocks.map((b) => (
            <article
              key={`${card.key}-${b.id}`}
              className={cn("min-w-0", b.type === "report" ? "rounded-card" : blockSurface(b), ENTER, card.group === newestGroup && b.type !== "report" && HIGHLIGHT)}
            >
              <UiBlockView
                block={b}
                handlers={
                  b.type === "report"
                    ? { ...handlers, compactReports: !card.full, activeCue: card.group === newestGroup ? cueFor(card.segments, aiText) : null }
                    : handlers
                }
              />
            </article>
          ))
        ),
      )}
    </section>
  );
}

/** The segment whose text the AI is speaking now (by transcript length). */
function cueFor(segments: { cue: string; text: string }[] | undefined, said: string): string | null {
  if (!segments?.length) return null;
  const n = said.length;
  let acc = 0;
  for (const s of segments) {
    acc += s.text.length;
    if (n <= acc) return s.cue;
  }
  return segments[segments.length - 1]?.cue ?? null;
}
