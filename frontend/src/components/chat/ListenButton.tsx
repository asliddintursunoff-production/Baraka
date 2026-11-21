import { LoaderCircle } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { PlayIcon, StopIcon } from "./icons";

type Phase = "idle" | "loading" | "playing" | "error";

/** "Tinglash": plays GET /api/chat/messages/{id}/speech (audio/wav); spinner until playback starts. */
export function ListenButton({ messageId }: { messageId: number | null }) {
  const [phase, setPhase] = useState<Phase>("idle");
  const audioRef = useRef<HTMLAudioElement | null>(null);

  useEffect(
    () => () => {
      audioRef.current?.pause();
      audioRef.current = null;
    },
    [],
  );

  const stop = () => {
    const a = audioRef.current;
    if (a) {
      a.pause();
      a.currentTime = 0;
    }
    setPhase("idle");
  };

  const play = () => {
    if (messageId == null) return;
    let a = audioRef.current;
    if (!a) {
      const audio = new Audio(`/api/chat/messages/${messageId}/speech`);
      audio.preload = "auto";
      audio.addEventListener("playing", () => setPhase("playing"));
      audio.addEventListener("ended", () => setPhase("idle"));
      audio.addEventListener("error", () => {
        if (audioRef.current === audio) audioRef.current = null;
        setPhase("error");
      });
      audioRef.current = audio;
      a = audio;
    } else {
      a.currentTime = 0;
    }
    setPhase("loading");
    a.play().catch((e: unknown) => {
      // pause() during loading rejects play() with AbortError: that is a user stop, not a failure.
      if (e instanceof DOMException && e.name === "AbortError") return;
      audioRef.current = null;
      setPhase("error");
    });
  };

  const active = phase === "loading" || phase === "playing";
  return (
    <span className="inline-flex flex-wrap items-center gap-[10px]">
      <button
        type="button"
        onClick={active ? stop : play}
        disabled={messageId == null}
        aria-label={active ? "Tinglashni to'xtatish" : "Javobni ovozda tinglash"}
        aria-busy={phase === "loading" || undefined}
        className="inline-flex min-h-tap items-center gap-2 rounded-pill border border-border-input bg-surface pl-[6px] pr-[14px] text-14 font-semibold text-text-2 hover:bg-surface-muted disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="flex h-7 w-7 items-center justify-center rounded-[14px] bg-primary">
          {phase === "loading" ? (
            <LoaderCircle size={14} color="#FFFFFF" strokeWidth={2.6} className="motion-safe:animate-spin" aria-hidden="true" />
          ) : phase === "playing" ? (
            <StopIcon size={12} />
          ) : (
            <PlayIcon />
          )}
        </span>
        Tinglash
      </button>
      {phase === "error" && (
        <span role="status" className="text-14 font-semibold text-danger">
          Ovozni yuklab bo'lmadi.
        </span>
      )}
    </span>
  );
}
