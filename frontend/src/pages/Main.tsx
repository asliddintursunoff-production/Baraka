import { useQuery } from "@tanstack/react-query";
import { Check, Lightbulb, Mic, RefreshCw, Sparkles, TriangleAlert, Users, X } from "lucide-react";
import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";

import { ActionSteps } from "@/components/ActionSteps";
import { AlertsBell } from "@/components/AlertsBell";
import { AppShell } from "@/components/AppShell";
import { KpiCard } from "@/components/KpiCard";
import { TwoPanelChart } from "@/components/TwoPanelChart";
import { EmptyState, ErrorState, InsufficientData, PageSkeleton, Skeleton } from "@/components/States";
import { apiGet } from "@/lib/api";
import type { ForecastRange } from "@/lib/twoPanel";
import type { Dashboard, Verdict } from "@/lib/types";
import { cn } from "@/lib/utils";

const MonthlyBars = lazy(() => import("@/components/MonthlyBars"));

export const CHIP: Record<Verdict, { cls: string; Icon: typeof Check }> = {
  yes: { cls: "bg-success-bg text-success", Icon: Check },
  risky: { cls: "bg-warning-bg text-warning", Icon: TriangleAlert },
  no: { cls: "bg-danger-bg text-danger", Icon: X },
};

const PRIORITY_PILL = {
  critical: "bg-danger-bg text-danger",
  deferrable: "bg-[#F2F4F7] text-text-2",
  discretionary: "bg-[#F2F4F7] text-text-2",
} as const;

function dismissKey(day: string) {
  return `advice-dismissed:${day}`;
}

function readDismissed(day: string): boolean {
  try {
    return localStorage.getItem(dismissKey(day)) === "1";
  } catch {
    return false;
  }
}

