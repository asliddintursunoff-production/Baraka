import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useState } from "react";

import { AppShell } from "@/components/AppShell";
import { ErrorState, PageSkeleton } from "@/components/States";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import type { CalendarDay, CalendarPage } from "@/lib/types";
import { cn } from "@/lib/utils";

const DAY_STYLE: Record<CalendarDay["kind"], string> = {
  hot: "border-2 border-warning-accent bg-warning-bg",
  pay: "border border-border-input bg-surface",
  plain: "border border-border-subtle bg-surface-muted-2",
  out: "border border-border-subtle bg-surface-muted-2 opacity-60",
};

function AddPayment({ onDone }: { onDone: () => void }) {
  const qc = useQueryClient();
  const [form, setForm] = useState({ title: "", amount: "", due_date: "", priority: "critical" });
  const add = useMutation({
    mutationFn: () => apiPost("/api/obligations", { ...form, amount: form.amount.replace(/\s/g, "") }),
    onSuccess: async () => {
      await qc.invalidateQueries();
      onDone();
    },
  });
  const err = add.error instanceof ApiError ? (add.error.body as { message?: string } | null)?.message : null;
  return (
    <form
      aria-label="To'lov qo'shish"
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-5"
      onSubmit={(e) => {
        e.preventDefault();
        add.mutate();
      }}
    >
      <h2 className="m-0 font-display text-20 font-bold">Yangi to'lov</h2>
      <label className="flex flex-col gap-1 text-13 font-semibold text-text-3">
        Nima uchun
        <input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} className="min-h-tap rounded-btn border border-border-input px-3 text-15 font-normal text-ink" />
      </label>
      <label className="flex flex-col gap-1 text-13 font-semibold text-text-3">
        Summa (so'm)
        <input required inputMode="numeric" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} className="min-h-tap rounded-btn border border-border-input px-3 text-15 font-normal text-ink" />
      </label>
      <label className="flex flex-col gap-1 text-13 font-semibold text-text-3">
        Sana
        <input required type="date" value={form.due_date} onChange={(e) => setForm({ ...form, due_date: e.target.value })} className="min-h-tap rounded-btn border border-border-input px-3 text-15 font-normal text-ink" />
      </label>
      <label className="flex flex-col gap-1 text-13 font-semibold text-text-3">
        Turi
        <select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })} className="min-h-tap rounded-btn border border-border-input px-3 text-15 font-normal text-ink">
          <option value="critical">Majburiy to'lov</option>
          <option value="deferrable">Kechiktirsa bo'ladi</option>
          <option value="discretionary">Ixtiyoriy</option>
        </select>
      </label>
      {err && <p className="m-0 text-14 text-danger">{err}</p>}
      {add.isError && !err && <p className="m-0 text-14 text-danger">Saqlab bo'lmadi. Maydonlarni tekshiring.</p>}
      <div className="flex gap-2">
        <button type="submit" disabled={add.isPending} className="min-h-tap rounded-btn bg-primary px-[18px] text-15 font-semibold text-white">
          Saqlash
        </button>
        <button type="button" onClick={onDone} className="min-h-tap rounded-btn border border-border-input bg-surface px-[18px] text-15 font-semibold text-text-2">
          Bekor qilish
        </button>
      </div>
    </form>
  );
}

