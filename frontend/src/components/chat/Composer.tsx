import { LoaderCircle, Paperclip } from "lucide-react";
import { useLayoutEffect, useState, type FormEvent, type KeyboardEvent, type RefObject } from "react";
import { Link } from "react-router-dom";

import type { SendPayload } from "@/lib/chatTypes";
import { cn } from "@/lib/utils";

import { MicIcon, SendIcon, StopIcon, WaveIcon } from "./icons";
import { prefetchLive } from "./live";
import { useVoiceRecorder } from "./useVoiceRecorder";

interface Props {
  /** A message is streaming: send becomes ■ stop. */
  busy: boolean;
  value: string;
  onChange: (v: string) => void;
  onSend: (payload: SendPayload, display: string) => void;
  onStop?: () => void;
  inputRef: RefObject<HTMLTextAreaElement>;
  containerRef: RefObject<HTMLDivElement>;
}

const ICON_BTN = "grid size-tap shrink-0 place-items-center rounded-full border-0";
const MAX_ROWS = 8;
const LINE = 24;

/** Sticky composer: auto-growing textarea (1–8 lines), 📎 · 🎙 · ◉ Live · ➤ / ■. Enter sends, Shift+Enter = new line. */
export function Composer({ busy, value, onChange, onSend, onStop, inputRef, containerRef }: Props) {
  const mic = useVoiceRecorder((r) => onSend({ text: r.text, voice: { duration: r.duration } }, r.text));
  const recording = mic.phase === "recording";
  const micBusy = mic.phase === "starting" || mic.phase === "transcribing";
  const blocked = busy || mic.phase !== "idle";
  const [focused, setFocused] = useState(false);

  useLayoutEffect(() => {
    const el = inputRef.current;
    if (!el) return;
    el.style.height = "auto";
    // empty: one line (a long placeholder must not grow the box)
    if (value) el.style.height = `${Math.min(el.scrollHeight, LINE * MAX_ROWS + 16)}px`;
  }, [value, inputRef]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const text = value.trim();
    if (!text || blocked) return;
    onSend({ text }, text);
    onChange("");
  };
  const onKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey && !e.nativeEvent.isComposing) {
      e.preventDefault();
      submit();
    }
  };

  const micStatus = recording
    ? "Gapiring… Tugatgach, mikrofon tugmasini yana bosing."
    : mic.phase === "transcribing"
      ? "Ovozingizni matnga aylantiryapman…"
      : "";

  return (
    <div
      ref={containerRef}
      className="sticky bottom-0 z-20 bg-gradient-to-t from-bg via-bg to-bg/0 px-4 pb-[calc(8px+env(safe-area-inset-bottom))] pt-4 md:px-6"
    >
      <div className="mx-auto flex w-full max-w-chat flex-col gap-1.5">
        <form
          onSubmit={submit}
          className="flex items-end gap-1 rounded-[24px] border border-border-input bg-surface p-1.5 shadow-[0_4px_16px_rgba(16,24,40,.08)] has-[textarea:focus-visible]:border-primary"
        >
          <Link
            to="/files"
            aria-label="Excel fayl yuklash (Fayl tahlili)"
            title="Excel fayl yuklash — AI uni to'liq tahlil qiladi"
            className={cn(ICON_BTN, "text-text-3 hover:bg-[#F2F4F7] hover:text-ink")}
          >
            <Paperclip size={20} />
          </Link>
          <label htmlFor="ask" className="sr-only">
            AI CFO'ga savol
          </label>
          <textarea
            id="ask"
            ref={inputRef}
            rows={1}
            value={value}
            onChange={(e) => onChange(e.target.value)}
            onKeyDown={onKey}
            onFocus={() => setFocused(true)}
            onBlur={() => setFocused(false)}
            placeholder={focused ? "Savol yozing yoki rasm joylang…" : "Savolingizni yozing…"}
            autoComplete="off"
            enterKeyHint="send"
            className="h-tap max-h-[208px] min-h-tap overflow-y-auto placeholder:truncate min-w-0 flex-1 resize-none border-0 bg-transparent px-1 py-[10px] text-16 leading-6 text-ink outline-none placeholder:text-text-4"
          />
          <button
            type="button"
            onClick={mic.toggle}
            disabled={busy || micBusy}
            aria-label={recording ? "Yozishni tugatib yuborish" : "Ovoz bilan yozish"}
            className={cn(
              ICON_BTN,
              "disabled:cursor-not-allowed disabled:opacity-60",
              recording ? "bg-danger-bg" : "bg-transparent hover:bg-[#F2F4F7]",
            )}
          >
            {recording ? (
              <StopIcon size={18} color="#B42318" />
            ) : micBusy ? (
              <LoaderCircle size={20} color="#344054" className="motion-safe:animate-spin" aria-hidden="true" />
            ) : (
              <MicIcon size={20} color="#344054" />
            )}
          </button>
          <Link
            to="/live"
            aria-label="Jonli suhbatni boshlash"
            title="Jonli gaplashish"
            onMouseEnter={prefetchLive}
            onFocus={prefetchLive}
            className={cn(ICON_BTN, "bg-[#F2F4F7] no-underline hover:bg-border")}
          >
            <WaveIcon size={20} color="#101828" d="M3 12h2M7 8v8M11 5v14M15 8v8M19 10v4" />
          </Link>
          {busy && onStop ? (
            <button type="button" aria-label="To'xtatish" onClick={onStop} className={cn(ICON_BTN, "bg-ink")}>
              <StopIcon size={16} color="#FFFFFF" />
            </button>
          ) : (
            <button
              type="submit"
              aria-label="Yuborish"
              disabled={blocked || !value.trim()}
              className={cn(ICON_BTN, "bg-ink disabled:cursor-not-allowed disabled:bg-[#D0D5DD]")}
            >
              <SendIcon />
            </button>
          )}
        </form>
        <p role="status" className={cn("m-0 text-14 font-semibold text-text-3", !micStatus && "sr-only")}>
          {micStatus}
        </p>
        {mic.error && (
          <p role="alert" className="m-0 text-14 font-semibold text-danger">
            {mic.error}
          </p>
        )}
        <p className="m-0 text-center text-12 text-text-4">AI CFO xato qilishi mumkin — muhim qarorlarni tekshiring.</p>
      </div>
    </div>
  );
}
