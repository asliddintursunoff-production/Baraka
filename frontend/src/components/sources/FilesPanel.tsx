import type { Proposals, SourceProposal } from "@/lib/sourcesTypes";
import { cn } from "@/lib/utils";

import { PickErrorBox, PickStatus } from "./ConnectSteps";
import { SheetIcon } from "./icons";
import { PrivacyNote } from "./shared";
import { usePickFiles } from "./usePickFiles";

/** Left column of step 3: connected files, "+ Yana fayl qo'shish", privacy note. */
export function FilesPanel({
  sources,
  selectedId,
  onSelect,
  onAdd,
  businessName,
  disabled,
}: {
  sources: SourceProposal[];
  selectedId: number | null;
  onSelect: (sourceId: number) => void;
  onAdd: (p: Proposals) => void;
  businessName: string | null | undefined;
  disabled: boolean;
}) {
  const { phase, error, pick } = usePickFiles(onAdd);
  return (
    <section
      aria-labelledby="files-title"
      className="flex min-w-0 flex-[1_1_300px] flex-col gap-3 rounded-card border border-border bg-surface p-5"
    >
      <h2 id="files-title" className="m-0 font-display text-[18px] font-bold">
        Ulangan fayllar
      </h2>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {sources.map((s) => {
          const selected = s.id === selectedId;
          return (
            <li key={s.id}>
              <button
                type="button"
                aria-pressed={selected}
                onClick={() => onSelect(s.id)}
                className={cn(
                  "flex min-h-tap w-full flex-col gap-[6px] rounded-inner p-3 text-left font-[inherit] text-ink",
                  selected
                    ? "border-2 border-primary bg-primary-soft"
                    : "border border-border bg-surface hover:bg-bg",
                )}
              >
                <span className="flex items-center gap-[10px] text-15 font-semibold">
                  <SheetIcon />
                  <span className="min-w-0 break-words">{s.title}</span>
                </span>
                {s.summary && <span className="pl-[30px] text-13 text-text-3">{s.summary}</span>}
              </button>
            </li>
          );
        })}
      </ul>
      <button
        type="button"
        onClick={() => void pick()}
        disabled={disabled || phase !== "idle"}
        aria-busy={phase !== "idle"}
        className="min-h-tap rounded-btn border border-dashed border-[#98A2B3] bg-surface text-14 font-semibold text-text-2 hover:bg-bg disabled:cursor-not-allowed disabled:opacity-60"
      >
        + Yana fayl qo'shish
      </button>
      <div aria-live="polite">
        <PickStatus phase={phase} />
      </div>
      {error && <PickErrorBox error={error} />}
      <PrivacyNote businessName={businessName} />
    </section>
  );
}