function Detail({ day }: { day: CalendarDay }) {
  const remind = useMutation({
    mutationFn: (r: { date: string; label: string }) =>
      apiPost("/api/actions", { kind: "reminder", date: r.date, text: `${day.title}: muhim to'lovlar kuni` }),
  });
  const d = day.detail;
  return (
    <aside aria-label="Tanlangan kun" className="flex min-w-0 flex-[1_1_320px] flex-col gap-[14px] rounded-card border border-border bg-surface px-5 py-[22px]">
      <span className="text-13 font-bold uppercase tracking-label text-text-4">Tanlangan kun</span>
      <h2 className="m-0 font-display text-24 font-bold">{day.title}</h2>
      {!d && <p className="m-0 text-15 text-text-3">Bu kun prognoz oralig'idan tashqarida.</p>}
      {d?.full && (
        <div className="flex flex-col gap-[14px]">
          <span
            className={cn(
              "inline-flex items-center gap-[6px] self-start rounded-pill px-3 py-[5px] text-14 font-bold",
              d.status === "danger" ? "bg-danger-bg text-danger" : "bg-warning-bg text-warning",
            )}
          >
            {d.chip}
          </span>
          <div className="flex flex-col text-15">
            {d.rows.map((r, i) => (
              <div key={i} className="flex justify-between border-b border-border-subtle py-[10px]">
                <span className={r.tone === "plain" || r.tone === "success" ? "text-text-3" : ""}>
                  {r.label} {r.badge && <span className="text-12 font-bold text-danger">{r.badge}</span>}
                </span>
                <strong className={r.tone === "success" ? "text-success" : r.tone === "danger" ? "text-danger" : ""}>{r.value}</strong>
              </div>
            ))}
            <div className="flex justify-between py-3">
              <span className="font-bold">Kun oxirida qoladi</span>
              <strong className={cn("text-[18px]", d.status === "danger" ? "text-danger" : "text-warning")}>{d.closing}</strong>
            </div>
          </div>
          <div className="flex flex-col gap-[6px] rounded-inner bg-ink p-[14px] text-white">
            <span className="text-12 font-bold tracking-label text-[#B2CCFF]">AI MASLAHATI</span>
            <span className="text-15 leading-normal">{d.advice}</span>
          </div>
          {d.reminder && (
            <button
              type="button"
              disabled={remind.isPending || remind.isSuccess}
              onClick={() => d.reminder && remind.mutate(d.reminder)}
              className="min-h-tap rounded-btn border border-border-input bg-surface text-14 font-semibold text-text-2"
            >
              {remind.isSuccess ? "Eslatma qo'yildi" : d.reminder.label}
            </button>
          )}
        </div>
      )}
      {d && !d.full && (
        <div className="flex flex-col gap-[10px]">
          <span className="text-15 leading-normal text-text-2">{d.text}</span>
          <div className="flex justify-between border-t border-border-subtle py-3 text-15">
            <span className="font-bold">Kun oxirida qoladi</span>
            <strong className="text-[18px]">{d.closing}</strong>
          </div>
        </div>
      )}
    </aside>
  );
}

export default function CalendarPageView() {
  const [month, setMonth] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const [grid, setGrid] = useState(false); // mobile: agenda list by default, month grid on toggle
  const q = useQuery({
    queryKey: ["calendar", month],
    queryFn: () => apiGet<CalendarPage>(`/api/calendar${month ? `?month=${month}` : ""}`),
  });

  if (q.isPending)
    return (
      <AppShell active="calendar">
        <PageSkeleton />
      </AppShell>
    );
  if (q.isError)
    return (
      <AppShell active="calendar">
        <ErrorState error={q.error} onRetry={() => q.refetch()} />
      </AppShell>
    );
  const c = q.data;
  const sel = c.days.find((d) => d.date === (selected ?? c.selected)) ?? c.days[0]!;

  return (
    <AppShell active="calendar">
      <header className="flex flex-wrap items-end justify-between gap-4">
        <div className="flex flex-col gap-[6px]">
          <h1 className="m-0 font-display text-30 font-bold">To'lovlar kalendari</h1>
          <span className="text-16 text-text-3">Qachon, kimga, qancha to'lashingiz kerak — va o'sha kuni kassada qancha qoladi</span>
        </div>
        <div className="flex flex-wrap gap-[10px]">
          <div className="flex items-center gap-1">
            <button
              type="button"
              aria-label="Oldingi oy"
              onClick={() => {
                setMonth(c.prev);
                setSelected(null);
              }}
              className="flex h-11 w-11 items-center justify-center rounded-btn border border-border-input bg-surface"
            >
              <ChevronLeft size={18} color="#344054" aria-hidden="true" />
            </button>
            <span className="min-w-[140px] text-center text-17 font-bold" aria-live="polite">
              {c.title}
            </span>
            <button
              type="button"
              aria-label="Keyingi oy"
              onClick={() => {
                setMonth(c.next);
                setSelected(null);
              }}
              className="flex h-11 w-11 items-center justify-center rounded-btn border border-border-input bg-surface"
            >
              <ChevronRight size={18} color="#344054" aria-hidden="true" />
            </button>
          </div>
          <button
            type="button"
            onClick={() => setAdding((v) => !v)}
            className="min-h-tap rounded-btn border-0 bg-primary px-[18px] text-15 font-semibold text-white hover:bg-primary-hover"
          >
            + To'lov qo'shish
          </button>
        </div>
      </header>

      {adding && <AddPayment onDone={() => setAdding(false)} />}

      <div className="flex flex-wrap items-start gap-5">
        <div className="flex w-full items-center justify-between md:hidden">
          <span className="text-15 font-bold">{grid ? "Oy ko'rinishi" : "To'lovlar ro'yxati"}</span>
          <button
            type="button"
            onClick={() => setGrid((v) => !v)}
            className="min-h-tap rounded-pill border border-border-input bg-surface px-4 text-14 font-semibold text-text-2"
          >
            {grid ? "Ro'yxat" : "Oy ko'rinishi"}
          </button>
        </div>
        {!grid && (
          <ul aria-label={`${c.title}: to'lovlar`} className="m-0 flex w-full list-none flex-col gap-2 p-0 md:hidden">
            {c.days.filter((d) => d.items.length > 0 || d.kind === "hot").length === 0 && (
              <li className="rounded-card border border-border bg-surface p-4 text-14 text-text-3">Bu oyda to'lov yo'q</li>
            )}
            {c.days
              .filter((d) => d.items.length > 0 || d.kind === "hot")
              .map((d) => (
                <li key={d.date}>
                  <button
                    type="button"
                    onClick={() => setSelected(d.date)}
                    aria-pressed={d.date === sel.date}
                    className={cn(
                      "flex min-h-14 w-full items-start gap-3 rounded-card border bg-surface p-3 text-left",
                      d.date === sel.date ? "border-primary-border" : "border-border",
                    )}
                  >
                    <span className="flex w-11 shrink-0 flex-col items-center rounded-btn bg-[#F2F4F7] py-1">
                      <span className="text-17 font-bold leading-tight">{d.n}</span>
                    </span>
                    <span className="flex min-w-0 flex-1 flex-col gap-1">
                      {d.items.map((it, i) => (
                        <span key={i} className="flex items-center justify-between gap-2 text-14">
                          <span className="truncate font-semibold">{it.label}</span>
                          {it.critical && <span className="shrink-0 rounded-pill bg-danger-bg px-2 text-12 font-bold text-danger">majburiy</span>}
                        </span>
                      ))}
                      {d.bal && (
                        <span className={cn("text-13", d.kind === "hot" ? "font-bold text-warning" : "text-text-3")}>
                          Kun oxirida: {d.bal}
                          {d.kind === "hot" && " · qiyin kun"}
                        </span>
                      )}
                    </span>
                  </button>
                </li>
              ))}
          </ul>
        )}
        <section
          aria-label={c.title}
          className={cn(
            "min-w-0 flex-[999_1_600px] overflow-x-auto rounded-card border border-border bg-surface p-[18px]",
            !grid && "hidden md:block",
          )}
        >
          <div className="grid min-w-[640px] grid-cols-7 gap-[6px]">
            {c.weekdays.map((w) => (
              <span key={w} className="py-[6px] text-center text-12 font-bold text-text-4">
                {w}
              </span>
            ))}
            {Array.from({ length: c.lead }).map((_, i) => (
              <div key={`lead-${i}`} className="min-h-[104px]" />
            ))}
            {c.days.map((d) => (
              <button
                key={d.date}
                type="button"
                onClick={() => setSelected(d.date)}
                aria-pressed={d.date === sel.date}
                aria-label={`${d.title}${d.bal ? `, kun oxirida ${d.bal}` : ""}`}
                className={cn(
                  "flex min-h-[104px] flex-col items-stretch gap-1 rounded-btn p-2 text-left",
                  DAY_STYLE[d.kind],
                  d.date === sel.date && "outline outline-2 outline-offset-1 outline-primary-border",
                )}
              >
                <span className={cn("text-14", d.kind === "plain" || d.kind === "out" ? "font-semibold text-text-3" : "font-bold text-ink")}>{d.n}</span>
                {d.items.map((it, i) => (
                  <span
                    key={i}
                    className={cn(
                      "rounded-md px-[6px] py-[2px] text-[11px] font-bold",
                      it.critical ? "bg-danger text-white" : "bg-primary-soft text-primary",
                    )}
                  >
                    {it.label}
                  </span>
                ))}
                {d.bal && (
                  <span
                    className={cn(
                      "mt-auto text-[11px]",
                      d.kind === "hot" ? "font-bold text-warning" : d.kind === "pay" ? "font-semibold text-text-3" : "text-text-4",
                    )}
                  >
                    {d.bal}
                  </span>
                )}
              </button>
            ))}
          </div>
          <div className="flex min-w-[640px] flex-wrap gap-4 pt-[14px] text-13 text-text-3">
            <span className="inline-flex items-center gap-[6px]">
              <span className="h-3 w-3 rounded-[3px] bg-danger" />
              Majburiy to'lov
            </span>
            <span className="inline-flex items-center gap-[6px]">
              <span className="h-3 w-3 rounded-[3px] border border-primary-border bg-primary-soft" />
              Boshqa to'lov
            </span>
            <span className="inline-flex items-center gap-[6px]">
              <span className="h-3 w-3 rounded-[3px] border-2 border-warning-accent bg-warning-bg" />
              Qiyin kun
            </span>
            <span>Pastdagi raqam — kun oxirida kassada qoladigan pul</span>
          </div>
        </section>
        <Detail day={sel} />
      </div>
    </AppShell>
  );
}
