import { LoaderCircle } from "lucide-react";
import type { FormEvent, RefObject } from "react";
import { Link } from "react-router-dom";

import type { Chip, SendPayload } from "@/lib/chatTypes";
import { cn } from "@/lib/utils";

import { MicIcon, SendIcon, StopIcon, WaveIcon } from "./icons";
import { prefetchLive } from "./live";
import { useVoiceRecorder } from "./useVoiceRecorder";

interface Props {
  chips: Chip[];
  /** A message is streaming. */
  busy: boolean;
  value: string;
  onChange: (v: string) => void;
  onSend: (payload: SendPayload, display: string) => void;
  inputRef: RefObject<HTMLInputElement>;
  containerRef: RefObject<HTMLDivElement>;
}

const ROUND_BTN = "flex h-12 w-12 shrink-0 items-center justify-center rounded-[24px]";

export function Composer({ chips, busy, value, onChange, onSend, inputRef, containerRef }: Props) {
  const mic = useVoiceRecorder((r) => onSend({ text: r.text, voice: { duration: r.duration } }, r.text));
  const recording = mic.phase === "recording";
  const micBusy = mic.phase === "starting" || mic.phase === "transcribing";
  const blocked = busy || mic.phase !== "idle";

  const submit = (e: FormEvent) => {
    e.preventDefault();
    const text = value.trim();
    if (!text || blocked) return;
    onSend({ text }, text);
    onChange("");
  };

  const micStatus = recording
    ? "Gapiring… Tugatgach, mikrofon tugmasini yana bosing."
    : mic.phase === "transcribing"
      ? "Ovozingizni matnga aylantiryapman…"
      : "";

  return (
    <div ref={containerRef} className="sticky bottom-0 z-10 border-t border-border bg-bg px-4 pb-6 pt-3 sm:px-8">
      <div className="mx-auto flex max-w-[836px] flex-col gap-[10px]">
        {chips.length > 0 && (
          <div className="-m-1 flex gap-2 overflow-x-auto p-1 sm:flex-wrap sm:overflow-visible">
            {chips.map((c) => (
              <button
                key={c.id}
                type="button"
                disabled={blocked}
                onClick={() => onSend({ chip: c.id }, c.label)}
                className="min-h-tap shrink-0 rounded-pill border border-border-input bg-surface px-[14px] text-14 font-semibold text-text-2 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
              >
                {c.label}
              </button>
            ))}
          </div>
        )}
        <form
          onSubmit={submit}
          className="flex items-center gap-[10px] rounded-card border border-border-input bg-surface py-2 pl-4 pr-2 shadow-[0_2px_6px_rgba(16,24,40,.06)] has-[input:focus-visible]:border-primary has-[input:focus-visible]:shadow-[0_0_0_3px_rgba(29,78,216,.18)]"
        >
          <label htmlFor="ask" className="sr-only">
            AI CFO'ga savol
          </label>
          <input
            id="ask"
            ref={inputRef}
            type="text"
            value={value}
            onChange={(e) => onChange(e.target.value)}
            placeholder="Savolingizni yozing…"
            autoComplete="off"
            enterKeyHint="send"
            className="min-h-tap min-w-0 grow border-0 bg-transparent text-16 text-ink outline-none placeholder:text-text-4"
          />
          <button
            type="button"
            onClick={mic.toggle}
            disabled={busy || micBusy}
            aria-label={recording ? "Yozishni tugatib yuborish" : "Ovozli xabar yozib yuborish"}
            className={cn(
              ROUND_BTN,
              "border disabled:cursor-not-allowed disabled:opacity-60",
              recording ? "border-danger bg-danger-bg" : "border-border-input bg-surface hover:bg-surface-muted",
            )}
          >
            {recording ? (
              <StopIcon size={18} color="#B42318" />
            ) : micBusy ? (
              <LoaderCircle size={22} color="#344054" className="motion-safe:animate-spin" aria-hidden="true" />
            ) : (
              <MicIcon size={22} color="#344054" />
            )}
          </button>
          <Link
            to="/live"
            aria-label="Jonli suhbatni boshlash"
            onMouseEnter={prefetchLive}
            onFocus={prefetchLive}
            className={cn(ROUND_BTN, "bg-ink no-underline")}
          >
            <WaveIcon size={22} d="M3 12h2M7 8v8M11 5v14M15 8v8M19 10v4" />
          </Link>
          <button
            type="submit"
            aria-label="Yuborish"
            disabled={blocked || !value.trim()}
            className={cn(ROUND_BTN, "border-0 bg-primary hover:bg-primary-hover disabled:cursor-not-allowed disabled:opacity-60")}
          >
            <SendIcon />
          </button>
        </form>
        <p role="status" className={cn("m-0 text-14 font-semibold text-text-3", !micStatus && "sr-only")}>
          {micStatus}
        </p>
        {mic.error && (
          <p role="alert" className="m-0 text-14 font-semibold text-danger">
            {mic.error}
          </p>
        )}
      </div>
    </div>
  );
}
