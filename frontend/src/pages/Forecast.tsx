import { useMutation, useQuery } from "@tanstack/react-query";
import { lazy, Suspense, useState } from "react";
import { Link } from "react-router-dom";

import { AppShell } from "@/components/AppShell";
import { RichText } from "@/components/RichText";
import { HorizonToggle, type Horizon } from "@/components/HorizonToggle";
import { ErrorState, InsufficientData, PageSkeleton, Skeleton } from "@/components/States";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import type { ForecastPage, ScenarioCard, ScenarioResult } from "@/lib/types";
import { cn } from "@/lib/utils";

import { CHIP } from "./Main";

const ForecastChart = lazy(() => import("@/components/ForecastChart"));

const CARD_TONE = {
  success: { box: "bg-success-bg", title: "text-success" },
  warning: { box: "bg-warning-bg", title: "text-warning" },
  danger: { box: "bg-danger-bg", title: "text-danger" },
} as const;

function Card({ card }: { card: ScenarioCard }) {
  const tone = CARD_TONE[card.tone];
  return (
    <div className={cn("flex flex-col gap-2 rounded-[14px] p-4", tone.box)} aria-live="polite">
      <span className={cn("font-display text-22 font-bold", tone.title)}>{card.title}</span>
      <span className="text-15 leading-normal text-text-2">
        {card.body.before}
        <strong>{card.body.strong}</strong>
        {card.body.after}
      </span>
      <span className="text-15 font-semibold leading-normal text-ink">{card.tip}</span>
    </div>
  );
}

