import { useEffect, useRef, useState } from "react";

import type { TranscribeResult } from "@/lib/chatTypes";
import { csrfToken } from "@/lib/sse";

export type MicPhase = "idle" | "starting" | "recording" | "transcribing";

const MAX_RECORDING_MS = 30_000;
// The transcribe endpoint accepts audio/webm or audio/ogg (docs/API_CHAT.md).
const MIME_TYPES = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/ogg"];

const MSG = {
  denied: "Mikrofonga ruxsat berilmagan. Brauzer sozlamalarida mikrofonga ruxsat bering va qaytadan urinib ko'ring.",
  noMic: "Mikrofon topilmadi. Mikrofonni ulab, qaytadan urinib ko'ring.",
  busy: "Mikrofon boshqa dasturda band. Uni yopib, qaytadan urinib ko'ring.",
  unsupported: "Bu brauzerda ovoz yozib bo'lmaydi. Savolingizni yozib yuboring.",
  generic: "Mikrofonni yoqib bo'lmadi. Qaytadan urinib ko'ring.",
  transcribe: "Ovozni tushunib bo'lmadi. Qaytadan gapiring yoki yozib yuboring.",
};

function micErrorText(e: unknown): string {
  const name = e instanceof DOMException || e instanceof Error ? e.name : "";
  if (name === "NotAllowedError" || name === "SecurityError" || name === "PermissionDeniedError") return MSG.denied;
  if (name === "NotFoundError" || name === "OverconstrainedError" || name === "DevicesNotFoundError") return MSG.noMic;
  if (name === "NotReadableError" || name === "TrackStartError") return MSG.busy;
  return MSG.generic;
}

/**
 * Mic → MediaRecorder (≤ 30 s) → POST /api/chat/transcribe (raw body) → `onResult`.
 * Press once to start, again to stop and send.
 */
export function useVoiceRecorder(onResult: (r: TranscribeResult) => void) {
  const [phase, setPhase] = useState<MicPhase>("idle");
  const [error, setError] = useState<string | null>(null);
  const mounted = useRef(false);
  const recorder = useRef<MediaRecorder | null>(null);
  const stream = useRef<MediaStream | null>(null);
  const timer = useRef<number | undefined>(undefined);
  const upload = useRef<AbortController | null>(null);
  const onResultRef = useRef(onResult);

  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      window.clearTimeout(timer.current);
      upload.current?.abort();
      const rec = recorder.current;
      recorder.current = null;
      if (rec) {
        rec.onstop = null;
        if (rec.state !== "inactive") rec.stop();
      }
      stream.current?.getTracks().forEach((t) => t.stop());
      stream.current = null;
    };
  }, []);

  const releaseMic = () => {
    window.clearTimeout(timer.current);
    stream.current?.getTracks().forEach((t) => t.stop());
    stream.current = null;
  };

  const transcribe = async (blob: Blob) => {
    setPhase("transcribing");
    const ctrl = new AbortController();
    upload.current = ctrl;
    try {
      const res = await fetch("/api/chat/transcribe", {
        method: "POST",
        credentials: "same-origin",
        headers: { "Content-Type": blob.type, "X-CSRFToken": csrfToken() },
        body: blob,
        signal: ctrl.signal,
      });
      const data = (await res.json().catch(() => null)) as (Partial<TranscribeResult> & { message?: string }) | null;
      if (!mounted.current) return;
      const text = data?.text?.trim() ?? "";
      setPhase("idle");
      if (!res.ok || !text) {
        setError(data?.message || MSG.transcribe);
        return;
      }
      onResultRef.current({ text, duration: data?.duration ?? "" });
    } catch {
      if (ctrl.signal.aborted || !mounted.current) return;
      setPhase("idle");
      setError(MSG.transcribe);
    } finally {
      if (upload.current === ctrl) upload.current = null;
    }
  };

  const stop = () => {
    const rec = recorder.current;
    if (rec && rec.state !== "inactive") rec.stop();
  };

  const start = async () => {
    setError(null);
    if (!navigator.mediaDevices?.getUserMedia || typeof MediaRecorder === "undefined") {
      setError(MSG.unsupported);
      return;
    }
    setPhase("starting");
    let media: MediaStream;
    try {
      media = await navigator.mediaDevices.getUserMedia({ audio: true });
    } catch (e) {
      if (!mounted.current) return;
      setPhase("idle");
      setError(micErrorText(e));
      return;
    }
    if (!mounted.current) {
      media.getTracks().forEach((t) => t.stop());
      return;
    }
    stream.current = media;
    const mime = MIME_TYPES.find((t) => MediaRecorder.isTypeSupported(t));
    let rec: MediaRecorder;
    try {
      rec = new MediaRecorder(media, mime ? { mimeType: mime } : undefined);
    } catch {
      releaseMic();
      setPhase("idle");
      setError(MSG.unsupported);
      return;
    }
    const chunks: Blob[] = [];
    rec.ondataavailable = (e) => {
      if (e.data.size > 0) chunks.push(e.data);
    };
    rec.onstop = () => {
      releaseMic();
      recorder.current = null;
      const type = (rec.mimeType || mime || "audio/webm").split(";")[0]!;
      const blob = new Blob(chunks, { type });
      if (blob.size === 0) {
        setPhase("idle");
        setError(MSG.transcribe);
        return;
      }
      void transcribe(blob);
    };
    recorder.current = rec;
    rec.start();
    setPhase("recording");
    timer.current = window.setTimeout(stop, MAX_RECORDING_MS);
  };

  const toggle = () => {
    if (phase === "recording") stop();
    else if (phase === "idle") void start();
  };

  return { phase, error, toggle };
}
