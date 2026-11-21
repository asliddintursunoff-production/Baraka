/** Live footer controls and the "Yozib so'rash" text fallback (design/pages/Live.html). */
import { useState } from "react";
import { Link } from "react-router-dom";

import { cn } from "@/lib/utils";

const PILL =
  "inline-flex min-h-[64px] items-center gap-[10px] rounded-[32px] border-0 text-white no-underline hover:text-white";

function PauseIcon() {
  return (
    <svg width="20" height="20" viewBox="0 0 24 24" fill="#101828" aria-hidden="true">
      <rect x="6" y="5" width="4" height="14" rx="1" />
      <rect x="14" y="5" width="4" height="14" rx="1" />
    </svg>
  );
}

function KeyboardIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2" aria-hidden="true">
      <rect x="2" y="6" width="20" height="12" rx="2" />
      <path d="M6 10h.01M10 10h.01M14 10h.01M18 10h.01M7 14h10" />
    </svg>
  );
}

function HangUpIcon() {
  return (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" strokeWidth="2.2" aria-hidden="true">
      <path d="M3 15c5-5 13-5 18 0l-2.5 2.5-3-1.5v-3a12 12 0 0 0-7 0v3l-3 1.5z" />
    </svg>
  );
}

export const TEXT_FORM_ID = "live-text-form";

export function LiveControls({
  speaking,
  onStop,
  textMode,
  textOpen,
  onToggleText,
  onFinish,
  finishing,
}: {
  speaking: boolean;
  onStop: () => void;
  /** "inline": the session is open, typed questions go to Live. "chat": no session, go to /chat. */
  textMode: "inline" | "chat";
  textOpen: boolean;
  onToggleText: () => void;
  onFinish: () => void;
  finishing: boolean;
}) {
  return (
    <footer className="flex flex-wrap items-center justify-center gap-4 px-4 pb-8 pt-5 sm:px-8">
      <button
        type="button"
        onClick={onStop}
        disabled={!speaking}
        aria-label="AI ovozini to'xtatish"
        className={cn(PILL, "bg-white px-[26px] text-16 font-bold text-ink hover:text-ink disabled:cursor-default disabled:opacity-50")}
      >
        <PauseIcon />
        To'xtatish
      </button>
      {textMode === "inline" ? (
        <button
          type="button"
          onClick={onToggleText}
          aria-expanded={textOpen}
          aria-controls={TEXT_FORM_ID}
          className={cn(PILL, "bg-live-border px-[22px] text-15 font-semibold")}
        >
          <KeyboardIcon />
          Yozib so'rash
        </button>
      ) : (
        <Link to="/chat" className={cn(PILL, "bg-live-border px-[22px] text-15 font-semibold")}>
          <KeyboardIcon />
          Yozib so'rash
        </Link>
      )}
      <button
        type="button"
        onClick={onFinish}
        disabled={finishing}
        aria-busy={finishing || undefined}
        className={cn(PILL, "bg-danger-strong px-[26px] text-15 font-bold disabled:cursor-wait disabled:opacity-80")}
      >
        <HangUpIcon />
        Tugatish
      </button>
    </footer>
  );
}

export function LiveTextForm({ onSend }: { onSend: (text: string) => void }) {
  const [text, setText] = useState("");
  return (
    <form
      id={TEXT_FORM_ID}
      className="flex w-full max-w-[600px] gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        const t = text.trim();
        if (!t) return;
        onSend(t);
        setText("");
      }}
    >
      <input
        // Opened by "Yozib so'rash" or offered after a mic error: typing is the next step.
        autoFocus
        className="min-h-tap min-w-0 flex-1 rounded-btn border border-live-border bg-live-surface px-4 text-16 text-white placeholder:text-[#98A2B3]"
        placeholder="Savolingizni yozing…"
        aria-label="Yozib so'rash"
        maxLength={300}
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button
        type="submit"
        className="min-h-tap shrink-0 rounded-btn border-0 bg-primary px-[18px] text-15 font-semibold text-white hover:bg-primary-hover"
      >
        Yuborish
      </button>
    </form>
  );
}
