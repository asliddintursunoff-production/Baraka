/** Live captions (design/pages/Live.html): the user's last utterance, then the AI caption.
 * Received AI words are white; the word still arriving and an older answer are grey. */

export interface AiCaption {
  text: string;
  /** The model finished this turn (every word is final). */
  final: boolean;
  /** The user has spoken since: this answer is history. */
  old: boolean;
}

const SPOKEN = "text-white";
const PENDING = "text-[#667085]";

function captionParts(c: AiCaption): { text: string; on: boolean }[] {
  const tokens = c.text.split(/(\s+)/).filter(Boolean);
  // While the turn is still streaming, the last fragment may be a partial word.
  const lastWordIdx = !c.final && !/\s$/.test(c.text) ? tokens.length - 1 : -1;
  return tokens.map((t, i) => ({ text: t, on: !c.old && i !== lastWordIdx }));
}

export function LiveCaptions({ user, ai }: { user: string; ai: AiCaption | null }) {
  return (
    // Always mounted, so screen readers pick up the first caption too.
    <div className="flex w-full max-w-[600px] flex-col gap-4" aria-live="polite">
      {user && (
        <div className="flex flex-col gap-1">
          <span className="text-12 font-bold tracking-[0.06em] text-[#98A2B3]">SIZ</span>
          <span className="text-17 leading-normal text-[#D0D5DD] [overflow-wrap:anywhere]">{user}</span>
        </div>
      )}
      {ai && ai.text.trim() && (
        <div className="flex flex-col gap-[6px] rounded-card border border-live-border bg-live-surface px-5 py-[18px]">
          <span className="text-12 font-bold tracking-[0.06em] text-primary-border">AI CFO</span>
          <p className="m-0 text-22 font-medium leading-normal [overflow-wrap:anywhere]">
            {captionParts(ai).map((p, i) => (
              <span key={i} className={p.on ? SPOKEN : PENDING}>
                {p.text}
              </span>
            ))}
          </p>
        </div>
      )}
    </div>
  );
}
