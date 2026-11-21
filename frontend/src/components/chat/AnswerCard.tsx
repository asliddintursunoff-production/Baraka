import { Check, Copy, FileDown, Info, LoaderCircle, TriangleAlert, X } from "lucide-react";
import { useRef, useState } from "react";

import { Markdown } from "@/components/Markdown";
import { RichText } from "@/components/RichText";
import { ChatSteps, PlanTimeline, UiBlockRenderer, type UiBlock } from "@/components/UiBlockRenderer";
import type { Answer, AnswerVerdict } from "@/lib/chatTypes";
import { cn } from "@/lib/utils";

import { AssumptionChips, type Recomputed } from "./AssumptionChips";
import type { AnswerActions } from "./useAnswerActions";

const VERDICT: Record<AnswerVerdict, { bg: string; color: string; Icon: typeof Check }> = {
  yes: { bg: "bg-success-bg", color: "text-success", Icon: Check },
  no: { bg: "bg-danger-bg", color: "text-danger", Icon: X },
  risky: { bg: "bg-warning-bg", color: "text-warning", Icon: TriangleAlert },
  info: { bg: "bg-primary-soft", color: "text-primary", Icon: Info },
};

/** Shown when an answer has a plan but no follow-up chips, so "Ha" always has its alternative. */
const ALTERNATIVE = "Boshqa yo'l bormi?";

/** Verdict, reason and steps come from `Answer` itself; approval only when there is no `plan`. */
export function cardBlocks(answer: Answer, blocks: UiBlock[] = answer.blocks ?? []): UiBlock[] {
  return blocks.filter((b) => b.type !== "verdict" && b.type !== "steps" && !(answer.plan && b.type === "approval"));
}

function approvedIds(actions: AnswerActions): Set<string> {
  return new Set(
    Object.entries(actions.plans)
      .filter(([, s]) => s.status === "done")
      .map(([id]) => id),
  );
}

export function hasCardContent(answer: Answer): boolean {
  const adv = answer.advisor;
  return (
    Boolean(answer.markdown?.trim()) ||
    (answer.steps ?? []).length > 0 ||
    cardBlocks(answer).length > 0 ||
    answer.plan != null ||
    (adv != null && ((adv.plan ?? []).length > 0 || (adv.assumptions ?? []).length > 0 || (adv.risks ?? []).length > 0))
  );
}

interface Props {
  answer: Answer;
  /** Server id of the assistant message (needed for "Tinglash"); null while still streaming. */
  messageId: number | null;
  /** A message is streaming: follow-up questions wait. */
  busy: boolean;
  onAsk: (text: string) => void;
  actions: AnswerActions;
}

