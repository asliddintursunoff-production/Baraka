import { Check, Copy, Radio, RotateCcw, ThumbsDown, ThumbsUp } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import type { Voice } from "@/lib/chatTypes";
import { track } from "@/lib/telemetry";
import { cn } from "@/lib/utils";

import { MicIcon, SparkIcon } from "./icons";

/** "Siz · 10:41" — kept for hover titles only (no visible timestamps). */
export function metaLabel(author: string, time: string): string {
  return time ? `${author} · ${time}` : author;
}

/** Assistant answer: no bubble, full column width, small ✦ avatar. `live` = being streamed now. */
export function AssistantRow({ children, live = false, footer }: { children: ReactNode; live?: boolean; footer?: ReactNode }) {
  return (
    <div className="group/msg flex items-start gap-3" aria-live={live ? "polite" : undefined}>
      <div className="mt-0.5 hidden size-7 shrink-0 items-center justify-center rounded-full bg-ink sm:flex" aria-hidden="true">
        <SparkIcon size={14} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col gap-3 text-16 leading-[1.6]">
        {children}
        {footer}
      </div>
    </div>
  );
}

export function AssistantText({ children }: { label?: string; children: ReactNode }) {
  return <div className="text-16 leading-[1.6] text-ink [overflow-wrap:anywhere]">{children}</div>;
}

export function MessageUser({ label, text, voice }: { label: string; text: string; voice: Voice | null }) {
  return (
    <div className="flex justify-end" title={label}>
      <div className="flex max-w-[85%] flex-col gap-1 rounded-[18px] bg-[#F4F4F5] px-4 py-[10px] text-ink [overflow-wrap:anywhere] sm:max-w-[75%]">
        {voice && (
          <span className="inline-flex items-center gap-1.5 text-13 text-text-3">
            <MicIcon size={14} color="#475467" />
            {voice.duration ? `Ovozli · ${voice.duration}` : "Ovozli"}
          </span>
        )}
        <span className="whitespace-pre-wrap text-16 leading-normal">{text}</span>
      </div>
    </div>
  );
}

/** Kept for callers of the old name. */
export const UserMessage = MessageUser;

const ICON_BTN =
  "grid size-tap place-items-center rounded-btn border-0 bg-transparent text-text-3 hover:bg-[#F2F4F7] hover:text-ink md:size-9";

/** Copy · regenerate · 👍 · 👎 · Live — under every assistant answer (hover on desktop, always on mobile). */
export function MessageActions({ text, onRegenerate, busy }: { text: string; onRegenerate?: () => void; busy: boolean }) {
  const [copied, setCopied] = useState(false);
  const [vote, setVote] = useState<"up" | "down" | null>(null);
  const rate = (v: "up" | "down") => {
    setVote(v);
    track("chat", `feedback_${v}`, 0, {});
  };
  return (
    <div className="-ml-2 flex items-center gap-0.5 opacity-100 transition-opacity md:opacity-0 md:focus-within:opacity-100 md:group-hover/msg:opacity-100 print:hidden">
      <button
        type="button"
        aria-label="Nusxa olish"
        title="Nusxa olish"
        className={ICON_BTN}
        onClick={() => {
          void navigator.clipboard?.writeText(text).then(() => {
            setCopied(true);
            window.setTimeout(() => setCopied(false), 1500);
          });
        }}
      >
        {copied ? <Check size={16} /> : <Copy size={16} />}
      </button>
      {onRegenerate && (
        <button type="button" aria-label="Qayta javob" title="Qayta javob" disabled={busy} onClick={onRegenerate} className={cn(ICON_BTN, "disabled:opacity-50")}>
          <RotateCcw size={16} />
        </button>
      )}
      <button type="button" aria-label="Yaxshi javob" aria-pressed={vote === "up"} onClick={() => rate("up")} className={cn(ICON_BTN, vote === "up" && "text-success")}>
        <ThumbsUp size={16} />
      </button>
      <button type="button" aria-label="Yomon javob" aria-pressed={vote === "down"} onClick={() => rate("down")} className={cn(ICON_BTN, vote === "down" && "text-danger")}>
        <ThumbsDown size={16} />
      </button>
      <Link to="/live" className="inline-flex min-h-tap items-center gap-1.5 rounded-btn px-2 text-13 font-semibold text-text-3 no-underline hover:bg-[#F2F4F7] hover:text-ink md:min-h-9">
        <Radio size={16} aria-hidden="true" />
        Live'da ochish
      </Link>
    </div>
  );
}
