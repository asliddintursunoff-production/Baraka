import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation } from "react-router-dom";

import { ConnectLayout } from "@/components/sources/ConnectLayout";
import { CheckIcon } from "@/components/sources/icons";
import { BTN_PRIMARY, ErrorBox, errorText, invalidateFinance, Spinner, STREAM_FAILED } from "@/components/sources/shared";
import { apiGet } from "@/lib/api";
import { useMe } from "@/lib/auth";
import type { ConfirmBody, SourcesStreamEvents } from "@/lib/sourcesTypes";
import { postSse } from "@/lib/sse";
import type { Dashboard } from "@/lib/types";

type Phase = "running" | "done" | "error";

/** Step 4 "Birinchi tahlil": the first sync over SSE, then the first AI insight (FirstSync.html). */
/** Already onboarded and nothing to confirm: never start a sync just by opening the URL. */
export default function FirstSyncPage() {
  const confirm = (useLocation().state as { confirm?: ConfirmBody } | null)?.confirm ?? null;
  const me = useMe();
  if (!confirm && me.isLoading) return null;
  if (!confirm && me.data?.onboarding_step === "done") return <Navigate to="/dashboard" replace />;
  return <FirstSyncRun confirm={confirm} />;
}

function FirstSyncRun({ confirm }: { confirm: ConfirmBody | null }) {
  const qc = useQueryClient();
  const [phase, setPhase] = useState<Phase>("running");
  const [steps, setSteps] = useState<string[]>([]);
  const [pct, setPct] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const confirmRef = useRef(confirm);

  const start = useCallback(
    (signal: AbortSignal) => {
      const body = confirmRef.current;
      setPhase("running");
      setError(null);
      setSteps([]);
      setPct(0);
      let finished = false;
      postSse<SourcesStreamEvents>(
        body ? "/api/sources/confirm" : "/api/sources/sync",
        body ?? {},
        {
          progress: (d) => {
            const text = d?.text;
            if (text) setSteps((prev) => (prev[prev.length - 1] === text ? prev : [...prev, text]));
            if (typeof d?.pct === "number" && Number.isFinite(d.pct)) setPct(Math.max(0, Math.min(100, d.pct)));
          },
          done: () => {
            finished = true;
            // A reload must not re-send the confirm body: the mapping is saved now.
            confirmRef.current = null;
            setPct(100);
            setPhase("done");
            invalidateFinance(qc);
            void qc.invalidateQueries({ queryKey: ["me"] });
            void qc.invalidateQueries({ queryKey: ["sources"] });
          },
          error: (d) => {
            finished = true;
            setError(d?.message || STREAM_FAILED);
            setPhase("error");
          },
        },
        signal,
      )
        .then(() => {
          if (!finished) {
            setError(STREAM_FAILED);
            setPhase("error");
          }
        })
        .catch((e: unknown) => {
          if (signal.aborted) return;
          setError(errorText(e, STREAM_FAILED));
          setPhase("error");
        });
    },
    [qc],
  );

  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    const ctrl = new AbortController();
    // Deferred so StrictMode's mount/unmount/mount does not send the request twice.
    const t = window.setTimeout(() => start(ctrl.signal), 0);
    return () => {
      window.clearTimeout(t);
      ctrl.abort();
    };
  }, [start, attempt]);

  const dash = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => apiGet<Dashboard>("/api/dashboard"),
    enabled: phase === "done",
    retry: false,
  });
  const banner = dash.data?.banner;
  const finished = phase === "done";

  return (
    <ConnectLayout step={4} finished={finished} mainClassName="max-w-[760px] gap-6 py-12">
      <div className="flex flex-col gap-2 text-center">
        <h1 className="m-0 font-display text-30 font-bold">
          {finished ? "Tayyor!" : "AI jadvallaringizni o'rganyapti"}
        </h1>
        <span className="text-16 text-text-3">
          {finished
            ? "Endi AI biznesingizni har 15 daqiqada kuzatib boradi."
            : "Odatda 1 daqiqadan kam vaqt oladi."}
        </span>
      </div>

      <div
        role="progressbar"
        aria-label="Tahlil jarayoni"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(pct)}
        className="h-[10px] overflow-hidden rounded-[5px] bg-border"
      >
        <div
          className="h-full rounded-[5px] bg-primary transition-[width] duration-300"
          style={{ width: `${Math.round(pct)}%` }}
        />
      </div>

      <ol
        aria-live="polite"
        className="m-0 list-none overflow-hidden rounded-card border border-border bg-surface p-0"
      >
        {steps.length === 0 && phase === "running" && (
          <li className="flex items-center gap-[14px] border-b border-border-subtle px-5 py-4 text-primary">
            <span className="flex h-7 w-7 shrink-0 items-center justify-center">
              <Spinner size={22} />
            </span>
            <span className="grow text-16 font-bold">Tahlil boshlanmoqda…</span>
          </li>
        )}
        {steps.map((label, i) => {
          const active = phase === "running" && i === steps.length - 1;
          return (
            <li key={`${i}-${label}`} className="flex items-center gap-[14px] border-b border-border-subtle px-5 py-4">
              {active ? (
                <>
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center text-primary">
                    <Spinner size={22} />
                  </span>
                  <span className="grow text-16 font-bold text-primary">{label}</span>
                </>
              ) : (
                <>
                  <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-[14px] bg-success-bg">
                    <CheckIcon size={16} color="#067647" />
                  </span>
                  <span className="grow text-16 font-semibold">{label}</span>
                </>
              )}
            </li>
          );
        })}
      </ol>

      {phase === "error" && (
        <ErrorBox
          action={
            <button type="button" className={`${BTN_PRIMARY} self-start`} onClick={() => setAttempt((n) => n + 1)}>
              Qayta urinish
            </button>
          }
        >
          {error}
        </ErrorBox>
      )}

      {finished && (
        <section aria-label="Birinchi xulosa" className="flex flex-col gap-[10px] rounded-card bg-ink px-6 py-[22px] text-white">
          <span className="text-13 font-bold tracking-label text-[#B2CCFF]">AI'NING BIRINCHI XULOSASI</span>
          {banner ? (
            <>
              <span className="font-display text-22 font-bold leading-[1.3]">{banner.headline}</span>
              <span className="text-15 leading-[1.5] text-border-input">
                {[banner.reason, banner.instruction].filter(Boolean).join(" ")}
              </span>
            </>
          ) : dash.isPending ? (
            <span className="flex items-center gap-2 text-15 text-border-input">
              <Spinner size={16} />
              Yuklanmoqda…
            </span>
          ) : null}
          <div className="flex flex-wrap gap-[10px] pt-[6px]">
            <Link
              to="/dashboard"
              className="inline-flex min-h-[46px] items-center rounded-btn bg-surface px-5 text-15 font-bold text-ink no-underline hover:text-ink"
            >
              Bosh sahifaga o'tish
            </Link>
            <Link
              to="/chat"
              className="inline-flex min-h-[46px] items-center rounded-btn border border-text-3 px-5 text-15 font-semibold text-white no-underline hover:text-white"
            >
              AI'dan savol so'rash
            </Link>
          </div>
        </section>
      )}
    </ConnectLayout>
  );
}
