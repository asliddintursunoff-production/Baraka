import { Check, Info, LoaderCircle, TriangleAlert, X } from "lucide-react";
import { useState } from "react";

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
  const hasReport = blocks.some((b) => b.type === "report");
  const planNote = approved ? (planState?.summary ?? plan?.summary ?? "") : "";

  return (
    <article className="flex min-w-0 flex-col gap-4 [overflow-wrap:anywhere]">
      {markdown ? (
        <Markdown text={markdown} />
      ) : hasReport ? null : (
        <div className="flex flex-col gap-2">
          <div className="flex items-start gap-2">
            <span className={cn("mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full", v.bg, v.color)}>
              <v.Icon size={14} strokeWidth={2.8} aria-hidden="true" />
            </span>
            <h2 className="m-0 min-w-0 text-[19px] font-semibold leading-snug text-ink">{answer.headline}</h2>
          </div>
          {answer.reason && (
            <p className="m-0 text-16 leading-[1.6] text-text-2 [&_strong]:text-ink">
              <RichText text={answer.reason} />
            </p>
          )}
        </div>
      )}

      {(answer.demo?.cards ?? []).length > 0 && (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {(answer.demo?.cards ?? []).map((c) => (
            <button
              key={c.intent}
              type="button"
              disabled={busy}
              onClick={() => onAsk(c.text)}
              className="flex min-h-[64px] items-center rounded-card border border-border bg-surface px-4 py-3 text-left text-15 font-semibold leading-snug text-ink hover:bg-[#F9FAFB] disabled:opacity-60"
            >
              {c.text}
            </button>
          ))}
        </div>
      )}

      {blocks.length > 0 && (
        <div>
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
        <div>
          <AssumptionChips items={assumptions} onRecomputed={setRecomputed} />
        </div>
      )}

      {hasActions && (
        <div className="flex flex-col gap-3">
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
                  className="min-h-tap rounded-pill border border-border-input bg-surface px-4 text-14 font-semibold text-text-2 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
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
        <div className="flex flex-wrap items-center gap-[14px]">
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