export function AnswerCard({ answer, busy, onAsk, actions }: Props) {
  const v = VERDICT[answer.verdict] ?? VERDICT.info;
  const advisor = answer.advisor ?? null;
  /** Result of re-running a tool from an edited assumption (replaces blocks + assumptions). */
  const [recomputed, setRecomputed] = useState<Recomputed | null>(null);
  /** Markdown answers carry verdict, reason, steps, risks and the question in the text itself. */
  const markdown = (answer.markdown ?? "").trim();
  const timeline = markdown ? [] : advisor ? (advisor.plan ?? []) : [];
  const steps = markdown || advisor ? [] : (answer.steps ?? []);
  const risks = markdown ? [] : (advisor?.risks ?? []);
  const question = markdown ? null : (advisor?.question ?? null);
  const assumptions = recomputed ? recomputed.assumptions : (advisor?.assumptions ?? []);
  const explain = answer.explain ?? [];
  const blocks = cardBlocks(answer, recomputed ? recomputed.blocks : undefined);
  const plan = answer.plan;
  const planState = plan
    ? (actions.plans[plan.id] ?? (plan.status === "approved" ? { status: "done" as const, summary: plan.summary } : undefined))
    : undefined;
  const approved = planState?.status === "done";
  const approving = planState?.status === "pending";
  const followUps = (answer.chips ?? []).length > 0 ? answer.chips : plan ? [ALTERNATIVE] : [];
  const hasActions =
    steps.length > 0 || timeline.length > 0 || risks.length > 0 || question != null || plan != null || followUps.length > 0;
  const cardRef = useRef<HTMLElement>(null);
  const [copied, setCopied] = useState(false);
  const planNote = approved ? (planState?.summary ?? plan?.summary ?? "") : "";

  return (
    <article
      ref={cardRef}
      className="min-w-0 flex-[1_1_auto] overflow-hidden rounded-[4px_16px_16px_16px] border border-border bg-surface [overflow-wrap:anywhere]"
    >
      {markdown ? (
        <div className="px-[22px] pb-[18px] pt-[22px]">
          <Markdown text={markdown} />
          <div className="mt-3 flex flex-wrap gap-2 print:hidden">
            <button
              type="button"
              onClick={() => {
                void navigator.clipboard?.writeText(markdown).then(() => {
                  setCopied(true);
                  window.setTimeout(() => setCopied(false), 1500);
                });
              }}
              className="inline-flex items-center gap-1 rounded-pill border border-border px-3 py-1 text-13 text-text-3 hover:text-ink"
            >
              <Copy size={14} /> {copied ? "Nusxa olindi" : "Nusxa olish"}
            </button>
            <button
              type="button"
              onClick={() => exportPdf(cardRef.current)}
              className="inline-flex items-center gap-1 rounded-pill border border-border px-3 py-1 text-13 text-text-3 hover:text-ink"
            >
              <FileDown size={14} /> Hisobot (PDF)
            </button>
          </div>
        </div>
      ) : (
        <div className="flex flex-col gap-[10px] px-[22px] pb-[18px] pt-[22px]">
          <div className="flex items-center gap-3">
            <span className={cn("flex h-10 w-10 shrink-0 items-center justify-center rounded-[20px]", v.bg, v.color)}>
              <v.Icon size={22} strokeWidth={2.6} aria-hidden="true" />
            </span>
            <h2 className={cn("m-0 min-w-0 font-display text-26 font-bold leading-[1.2]", v.color)}>{answer.headline}</h2>
          </div>
          {answer.reason && (
            <p className="m-0 text-17 leading-[1.6] text-text-2 [&_strong]:text-ink">
              <RichText text={answer.reason} />
            </p>
          )}
        </div>
      )}

      {blocks.length > 0 && (
        <div className={cn("mx-[22px]", !hasActions && assumptions.length === 0 && "mb-[22px]")}>
          <UiBlockRenderer
            blocks={blocks}
            handlers={{
              onApprove: (id) => actions.approve(Number(id)),
              onAlternative: () => onAsk(ALTERNATIVE),
              approved: approvedIds(actions),
            }}
          />
        </div>
      )}

      {assumptions.length > 0 && (
        <div className={cn("mx-[22px] pt-4", !hasActions && "mb-[22px]")}>
          <AssumptionChips items={assumptions} onRecomputed={setRecomputed} />
        </div>
      )}

      {hasActions && (
        <div className="flex flex-col gap-3 px-[22px] py-5">
          {steps.length > 0 && (
            <>
              <span className="text-15 font-bold">Nima qilasiz:</span>
              <ChatSteps items={steps.map((text) => ({ text }))} />
            </>
          )}
          {timeline.length > 0 && (
            <>
              <span className="text-15 font-bold">Nima qilasiz:</span>
              <PlanTimeline steps={timeline} />
            </>
          )}
          {risks.length > 0 && (
            <div className="flex flex-col gap-1 rounded-inner bg-warning-bg p-[14px]">
              <span className="inline-flex items-center gap-[6px] text-14 font-bold text-warning">
                <TriangleAlert size={16} strokeWidth={2.4} aria-hidden="true" />
                Xavf
              </span>
              <ul className="m-0 list-disc pl-5 text-14 leading-[1.6] text-text-2">
                {risks.map((r, i) => (
                  <li key={i}>
                    <RichText text={r} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          {question && (
            <p className="m-0 text-16 font-semibold text-ink">
              <RichText text={question} />
            </p>
          )}
          {(plan || followUps.length > 0) && (
            <div className="flex flex-wrap gap-[10px] pt-[6px]">
              {plan && (
                <button
                  type="button"
                  onClick={() => {
                    if (!approved && !approving) actions.approve(plan.id);
                  }}
                  aria-disabled={approved || approving || undefined}
                  aria-busy={approving || undefined}
                  className={cn(
                    "inline-flex min-h-12 items-center gap-2 rounded-btn-lg border-0 px-[22px] text-16 font-semibold text-white",
                    approved ? "cursor-default bg-success" : "bg-primary hover:bg-primary-hover",
                    approving && "cursor-wait opacity-80",
                  )}
                >
                  {approved && <Check size={20} strokeWidth={2.6} aria-hidden="true" />}
                  {approving && <LoaderCircle size={18} className="motion-safe:animate-spin" aria-hidden="true" />}
                  {approved ? "Tasdiqlandi" : "Ha, shunday qilamiz"}
                </button>
              )}
              {followUps.map((text) => (
                <button
                  key={text}
                  type="button"
                  disabled={busy}
                  onClick={() => onAsk(text)}
                  className="min-h-12 rounded-btn-lg border border-border-input bg-surface px-5 text-16 font-semibold text-text-2 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {text}
                </button>
              ))}
            </div>
          )}
          {plan && (
            <p
              role="status"
              className={cn(
                "m-0 text-14 font-semibold",
                planState?.status === "error" ? "text-danger" : "text-success",
                !planNote && planState?.status !== "error" && "sr-only",
              )}
            >
              {planState?.status === "error" ? "Tasdiqlab bo'lmadi. Qaytadan urinib ko'ring." : planNote}
            </p>
          )}
        </div>
      )}

      {(answer.speech || explain.length > 0) && (
        <div className="flex flex-wrap items-center gap-[14px] border-t border-border-subtle bg-surface-muted-2 px-[22px] py-3">
          {explain.length > 0 && (
            <details className="min-w-0 flex-[1_1_260px]">
              <summary className="flex min-h-tap cursor-pointer items-center text-14 font-semibold text-text-3">
                Qanday hisobladim?
              </summary>
              <ul className="mb-1 mt-[6px] list-disc pl-5 text-14 leading-[1.7] text-text-3">
                {explain.map((line, i) => (
                  <li key={i}>
                    <RichText text={line} />
                  </li>
                ))}
              </ul>
            </details>
          )}
        </div>
      )}
    </article>
  );
}

/** "Hisobot": the answer (tables + charts as rendered) in a print window -> "Save as PDF". */
function exportPdf(el: HTMLElement | null): void {
  if (!el) return;
  const w = window.open("", "_blank", "width=900,height=1000");
  if (!w) return;
  const styles = Array.from(document.querySelectorAll('link[rel="stylesheet"], style'))
    .map((n) => n.outerHTML)
    .join("");
  w.document.write(
    `<!doctype html><html><head><meta charset="utf-8"><title>Baraka — hisobot</title>${styles}` +
      `<style>body{padding:24px;background:#fff} .print\\:hidden{display:none!important} table{page-break-inside:avoid}</style>` +
      `</head><body><h2 style="font-family:sans-serif">Baraka · AI CFO hisobot · ${new Date().toLocaleString("uz-UZ")}</h2>${el.outerHTML}</body></html>`,
  );
  w.document.close();
  w.onload = () => {
    w.focus();
    w.print();
  };
}
