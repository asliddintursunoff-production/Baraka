import { Check, LoaderCircle } from "lucide-react";

import { RichText } from "@/components/RichText";
import type { Candidate } from "@/lib/chatTypes";
import { cn } from "@/lib/utils";

import type { ActionStatus } from "./useAnswerActions";

interface Props {
  candidate: Candidate;
  status: ActionStatus | undefined;
  onAccept: () => void;
  onEdit: () => void;
}

/** "AI o'rgandi" bubble (Chat.html learning example): rule text + example, warning, confirm buttons. */
export function LearningCard({ candidate, status, onAccept, onEdit }: Props) {
  const done = status === "done";
  const pending = status === "pending";
  return (
    <div className="flex w-full max-w-[620px] flex-[1_1_auto] flex-col gap-3 self-start rounded-[4px_16px_16px_16px] border border-border bg-surface p-4 [overflow-wrap:anywhere]">
      <span className="text-16 leading-[1.55]">
        <RichText text={candidate.text} />
        {candidate.example && (
          <>
            {" "}
            <RichText text={candidate.example} />
          </>
        )}
      </span>
      {candidate.warning && (
        <span className="text-15 font-semibold leading-normal text-warning">
          <RichText text={candidate.warning} />
        </span>
      )}
      <div className="flex flex-wrap gap-[10px]">
        <button
          type="button"
          onClick={() => {
            if (!done && !pending) onAccept();
          }}
          aria-disabled={done || pending || undefined}
          aria-busy={pending || undefined}
          className={cn(
            "inline-flex min-h-tap items-center gap-2 rounded-btn border-0 px-[18px] text-15 font-semibold text-white",
            done ? "cursor-default bg-success" : "bg-ink hover:bg-text-2",
            pending && "cursor-wait opacity-80",
          )}
        >
          {done && <Check size={18} strokeWidth={2.6} aria-hidden="true" />}
          {pending && <LoaderCircle size={18} className="motion-safe:animate-spin" aria-hidden="true" />}
          {done ? "Eslab qoldim" : "To'g'ri, eslab qol"}
        </button>
        {!done && (
          <button
            type="button"
            onClick={onEdit}
            className="min-h-tap rounded-btn border border-border-input bg-surface px-[18px] text-15 font-semibold text-text-2 hover:bg-surface-muted"
          >
            O'zgartirish
          </button>
        )}
      </div>
      <p role="status" className={cn("m-0 text-14 font-semibold text-danger", status !== "error" && "sr-only")}>
        {status === "error" ? "Saqlab bo'lmadi. Qaytadan urinib ko'ring." : done ? "Eslab qoldim" : ""}
      </p>
    </div>
  );
}
