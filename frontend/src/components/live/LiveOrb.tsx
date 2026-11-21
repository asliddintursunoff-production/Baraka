/** Live voice orb (design/pages/Live.html): pulsing rings + bars only while the AI speaks.
 * Decorative: the status line next to it carries the meaning. */

// Keyframes copied from Live.html. `motion-reduce:animate-none` (and the global rule in
// index.css) keeps everything still for `prefers-reduced-motion`.
const KEYFRAMES = `
@keyframes bpPulse{0%,100%{transform:scale(1);opacity:.55}50%{transform:scale(1.12);opacity:.18}}
@keyframes bpBar{0%,100%{transform:scaleY(.35)}50%{transform:scaleY(1)}}
`;

const RING = "motion-safe:animate-[bpPulse_2.4s_ease-in-out_infinite] motion-reduce:animate-none";
const BAR = "motion-safe:animate-[bpBar_1s_ease-in-out_infinite] motion-reduce:animate-none";

const SPEAKING_BARS = [34, 56, 44, 60, 30];
const QUIET_BARS = [14, 22, 18, 24, 12];

export function LiveOrb({ speaking }: { speaking: boolean }) {
  return (
    <div className="relative flex h-[230px] w-[230px] shrink-0 items-center justify-center" aria-hidden="true">
      <style>{KEYFRAMES}</style>
      {speaking ? (
        <>
          <span className={`absolute inset-0 origin-center rounded-full bg-primary ${RING}`} />
          <span
            className={`absolute inset-[22px] origin-center rounded-full bg-[#2E5BEA] ${RING}`}
            style={{ animationDelay: ".8s" }}
          />
          <span className="relative flex h-[146px] w-[146px] items-center justify-center gap-[6px] rounded-full border-2 border-primary-border bg-primary">
            {SPEAKING_BARS.map((h, i) => (
              <span
                key={i}
                className={`w-[7px] origin-center rounded-[4px] bg-white ${BAR}`}
                style={{ height: h, animationDelay: `${i * 0.15}s` }}
              />
            ))}
          </span>
        </>
      ) : (
        <>
          <span className="absolute inset-[22px] rounded-full bg-[#16244A]" />
          <span className="relative flex h-[146px] w-[146px] items-center justify-center gap-[6px] rounded-full border-2 border-text-2 bg-live-border">
            {QUIET_BARS.map((h, i) => (
              <span key={i} className="w-[7px] rounded-[4px] bg-[#98A2B3]" style={{ height: h }} />
            ))}
          </span>
        </>
      )}
    </div>
  );
}
