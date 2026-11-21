import type { QueryClient } from "@tanstack/react-query";
import { LoaderCircle } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { PickerLoadError } from "@/lib/googlePicker";
import type { Proposals, SourcesErrorBody } from "@/lib/sourcesTypes";
import { cn } from "@/lib/utils";

import { LockIcon } from "./icons";

export const PICK_NEXT = "/onboarding/connect?step=pick";
export const OFFLINE_TEXT = "Internet aloqasini tekshiring va qaytadan urinib ko'ring.";
export const STREAM_FAILED =
  "Jarayon yakunlanmadi. Internet aloqasini tekshirib, qaytadan urinib ko'ring.";

/** Full-page navigation into the OAuth flow (not fetch: Google needs the top-level window). */
export function startGoogleAuth(next: string): void {
  window.location.assign(`/api/integrations/google/start?next=${encodeURIComponent(next)}`);
}

export function errorBody(e: unknown): SourcesErrorBody | null {
  if (!(e instanceof ApiError) || !e.body || typeof e.body !== "object") return null;
  return e.body as SourcesErrorBody;
}

export function isReauth(e: unknown): boolean {
  return errorBody(e)?.error === "reauth_required";
}

/** Uzbek text for a failed request: the server's message when there is one. */
export function errorText(e: unknown, fallback: string): string {
  if (e instanceof PickerLoadError) return "Google oynasini ochib bo'lmadi. " + OFFLINE_TEXT;
  if (!(e instanceof ApiError)) return OFFLINE_TEXT;
  return errorBody(e)?.message || fallback;
}

/** Data that depends on synced rows. */
export function invalidateFinance(qc: QueryClient): void {
  for (const key of ["dashboard", "forecast", "calendar"])
    void qc.invalidateQueries({ queryKey: [key] });
}

const AMOUNT_RE = /^\d+(?:[.,]\d{1,2})?$/;

/** "48 200 000" → "48200000" (so'm, a string for Decimal); null when it is not a plain amount. */
export function parseAmount(raw: string): string | null {
  const compact = raw.replace(/[\s']/g, "");
  if (!AMOUNT_RE.test(compact)) return null;
  return compact.replace(",", ".");
}

/** Today's date (Asia/Tashkent) as `YYYY-MM-DD`. */
export function todayIso(): string {
  return new Intl.DateTimeFormat("en-CA", {
    timeZone: "Asia/Tashkent",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).format(new Date());
}

/** Only same-origin paths are followed. */
export function safePath(path: unknown, fallback: string): string {
  return typeof path === "string" && path.startsWith("/") && !path.startsWith("//")
    ? path
    : fallback;
}

export function normalizeProposals(p: Partial<Proposals> | null | undefined): Proposals {
  return {
    sources: (p?.sources ?? []).map((s) => ({
      ...s,
      sheets: (s.sheets ?? []).map((sh) => ({ ...sh, columns: sh.columns ?? [] })),
    })),
    field_options: p?.field_options ?? [],
    kind_options: p?.kind_options ?? [],
    issues_preview: p?.issues_preview ?? [],
    needs_opening_balance: Boolean(p?.needs_opening_balance),
    opening_balance_hint: p?.opening_balance_hint ?? null,
  };
}

function unionOptions<T extends { value: string }>(a: T[], b: T[]): T[] {
  const next = new Map(b.map((o) => [o.value, o]));
  const merged = a.map((o) => next.get(o.value) ?? o);
  const seen = new Set(a.map((o) => o.value));
  return [...merged, ...b.filter((o) => !seen.has(o.value))];
}

/** "+ Yana fayl qo'shish": new proposals are merged in; a re-picked source replaces the old one in place. */
export function mergeProposals(prev: Proposals | null, raw: Proposals): Proposals {
  const next = normalizeProposals(raw);
  if (!prev) return next;
  const byId = new Map(next.sources.map((s) => [s.id, s]));
  const prevIds = new Set(prev.sources.map((s) => s.id));
  return {
    sources: [
      ...prev.sources.map((s) => byId.get(s.id) ?? s),
      ...next.sources.filter((s) => !prevIds.has(s.id)),
    ],
    field_options: unionOptions(prev.field_options, next.field_options),
    kind_options: unionOptions(prev.kind_options, next.kind_options),
    issues_preview: [
      ...prev.issues_preview.filter((i) => !byId.has(i.source_id)),
      ...next.issues_preview,
    ],
    needs_opening_balance: prev.needs_opening_balance || next.needs_opening_balance,
    opening_balance_hint: next.opening_balance_hint ?? prev.opening_balance_hint,
  };
}

export function Spinner({ size = 18 }: { size?: number }) {
  return (
    <LoaderCircle size={size} className="shrink-0 motion-safe:animate-spin" aria-hidden="true" />
  );
}

export function PrivacyNote({ businessName }: { businessName: string | null | undefined }) {
  return (
    <div className="flex gap-[10px] rounded-btn bg-bg p-3 text-13 leading-[1.5] text-text-3">
      <LockIcon />
      <span>
        Faqat o'qish huquqi. Ma'lumotlaringiz faqat{" "}
        {businessName ? `${businessName} hisobida` : "sizning hisobingizda"} saqlanadi va boshqa
        bizneslarga hech qachon ko'rinmaydi.
      </span>
    </div>
  );
}

/** Progress text + bar from SSE `progress` events. Render it inside an always-mounted `aria-live` region. */
export function ProgressBar({
  text,
  pct,
  label,
}: {
  text: string;
  pct: number | null;
  label: string;
}) {
  const value = pct == null ? null : Math.max(0, Math.min(100, Math.round(pct)));
  return (
    <div className="flex flex-col gap-2">
      <span className="flex items-center gap-2 text-14 font-semibold text-text-2">
        <Spinner size={16} />
        {text}
      </span>
      <div
        role="progressbar"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={value ?? undefined}
        className="h-2 w-full overflow-hidden rounded-pill bg-border-subtle"
      >
        <div
          className={cn(
            "h-full rounded-pill bg-primary transition-[width] duration-300 motion-reduce:transition-none",
            value == null && "w-1/5 motion-safe:animate-pulse",
          )}
          style={value == null ? undefined : { width: `${value}%` }}
        />
      </div>
    </div>
  );
}

export function ErrorBox({ children, action }: { children: ReactNode; action?: ReactNode }) {
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-inner bg-danger-bg p-[14px]">
      <p className="m-0 text-15 leading-normal text-danger">{children}</p>
      {action}
    </div>
  );
}

export const BTN_PRIMARY =
  "inline-flex min-h-tap items-center justify-center gap-2 rounded-btn border-0 bg-primary px-[18px] text-15 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white disabled:cursor-not-allowed disabled:opacity-60";
export const BTN_SECONDARY =
  "inline-flex min-h-tap items-center justify-center gap-2 rounded-btn border border-border-input bg-surface px-4 text-14 font-semibold text-text-2 no-underline hover:bg-bg hover:text-ink disabled:cursor-not-allowed disabled:opacity-60";
