import { CircleAlert } from "lucide-react";

import { Markdown } from "@/components/Markdown";
import { UiBlockRenderer, type UiBlock } from "@/components/UiBlockRenderer";
import { cn } from "@/lib/utils";

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
  const wide = cards.length > 0 || text.length > 0;
  return (
    <div
      className={cn(
        "flex min-w-0 flex-col gap-4 rounded-[4px_16px_16px_16px] border border-border bg-surface [overflow-wrap:anywhere]",
        wide ? "w-full p-[22px]" : "max-w-[620px] self-start px-4 py-[14px]",
      )}
    >
      {text && <Markdown text={text} />}
      {pending && !error && (
        <span className="inline-flex items-center gap-[10px] text-14 font-semibold text-text-3">
          <Dots />
          {!text && status}
        </span>
      )}
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