export default function ForecastPageView() {
  const q = useQuery({ queryKey: ["forecast"], queryFn: () => apiGet<ForecastPage>("/api/forecast") });
  const [horizon, setHorizon] = useState<Horizon>(60);
  const [selected, setSelected] = useState("buy");
  const [text, setText] = useState("");
  const [custom, setCustom] = useState<ScenarioResult | null>(null);
  const free = useMutation({
    mutationFn: (t: string) => apiPost<ScenarioResult>("/api/simulate", { text: t }),
    onSuccess: (r) => {
      setCustom(r);
      setSelected("custom");
    },
    onError: (e) => {
      const body = e instanceof ApiError ? (e.body as ScenarioResult | null) : null;
      setCustom({ card: null, message: body?.message ?? "Hisoblab bo'lmadi. Qaytadan urinib ko'ring." });
      setSelected("custom");
    },
  });

  if (q.isPending)
    return (
      <AppShell active="forecast">
        <PageSkeleton />
      </AppShell>
    );
  if (q.isError)
    return (
      <AppShell active="forecast">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </AppShell>
    );

  const d = q.data;
  const summary = d.forecast.summaries[String(horizon)]!;
  const chip = summary.verdict ? CHIP[summary.verdict] : null;
  const active: ScenarioResult | undefined = selected === "custom" ? (custom ?? undefined) : d.presets.find((p) => p.id === selected);
  const overlayColor = active?.card?.tone === "warning" ? "#B54708" : "#B42318";
  const keyDays = d.key_days.filter((k) => k.i <= horizon);

  return (
    <AppShell active="forecast">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-[6px]">
          <h1 className="m-0 font-display text-30 font-bold">Prognoz</h1>
          <span className="text-16 text-text-3">
            Kelajakda kassangizda qancha pul bo'lishi — va "agar shunday qilsam-chi?" degan savollarga javob
          </span>
        </div>
        <HorizonToggle value={horizon} onChange={setHorizon} large />
      </header>

      <div className="flex flex-wrap items-stretch gap-5">
        <section
          aria-label="Kassa prognozi grafigi"
          className="flex min-w-0 flex-[999_1_560px] flex-col gap-[14px] rounded-card border border-border bg-surface px-6 py-[22px]"
        >
          <div className="flex flex-wrap items-center gap-[10px]">
            {chip && (
              <span className={cn("inline-flex items-center gap-[6px] rounded-pill px-3 py-[5px] text-14 font-bold", chip.cls)}>
                <chip.Icon size={14} strokeWidth={2.8} aria-hidden="true" />
                {summary.verdict === "yes" ? "Hozirgi holatda pul yetadi" : summary.chip}
              </span>
            )}
            <span className="text-15 text-text-2">
              <RichText text={summary.text} />
            </span>
          </div>
          {d.forecast.insufficient_data ? (
            <InsufficientData />
          ) : (
            <Suspense fallback={<Skeleton className="h-64" />}>
              <ForecastChart
                series={d.forecast.series}
                days={horizon}
                safeMin={d.forecast.safe_min}
                safeLabel={d.forecast.safe_label}
                lowestIndex={summary.lowest_index}
                calloutTitle={summary.callout_title}
                calloutText={summary.callout_text}
                overlay={active?.overlay ?? null}
                overlayColor={overlayColor}
                overlayMarker={active?.marker_index != null && active.marker_index <= horizon ? active.marker_index : null}
                ariaLabel="Kassa prognozi va tanlangan 'agar' varianti"
                bandFill={0.08}
              />
            </Suspense>
          )}
          <div className="flex flex-wrap gap-[18px] text-13 text-text-3">
            <span className="inline-flex items-center gap-2">
              <span className="h-[3px] w-[18px] rounded-sm bg-primary" />
              Hozirgi holat
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="h-0 w-[18px] border-t-[3px] border-dashed border-danger" />
              Tanlangan "agar"
            </span>
            <span className="inline-flex items-center gap-2">
              <span className="h-[10px] w-[18px] rounded-sm bg-[#E1E8FA]" />
              Savdoga qarab o'zgarishi mumkin
            </span>
          </div>
        </section>

        <section
          aria-label="Agar shunday qilsam-chi"
          className="flex min-w-0 flex-[1_1_340px] flex-col gap-4 rounded-card border border-border bg-surface px-5 py-[22px]"
        >
          <h2 className="m-0 font-display text-20 font-bold">Agar shunday qilsam-chi?</h2>
          <div className="flex flex-col gap-2">
            {d.presets.map((p) => {
              const on = p.id === selected;
              return (
                <button
                  key={p.id}
                  type="button"
                  aria-pressed={on}
                  onClick={() => setSelected(p.id)}
                  className={cn(
                    "flex min-h-[52px] items-center gap-3 rounded-inner px-[14px] text-left text-15 font-semibold",
                    on ? "border-2 border-primary bg-primary-soft text-ink" : "border border-border-input bg-surface text-text-2",
                  )}
                >
                  <span
                    className={cn(
                      "box-border h-[18px] w-[18px] shrink-0 rounded-[9px]",
                      on ? "border-[5px] border-primary" : "border-2 border-[#98A2B3]",
                    )}
                  />
                  {p.label}
                </button>
              );
            })}
            <label htmlFor="own" className="pt-[6px] text-13 font-semibold text-text-3">
              Yoki o'zingiz yozing
            </label>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                if (text.trim()) free.mutate(text.trim());
              }}
            >
              <input
                id="own"
                type="text"
                value={text}
                onChange={(e) => setText(e.target.value)}
                placeholder={d.free_text_placeholder}
                className="box-border min-h-[46px] w-full rounded-btn border border-border-input px-3 text-15"
              />
            </form>
          </div>
          {free.isPending && <Skeleton className="h-28" />}
          {!free.isPending && active?.card && <Card card={active.card} />}
          {!free.isPending && active && !active.card && (
            <p className="m-0 rounded-[14px] bg-warning-bg p-4 text-15 text-warning">
              {active.message ??
                (active.needs === "staff_count"
                  ? "Xodimlar soni noma'lum. AI CFO bilan gaplashib, nechta xodimingiz borligini ayting."
                  : "Bu variantni hisoblab bo'lmadi.")}
            </p>
          )}
          <Link
            to="/chat"
            className="inline-flex min-h-[46px] items-center justify-center rounded-inner bg-ink text-15 font-semibold text-white no-underline hover:text-white"
          >
            AI bilan batafsil gaplashish
          </Link>
        </section>
      </div>

      <section aria-label="Muhim kunlar" className="flex flex-col gap-[14px] rounded-card border border-border bg-surface px-6 py-[22px]">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h2 className="m-0 font-display text-20 font-bold">Muhim kunlar</h2>
          <Link to="/calendar" className="text-14 font-semibold">
            Kalendarda ko'rish
          </Link>
        </div>
        <div className="grid grid-cols-[repeat(auto-fit,minmax(170px,1fr))] gap-3">
          {keyDays.map((k) => (
            <div
              key={k.date}
              className={cn(
                "flex flex-col gap-[6px] rounded-inner",
                k.hardest ? "border-2 border-warning-accent bg-warning-bg p-[13px]" : "border border-border p-[14px]",
              )}
            >
              <span className={cn("text-13 font-bold", k.hardest ? "text-warning" : "text-text-3")}>{k.label}</span>
              <span className="text-15 font-semibold">{k.title}</span>
              <span
                className={cn(
                  "text-14 font-semibold",
                  k.status === "ok" ? "text-success" : k.status === "warn" ? "text-warning" : "text-danger",
                )}
              >
                {k.balance}
              </span>
            </div>
          ))}
        </div>
      </section>
    </AppShell>
  );
}