export default function MainPage() {
  const q = useQuery({ queryKey: ["dashboard"], queryFn: () => apiGet<Dashboard>("/api/dashboard") });
  const [horizon, setHorizon] = useState<ForecastRange>(60);
  const [dismissed, setDismissed] = useState<string | null>(null);

  if (q.isPending) {
    return (
      <AppShell active="main">
        <PageSkeleton />
      </AppShell>
    );
  }
  if (q.isError) {
    return (
      <AppShell active="main">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </AppShell>
    );
  }
  const d = q.data;
  const summary = d.forecast.summaries[String(horizon)]!;
  const chip = summary.verdict ? CHIP[summary.verdict] : null;
  const bannerHidden = dismissed === d.today.iso || readDismissed(d.today.iso);

  return (
    <AppShell active="main">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div className="flex flex-col gap-1">
          <h1 className="m-0 font-display text-30 font-bold">Xayrli kun, {d.user.first_name}</h1>
          <span className="text-15 text-text-3">
            {d.today.label} · Barcha raqamlar Financial Engine tomonidan hisoblangan
          </span>
          {d.freshness?.text && (
            <span className="self-start rounded-pill bg-warning-bg px-3 py-1 text-13 font-semibold text-warning">
              {d.freshness.text}. Kiritilmagan kunlar taxmin bilan to&apos;ldirildi.
            </span>
          )}
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <Link
            to={d.sync.connected ? "/sources" : "/onboarding/connect"}
            className={cn(
              "inline-flex min-h-10 items-center gap-2 rounded-pill px-[14px] text-14 font-semibold no-underline",
              d.sync.ok ? "bg-success-bg text-success hover:text-success" : "bg-warning-bg text-warning hover:text-warning",
            )}
          >
            <RefreshCw size={16} strokeWidth={2.2} aria-hidden="true" />
            {d.sync.label}
          </Link>
          <AlertsBell count={d.alerts.new} />
        </div>
      </header>

      {!d.has_cash && <EmptyState />}

      {!bannerHidden && (
        <section aria-label="AI xulosasi" className="flex flex-wrap items-center gap-5 rounded-card bg-ink px-6 py-[22px] text-white">
          <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded-inner bg-primary">
            <Sparkles size={24} color="#FFFFFF" aria-hidden="true" />
          </div>
          <div className="flex flex-[1_1_420px] flex-col gap-[6px]">
            <span className="text-13 font-semibold uppercase tracking-label text-[#B2CCFF]">{d.banner.label}</span>
            <p className="m-0 font-display text-22 font-bold leading-[1.3]">{d.banner.headline}</p>
            <p className="m-0 text-16 leading-normal text-[#D0D5DD]">
              {d.banner.reason} <strong className="text-white">{d.banner.instruction}</strong>
            </p>
            {d.banner.beyond && <p className="m-0 text-14 leading-normal text-[#FEC84B]">{d.banner.beyond}</p>}
          </div>
          <div className="flex flex-wrap gap-[10px]">
            <Link
              to="/chat"
              className="inline-flex min-h-tap items-center rounded-btn bg-white px-[18px] text-15 font-semibold text-ink no-underline hover:text-ink"
            >
              AI bilan muhokama
            </Link>
            <button
              type="button"
              onClick={() => {
                try {
                  localStorage.setItem(dismissKey(d.today.iso), "1");
                } catch {
                  /* private mode: only hide for this view */
                }
                setDismissed(d.today.iso);
              }}
              className="min-h-tap rounded-btn border border-text-3 bg-transparent px-[18px] text-15 font-semibold text-white"
            >
              Tushunarli
            </button>
          </div>
        </section>
      )}

      <section aria-label="Asosiy ko'rsatkichlar" className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        {d.kpis.map((k) => (
          <KpiCard key={k.id} kpi={k} />
        ))}
      </section>

      <div className="flex flex-wrap items-stretch gap-5">
        <section
          aria-label="Kassa prognozi"
          className="flex min-w-0 flex-[999_1_560px] flex-col gap-[14px] rounded-card border border-border bg-surface px-6 py-[22px]"
        >
          <div className="flex flex-wrap items-center gap-[10px]">
            <h2 className="m-0 font-display text-20 font-bold">{summary.title}</h2>
            {chip && (
              <span className={cn("inline-flex items-center gap-[6px] rounded-pill px-[10px] py-1 text-13 font-bold", chip.cls)}>
                <chip.Icon size={14} strokeWidth={2.8} aria-hidden="true" />
                {summary.chip}
              </span>
            )}
            <Link to="/forecast" className="ml-auto text-14 font-semibold">
              Batafsil prognoz
            </Link>
          </div>
          {d.forecast.insufficient_data ? (
            <InsufficientData />
          ) : (
            <TwoPanelChart forecast={d.forecast} days={horizon} onDaysChange={setHorizon} />
          )}
        </section>

        <section
          aria-label="Ogohlantirishlar"
          className="flex min-w-0 flex-[1_1_320px] flex-col gap-[14px] rounded-card border border-border bg-surface px-5 py-[22px]"
        >
          <h2 className="m-0 font-display text-20 font-bold">Nima qilish kerak</h2>
          {d.steps.length ? <ActionSteps items={d.steps} /> : <InsufficientData />}
          {d.news.length > 0 && (
            <span className="pt-[6px] text-12 font-bold uppercase tracking-label text-text-4">AI yangiliklari</span>
          )}
          {d.news.map((n) => (
            <article
              key={n.kind}
              className={cn("flex gap-3 rounded-inner p-[14px]", n.kind === "learned" ? "bg-primary-soft" : "bg-bg")}
            >
              {n.kind === "learned" ? (
                <Lightbulb size={22} color="#1D4ED8" className="shrink-0" aria-hidden="true" />
              ) : (
                <Users size={22} color="#475467" className="shrink-0" aria-hidden="true" />
              )}
              <div className="flex flex-col gap-1">
                <span
                  className={cn(
                    "text-12 font-bold uppercase tracking-label",
                    n.kind === "learned" ? "text-primary" : "text-text-3",
                  )}
                >
                  {n.label}
                </span>
                <span className="text-14 leading-[1.45]">{n.text}</span>
              </div>
            </article>
          ))}
        </section>
      </div>

      <div className="flex flex-wrap items-stretch gap-5">
        <section
          aria-label="Kelgusi to'lovlar"
          className="flex min-w-0 flex-[1_1_420px] flex-col gap-3 rounded-card border border-border bg-surface px-6 py-[22px]"
        >
          <div className="flex items-center justify-between">
            <h2 className="m-0 font-display text-20 font-bold">Kelgusi to'lovlar · 30 kun</h2>
            <Link to="/calendar" className="text-14 font-semibold">
              Kalendar
            </Link>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] border-collapse text-14">
              <thead>
                <tr className="text-left text-12 uppercase tracking-label text-text-4">
                  <th className="py-2 font-semibold">Sana</th>
                  <th className="py-2 font-semibold">To'lov</th>
                  <th className="py-2 font-semibold">Turi</th>
                  <th className="py-2 text-right font-semibold">Summa</th>
                </tr>
              </thead>
              <tbody>
                {d.upcoming.rows.map((r, i) => (
                  <tr key={i} className="border-t border-border-subtle">
                    <td className="py-3 font-semibold">{r.date_label}</td>
                    <td className="py-3">{r.title}</td>
                    <td className="py-3">
                      <span className={cn("rounded-pill px-[9px] py-[3px] text-12 font-semibold", PRIORITY_PILL[r.priority])}>
                        {r.priority_label}
                      </span>
                    </td>
                    <td className="py-3 text-right font-semibold">{r.amount_display}</td>
                  </tr>
                ))}
                <tr className="border-t-2 border-border-input">
                  <td className="py-3 font-bold" colSpan={3}>
                    Jami
                  </td>
                  <td className="py-3 text-right font-bold">{d.upcoming.total_display}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </section>

        <section
          aria-label="Tushum va xarajat"
          className="flex min-w-0 flex-[1_1_420px] flex-col gap-3 rounded-card border border-border bg-surface px-6 py-[22px]"
        >
          <div className="flex flex-wrap items-center justify-between gap-2">
            <h2 className="m-0 font-display text-20 font-bold">Tushum va xarajat</h2>
            <div className="flex gap-[14px] text-13 text-text-3">
              <span className="inline-flex items-center gap-[6px]">
                <span className="h-3 w-3 rounded-[3px] bg-primary" />
                Tushum
              </span>
              <span className="inline-flex items-center gap-[6px]">
                <span className="h-3 w-3 rounded-[3px] bg-warning-accent" />
                Xarajat
              </span>
            </div>
          </div>
          <Suspense fallback={<Skeleton className="h-48" />}>
            <MonthlyBars months={d.monthly} />
          </Suspense>
          <span className="text-13 text-text-4">
            Ustidagi raqam — oylik sof foyda, mln so'm. Foyda bor, lekin to'lov sanalari bir-biriga to'g'ri kelgani
            uchun kassa tushib ketadi.
          </span>
        </section>
      </div>

      <Link
        to="/live"
        aria-label="AI CFO bilan jonli gaplashish"
        className="fixed bottom-[calc(theme(spacing.tabbar)+env(safe-area-inset-bottom)+12px)] right-4 z-20 inline-flex md:bottom-7 md:right-7 min-h-14 items-center gap-[10px] rounded-pill bg-primary pl-[18px] pr-[22px] text-15 font-semibold text-white no-underline shadow-[0_8px_24px_rgba(29,78,216,.35)] hover:bg-primary-hover hover:text-white"
      >
        <Mic size={22} color="#FFFFFF" aria-hidden="true" />
        AI bilan gaplashish
      </Link>
    </AppShell>
  );
}
