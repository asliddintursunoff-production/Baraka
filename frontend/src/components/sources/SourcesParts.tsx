import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useId, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { apiPost } from "@/lib/api";
import type { SourceFileRow, SourceIssue, SourcesPage, SyncLogEntry } from "@/lib/sourcesTypes";
import { cn } from "@/lib/utils";

import { AlertIcon, CheckIcon } from "./icons";
import {
  BTN_PRIMARY,
  BTN_SECONDARY,
  errorText,
  invalidateFinance,
  parseAmount,
  ProgressBar,
  startGoogleAuth,
} from "./shared";
import { useSseRun } from "./useSseRun";

const H2 = "m-0 font-display text-[19px] font-bold";
const SAVE_FAILED = "Saqlab bo'lmadi. Qaytadan urinib ko'ring.";

export function connectHref(connected: boolean): string {
  return connected ? "/onboarding/connect?step=pick" : "/onboarding/connect";
}

export function ReauthBanner() {
  return (
    <section
      aria-label="Google ulanishi"
      className="flex flex-wrap items-center gap-4 rounded-card border border-[#FEDF89] bg-warning-bg px-4 py-[18px] sm:px-[22px]"
    >
      <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-[22px] bg-warning">
        <AlertIcon />
      </span>
      <div className="flex min-w-0 flex-[1_1_300px] flex-col gap-[2px]">
        <span className="text-17 font-bold text-ink">Google ulanishi uzildi</span>
        <span className="text-14 text-text-2">
          Yangi qatorlarni o'qish uchun Google hisobingizni qayta ulang.
        </span>
      </div>
      <button type="button" onClick={() => startGoogleAuth("/sources")} className={BTN_PRIMARY}>
        Qayta ulash
      </button>
    </section>
  );
}

/** Green "Hammasi ishlayapti" card + "Hozir yangilash" (`POST /api/sources/sync`, SSE). */
export function SyncStatusCard({
  data,
  onSynced,
}: {
  data: SourcesPage;
  onSynced: () => Promise<void>;
}) {
  const { state, run } = useSseRun();
  const ok = data.status?.ok ?? !data.needs_reauth;
  const title = data.status?.title ?? "";
  const sub = data.status?.subtitle ?? "";
  const subtitle =
    data.email && !sub.includes(data.email) ? [sub, data.email].filter(Boolean).join(" · ") : sub;
  const running = state.status === "running";

  const sync = async () => {
    const result = await run("/api/sources/sync", {}, "Yangilanmoqda…");
    if (result) await onSynced();
  };

  return (
    <section
      aria-label="Sinxronlash holati"
      className={cn(
        "flex flex-wrap items-center gap-4 rounded-card border px-4 py-[18px] sm:px-[22px]",
        ok ? "border-[#ABEFC6] bg-success-bg" : "border-[#FEDF89] bg-warning-bg",
      )}
    >
      <span
        className={cn(
          "flex h-11 w-11 shrink-0 items-center justify-center rounded-[22px]",
          ok ? "bg-success" : "bg-warning",
        )}
      >
        {ok ? <CheckIcon size={22} strokeWidth={2.6} color="#FFFFFF" /> : <AlertIcon />}
      </span>
      <div className="flex min-w-0 flex-[1_1_300px] flex-col gap-[2px]">
        {title && (
          <span className={cn("text-17 font-bold", ok ? "text-[#054F31]" : "text-ink")}>
            {title}
          </span>
        )}
        {subtitle && (
          <span className={cn("break-words text-14", ok ? "text-[#085D3A]" : "text-text-2")}>
            {subtitle}
          </span>
        )}
        <div aria-live="polite">
          {running && (
            <div className="pt-2">
              <ProgressBar text={state.text} pct={state.pct} label="Yangilash jarayoni" />
            </div>
          )}
          {state.status === "done" && state.text && (
            <span className="block pt-1 text-14 font-semibold text-success">{state.text}</span>
          )}
        </div>
        {state.status === "error" && (
          <div role="alert" className="flex flex-wrap items-center gap-3 pt-1">
            <span className="text-14 font-semibold text-danger">{state.message}</span>
            {state.reauth && (
              <button
                type="button"
                onClick={() => startGoogleAuth("/sources")}
                className={BTN_SECONDARY}
              >
                Qayta ulash
              </button>
            )}
          </div>
        )}
      </div>
      <button
        type="button"
        onClick={() => void sync()}
        disabled={running}
        aria-busy={running}
        className={cn(
          "min-h-tap rounded-btn border bg-surface px-4 font-[inherit] text-14 font-semibold disabled:cursor-not-allowed disabled:opacity-60",
          ok ? "border-[#75E0A7] text-[#085D3A]" : "border-border-input text-text-2",
        )}
      >
        Hozir yangilash
      </button>
    </section>
  );
}

const STATE_TONE: Record<SourceFileRow["state_tone"], string> = {
  new: "text-success",
  same: "text-text-3",
  error: "text-danger",
};

