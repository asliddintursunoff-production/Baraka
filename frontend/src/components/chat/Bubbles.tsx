import type { ReactNode } from "react";

import type { Voice } from "@/lib/chatTypes";

import { MicIcon, SparkIcon } from "./icons";

/** "Siz · 10:41" — the time is omitted for messages sent in this session (the API gives none). */
export function metaLabel(author: string, time: string): string {
  return time ? `${author} · ${time}` : author;
}

export function DaySeparator({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-3 text-13 font-semibold text-text-4">
      <span className="h-px grow bg-border" aria-hidden="true" />
      {label}
      <span className="h-px grow bg-border" aria-hidden="true" />
    </div>
  );
}

function Avatar() {
  return (
    <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-btn bg-ink" aria-hidden="true">
      <SparkIcon />
    </div>
  );
}

/** Avatar + content column. `live` marks the bubble that is being streamed right now. */
export function AssistantRow({ children, live = false }: { children: ReactNode; live?: boolean }) {
  return (
    <div className="flex items-start gap-3" aria-live={live ? "polite" : undefined}>
      <Avatar />
      <div className="flex min-w-0 flex-[1_1_auto] flex-col gap-3">{children}</div>
    </div>
  );
}

export function AssistantText({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="flex max-w-[620px] flex-col gap-[6px] self-start">
      <span className="text-12 font-semibold text-text-4">{label}</span>
      <div className="rounded-[4px_16px_16px_16px] border border-border bg-surface px-4 py-[14px] text-16 leading-[1.55] [overflow-wrap:anywhere]">
        {children}
      </div>
    </div>
  );
}

export function UserMessage({ label, text, voice }: { label: string; text: string; voice: Voice | null }) {
  return (
    <div className="flex flex-col items-end gap-[6px]">
      <span className="text-12 font-semibold text-text-4">{label}</span>
      <div className="flex max-w-[520px] flex-col gap-2 rounded-[16px_4px_16px_16px] bg-primary px-4 py-[14px] text-white [overflow-wrap:anywhere]">
        {voice && (
          <span className="inline-flex items-center gap-2 text-13 text-[#D1E0FF]">
            <MicIcon size={16} color="#D1E0FF" />
            {voice.duration ? `Ovozli · ${voice.duration}` : "Ovozli"}
          </span>
        )}
        <span className="whitespace-pre-wrap text-16 leading-normal">{text}</span>
      </div>
    </div>
  );
}
