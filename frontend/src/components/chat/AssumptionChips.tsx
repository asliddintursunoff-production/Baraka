/**
 * Advisor assumptions shown as "taxmin" chips (docs/API_ADVISOR.md). An editable chip opens an
 * inline input; submit re-runs the tool directly (POST /api/tools/<tool>, no LLM) and the card
 * swaps in the new `ui_blocks` and `assumptions`.
 */
import { LoaderCircle, Pencil } from "lucide-react";
import { useState, type FormEvent } from "react";

import type { UiBlock } from "@/components/UiBlockRenderer";
import { apiPost, ApiError } from "@/lib/api";
import type { Assumption, ToolRunResult } from "@/lib/chatTypes";
import { cn } from "@/lib/utils";

const FAILED = "Qayta hisoblab bo'lmadi. Qiymatni tekshirib, yana urinib ko'ring.";

export interface Recomputed {
  blocks: UiBlock[];
  assumptions: Assumption[];
}

function errorText(body: unknown): string {
  if (body && typeof body === "object") {
    const r = body as Record<string, unknown>;
    for (const k of ["error", "detail", "message"] as const) {
      const v = r[k];
      if (typeof v === "string" && v.trim()) return v;
    }
  }
  return FAILED;
}

function withIds(raw: unknown): UiBlock[] {
  if (!Array.isArray(raw)) return [];
  return raw
    .filter((b): b is Record<string, unknown> => !!b && typeof b === "object" && typeof (b as { type?: unknown }).type === "string")
    .map((b, i) => ({ ...b, id: typeof b.id === "string" && b.id ? b.id : `r${i}` }) as UiBlock);
}

/** Keep a numeric arg numeric when the new text is a plain number. */
function coerce(prev: unknown, text: string): unknown {
  const t = text.trim();
  if (typeof prev === "number") {
    const n = Number(t);
    if (t !== "" && Number.isFinite(n)) return n;
  }
  return t;
}

export async function rerunAssumption(a: Assumption, value: string): Promise<Recomputed> {
  if (!a.tool || !a.key) throw new Error(FAILED);
  const args = a.args ?? {};
  let res: ToolRunResult;
  try {
    res = await apiPost<ToolRunResult>(`/api/tools/${encodeURIComponent(a.tool)}`, {
      ...args,
      [a.key]: coerce(args[a.key], value),
    });
  } catch (e) {
    throw new Error(e instanceof ApiError ? errorText(e.body) : FAILED, { cause: e });
  }
  if (res.ok === false) throw new Error(errorText(res));
  return { blocks: withIds(res.ui_blocks), assumptions: Array.isArray(res.assumptions) ? res.assumptions : [] };
}

function AssumptionChip({ a, onDone }: { a: Assumption; onDone: (r: Recomputed) => void }) {
  const [open, setOpen] = useState(false);
  const [value, setValue] = useState(a.value ?? "");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const editable = a.editable && !!a.tool && !!a.key;

  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (pending) return;
    setPending(true);
    setError(null);
    rerunAssumption(a, value)
      .then((r) => {
        setOpen(false);
        onDone(r);
      })
      .catch((err: unknown) => setError(err instanceof Error ? err.message : FAILED))
      .finally(() => setPending(false));
  };

  const label = (
    <>
      <span className="text-12 font-bold uppercase tracking-label text-text-4">taxmin</span>
      <span className="text-14 text-text-2">{a.text}</span>
    </>
  );

  return (
    <li className="flex min-w-0 max-w-full flex-col gap-1">
      {!editable ? (
        <span className="inline-flex min-h-tap flex-wrap items-center gap-2 rounded-pill border border-border bg-surface-muted px-[14px]">
          {label}
        </span>
      ) : open ? (
        <form onSubmit={submit} className="flex flex-wrap items-center gap-2 rounded-inner border border-primary-border bg-primary-soft p-2">
          <label className="flex min-w-0 flex-[1_1_180px] flex-col gap-1">
            <span className="px-1 text-13 text-text-3">{a.text}</span>
            <input
              autoFocus
              value={value}
              onChange={(e) => setValue(e.target.value)}
              inputMode="decimal"
              className="min-h-tap w-full rounded-btn border border-border-input bg-surface px-3 text-15 text-ink"
            />
          </label>
          <div className="flex gap-2">
            <button
              type="submit"
              aria-busy={pending || undefined}
              className={cn(
                "inline-flex min-h-tap items-center gap-2 rounded-btn border-0 bg-primary px-4 text-15 font-semibold text-white hover:bg-primary-hover",
                pending && "cursor-wait opacity-80",
              )}
            >
              {pending && <LoaderCircle size={16} className="motion-safe:animate-spin" aria-hidden="true" />}
              Qayta hisoblash
            </button>
            <button
              type="button"
              onClick={() => {
                setOpen(false);
                setError(null);
              }}
              className="min-h-tap rounded-btn border border-border-input bg-surface px-3 text-15 font-semibold text-text-2"
            >
              Bekor qilish
            </button>
          </div>
        </form>
      ) : (
        <button
          type="button"
          onClick={() => {
            setValue(a.value ?? "");
            setError(null);
            setOpen(true);
          }}
          className="inline-flex min-h-tap max-w-full flex-wrap items-center gap-2 rounded-pill border border-dashed border-border-input bg-surface px-[14px] text-left hover:bg-surface-muted"
        >
          {label}
          <Pencil size={14} className="shrink-0 text-text-4" aria-hidden="true" />
        </button>
      )}
      {error && (
        <span role="alert" className="px-1 text-13 font-semibold text-danger">
          {error}
        </span>
      )}
    </li>
  );
}

export function AssumptionChips({
  items,
  onRecomputed,
}: {
  items: Assumption[];
  onRecomputed: (r: Recomputed) => void;
}) {
  if (items.length === 0) return null;
  return (
    <ul className="m-0 flex list-none flex-wrap gap-2 p-0">
      {items.map((a, i) => (
        <AssumptionChip key={`${a.key ?? "t"}-${i}`} a={a} onDone={onRecomputed} />
      ))}
    </ul>
  );
}