/** "Ustunlarni qayta ko'rish" → `/onboarding/connect?step=map&source={id}`; one link per file when there are several. */
function RemapLinks({ files }: { files: SourceFileRow[] }) {
  const [open, setOpen] = useState(false);
  const listId = useId();
  const sources = [
    ...new Map(files.map((f) => [f.source_id, f.label.split(" › ")[0] || f.label])).entries(),
  ];
  const href = (id: number) => `/onboarding/connect?step=map&source=${id}`;
  const LINK = "inline-flex min-h-tap items-center self-start pt-[10px] text-14 font-semibold";
  if (sources.length === 0) return null;
  if (sources.length === 1) {
    return (
      <Link to={href(sources[0]![0])} className={LINK}>
        Ustunlarni qayta ko'rish
      </Link>
    );
  }
  return (
    <div className="flex flex-col">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={listId}
        onClick={() => setOpen((v) => !v)}
        className={cn(
          LINK,
          "border-0 bg-transparent px-0 pb-0 font-[inherit] text-primary underline hover:text-primary-hover",
        )}
      >
        Ustunlarni qayta ko'rish
      </button>
      {open && (
        <ul id={listId} className="m-0 flex list-none flex-col p-0 pl-3">
          {sources.map(([id, title]) => (
            <li key={id}>
              <Link to={href(id)} className="inline-flex min-h-tap items-center text-14">
                {title}
              </Link>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function FilesTable({ files }: { files: SourceFileRow[] }) {
  return (
    <section
      aria-labelledby="src-files"
      className="flex min-w-0 flex-[999_1_560px] flex-col gap-1 rounded-card border border-border bg-surface px-4 py-5 sm:px-[22px]"
    >
      <h2 id="src-files" className={cn(H2, "mb-2")}>
        Ulangan fayllar
      </h2>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-14">
          <thead>
            <tr className="text-left text-12 uppercase tracking-label text-text-4">
              <th scope="col" className="py-2 pr-3 font-semibold">
                Fayl / varaq
              </th>
              <th scope="col" className="py-2 pr-3 font-semibold">
                AI tanidi
              </th>
              <th scope="col" className="py-2 pr-3 text-right font-semibold">
                Qatorlar
              </th>
              <th scope="col" className="py-2 font-semibold">
                Holat
              </th>
            </tr>
          </thead>
          <tbody>
            {files.map((f, i) => (
              <tr key={`${f.source_id}-${f.label}-${i}`} className="border-t border-border-subtle">
                <td className="py-3 pr-3 font-semibold">{f.label}</td>
                <td className="py-3 pr-3 text-text-3">{f.kind_label}</td>
                <td className="py-3 pr-3 text-right">{f.rows}</td>
                <td className={cn("py-3 font-semibold", STATE_TONE[f.state_tone] ?? "text-text-3")}>
                  {f.state}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <RemapLinks files={files} />
    </section>
  );
}

function IssueItem({ issue, first }: { issue: SourceIssue; first: boolean }) {
  const qc = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);
  const inputId = useId();
  const resolve = useMutation({
    mutationFn: (payload: { action: SourceIssue["action"]; value?: string }) =>
      apiPost<{ ok: boolean }>(`/api/sources/issues/${issue.id}/resolve`, payload),
    onSuccess: async () => {
      setEditing(false);
      invalidateFinance(qc);
      await qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });

  const submitAmount = () => {
    const amount = parseAmount(value);
    setInvalid(!amount);
    if (amount) resolve.mutate({ action: "set_amount", value: amount });
  };

  return (
    <li className={cn("flex flex-col gap-[10px]", !first && "border-t border-border-subtle pt-3")}>
      <span className="text-15 leading-normal">{issue.message}</span>
      {resolve.isSuccess ? (
        <span
          role="status"
          className="inline-flex items-center gap-[6px] text-14 font-semibold text-success"
        >
          <CheckIcon strokeWidth={2.5} />
          Saqlandi
        </span>
      ) : editing ? (
        <form
          className="flex flex-wrap items-end gap-2"
          onSubmit={(e) => {
            e.preventDefault();
            submitAmount();
          }}
        >
          <label
            htmlFor={inputId}
            className="flex min-w-0 flex-[1_1_160px] flex-col gap-1 text-13 font-semibold text-text-3"
          >
            Summa (so'm)
            <input
              id={inputId}
              autoFocus
              required
              inputMode="decimal"
              autoComplete="off"
              value={value}
              aria-invalid={invalid || undefined}
              onChange={(e) => setValue(e.target.value)}
              className="min-h-tap rounded-btn border border-border-input bg-surface px-3 font-[inherit] text-15 font-normal text-ink"
            />
          </label>
          <button type="submit" disabled={resolve.isPending} className={BTN_PRIMARY}>
            Saqlash
          </button>
          <button type="button" onClick={() => setEditing(false)} className={BTN_SECONDARY}>
            Bekor qilish
          </button>
        </form>
      ) : (
        <button
          type="button"
          disabled={resolve.isPending}
          aria-busy={resolve.isPending}
          onClick={() =>
            issue.action === "set_amount"
              ? setEditing(true)
              : resolve.mutate({ action: issue.action })
          }
          className={cn(BTN_SECONDARY, "self-start")}
        >
          {issue.action_label}
        </button>
      )}
      {invalid && editing && (
        <p role="alert" className="m-0 text-14 text-danger">
          Summani faqat raqamlarda yozing.
        </p>
      )}
      {resolve.isError && (
        <p role="alert" className="m-0 text-14 text-danger">
          {errorText(resolve.error, SAVE_FAILED)}
        </p>
      )}
    </li>
  );
}

export function IssuesList({ issues }: { issues: SourceIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <section
      aria-labelledby="src-issues"
      className="flex flex-col gap-[10px] rounded-card border border-[#FEDF89] bg-surface p-5"
    >
      <h2 id="src-issues" className={H2}>
        Tekshirish kerak · {issues.length}
      </h2>
      <ul className="m-0 flex list-none flex-col gap-3 p-0">
        {issues.map((it, i) => (
          <IssueItem key={it.id} issue={it} first={i === 0} />
        ))}
      </ul>
    </section>
  );
}

const LOG_TONE: Record<NonNullable<SyncLogEntry["tone"]>, string> = {
  success: "font-semibold text-success",
  info: "font-semibold text-primary",
  muted: "text-text-3",
  error: "font-semibold text-danger",
};

export function SyncLog({ log }: { log: SyncLogEntry[] }) {
  if (log.length === 0) return null;
  return (
    <section
      aria-labelledby="src-log"
      className="flex flex-col gap-1 rounded-card border border-border bg-surface p-5"
    >
      <h2 id="src-log" className={cn(H2, "mb-2")}>
        Oxirgi yangilanishlar
      </h2>
      <ul className="m-0 flex list-none flex-col p-0">
        {log.map((e, i) => (
          <li
            key={`${e.when}-${i}`}
            className="flex justify-between gap-[10px] border-t border-border-subtle py-[10px] text-14"
          >
            <span className="shrink-0">{e.when}</span>
            <span
              className={cn("min-w-0 text-right", LOG_TONE[e.tone ?? "muted"] ?? LOG_TONE.muted)}
            >
              {e.text}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}

/** "Google'dan uzish" with a small inline confirm. */
export function DisconnectGoogle({ email }: { email: string | null }) {
  const qc = useQueryClient();
  const [asking, setAsking] = useState(false);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const disconnect = useMutation({
    mutationFn: () => apiPost<{ ok: boolean }>("/api/integrations/google/disconnect", {}),
    onSuccess: async () => {
      setAsking(false);
      invalidateFinance(qc);
      void qc.invalidateQueries({ queryKey: ["google-status"] });
      await qc.invalidateQueries({ queryKey: ["sources"] });
    },
  });
  const cancel = () => {
    setAsking(false);
    triggerRef.current?.focus();
  };
  return (
    <div className="flex flex-col gap-3">
      <button
        ref={triggerRef}
        type="button"
        aria-expanded={asking}
        aria-controls={panelId}
        onClick={() => setAsking((v) => !v)}
        className={cn(BTN_SECONDARY, "self-start text-danger hover:text-danger")}
      >
        Google'dan uzish
      </button>
      {asking && (
        <div
          id={panelId}
          role="group"
          aria-label="Google'dan uzishni tasdiqlash"
          className="flex max-w-[560px] flex-col gap-3 rounded-inner bg-danger-bg p-[14px]"
        >
          <p className="m-0 text-15 leading-normal text-ink">
            Google hisobi{email ? ` (${email})` : ""} uziladi va yangi qatorlar endi kelmaydi.
            Uzasizmi?
          </p>
          <div className="flex flex-wrap gap-2">
            <button
              type="button"
              disabled={disconnect.isPending}
              aria-busy={disconnect.isPending}
              onClick={() => disconnect.mutate()}
              className="inline-flex min-h-tap items-center rounded-btn border-0 bg-danger px-[18px] font-[inherit] text-15 font-semibold text-white hover:bg-danger-strong disabled:opacity-60"
            >
              Ha, uzish
            </button>
            <button type="button" onClick={cancel} className={BTN_SECONDARY}>
              Bekor qilish
            </button>
          </div>
          {disconnect.isError && (
            <p role="alert" className="m-0 text-14 text-danger">
              {errorText(disconnect.error, "Uzib bo'lmadi. Qaytadan urinib ko'ring.")}
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export function SourcesEmpty({ connected }: { connected: boolean }) {
  return (
    <section
      aria-labelledby="src-empty"
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6"
    >
      <h2 id="src-empty" className="m-0 font-display text-20 font-bold">
        Jadvalingizni ulang
      </h2>
      <p className="m-0 text-15 text-text-3">
        Google Sheets jadvalingizni bir marta ulang — keyin prognoz o'zi yangilanib boradi.
      </p>
      <Link to={connectHref(connected)} className={cn(BTN_PRIMARY, "self-start")}>
        + Yangi fayl ulash
      </Link>
    </section>
  );
}
