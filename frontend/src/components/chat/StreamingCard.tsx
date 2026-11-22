import { CircleAlert } from "lucide-react";

import { Markdown } from "@/components/Markdown";
import { UiBlockRenderer, type UiBlock } from "@/components/UiBlockRenderer";

function Dots() {
  return (
    <span className="inline-flex shrink-0 items-center gap-1" aria-hidden="true">
      {[0, 150, 300].map((delay) => (
        <span
          key={delay}
          className="h-[6px] w-[6px] rounded-[3px] bg-text-4 motion-safe:animate-pulse"
          style={{ animationDelay: `${delay}ms` }}
        />
      ))}
    </span>
  );
}

/**
 * The assistant bubble before the final `answer`: status line while waiting, the markdown text
 * from `delta` events as it arrives, cards from `blocks` below it, or the Uzbek error text.
 */
export function StreamingCard({
  status,
  pending,
  blocks,
  error,
  markdown = "",
}: {
  status: string | null;
  pending: boolean;
  blocks: UiBlock[] | null;
  error: string | null;
  markdown?: string;
}) {
  const cards = (blocks ?? []).filter((b) => b.type !== "approval");
  const text = markdown.trim();
  const waiting = pending && !error && !text && cards.length === 0;
  return (
    <div className="flex min-w-0 flex-col gap-4 [overflow-wrap:anywhere]">
      {text && <Markdown text={text} />}
      {pending && !error && (
        <span className="inline-flex items-center gap-[10px] text-14 font-semibold text-text-3">
          <Dots />
          {!text && status}
        </span>
      )}
      {waiting && status && <CardSkeleton />}
      {cards.length > 0 && <UiBlockRenderer blocks={cards} />}
      {error && (
        <p className="m-0 flex items-start gap-2 text-15 font-semibold leading-normal text-danger">
          <CircleAlert size={20} className="mt-[1px] shrink-0" aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  );
}

/** Report-shaped placeholder: title line, 4 KPI tiles, chart block. */
export function CardSkeleton() {
  return (
    <div className="flex flex-col gap-4 rounded-card border border-[#E5E7EB] bg-surface p-5" aria-hidden="true">
      <span className="h-5 w-2/3 rounded-md bg-[#F2F4F7] motion-safe:animate-pulse" />
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {[0, 1, 2, 3].map((i) => (
          <span key={i} className="h-[72px] rounded-inner bg-[#F2F4F7] motion-safe:animate-pulse" />
        ))}
      </div>
      <span className="h-[200px] rounded-inner bg-[#F2F4F7] motion-safe:animate-pulse lg:h-[240px]" />
    </div>
  );
}
