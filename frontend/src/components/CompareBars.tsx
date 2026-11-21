import { toMln } from "@/lib/format";
import { cn } from "@/lib/utils";

export interface CompareRow {
  label: string;
  value: string;
  display: string;
  status: "ok" | "bad" | "warn";
  status_text: string;
}

const COLOR = { ok: "#067647", bad: "#B42318", warn: "#B54708" } as const;

/** Diverging horizontal bars around a zero line, value + "Yetadi/Yetmaydi" (DESIGN.md). */
export function CompareBars({ title, rows, dark = false }: { title: string; rows: CompareRow[]; dark?: boolean }) {
  const values = rows.map((r) => toMln(r.value));
  const maxNeg = Math.max(0, ...values.map((v) => -v));
  const maxPos = Math.max(0, ...values);
  const negShare = maxNeg > 0 ? (maxPos > 0 ? 25 : 100) : 0;
  return (
    <div
      className={cn(
        "flex flex-col gap-[14px] rounded-inner border p-[18px]",
        dark ? "border-live-border bg-live-surface" : "border-border-subtle bg-surface-muted",
      )}
    >
      <span className={cn("text-14 font-bold", dark ? "text-[#D0D5DD]" : "text-text-2")}>{title}</span>
      {rows.map((r, i) => {
        const v = values[i] ?? 0;
        const color = COLOR[r.status];
        return (
          <div key={i} className="flex flex-wrap items-center gap-3">
            <span className={cn("flex-[0_0_170px] text-15 font-semibold", dark && "text-white")}>{r.label}</span>
            <div className="flex h-[30px] flex-[1_1_240px]" aria-hidden="true">
              {negShare > 0 && (
                <div
                  className={cn("flex justify-end", negShare < 100 && "border-r-2", dark ? "border-[#98A2B3]" : "border-text-2")}
                  style={{ width: `${negShare}%` }}
                >
                  {v < 0 && (
                    <div
                      className="rounded-l-md"
                      style={{ width: `${(-v / maxNeg) * 94}%`, background: color }}
                    />
                  )}
                </div>
              )}
              {negShare < 100 && (
                <div
                  className={cn("flex", negShare === 0 && "border-l-2", dark ? "border-[#98A2B3]" : "border-text-2")}
                  style={{ width: `${100 - negShare}%` }}
                >
                  {v > 0 && (
                    <div className="rounded-r-md" style={{ width: `${(v / maxPos) * 94}%`, background: color }} />
                  )}
                </div>
              )}
            </div>
            <span className="flex flex-[0_0_150px] flex-col items-end">
              <strong className="text-17" style={{ color }}>
                {r.display}
              </strong>
              <span className="text-13 font-semibold" style={{ color }}>
                {r.status_text}
              </span>
            </span>
          </div>
        );
      })}
    </div>
  );
}
