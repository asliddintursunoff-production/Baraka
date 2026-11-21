import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";

import { AppShell } from "@/components/AppShell";
import { BTN_PRIMARY, BTN_SECONDARY } from "@/components/sources/shared";
import { ErrorState, PageSkeleton } from "@/components/States";
import { ApiError, apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";

interface KnowledgePage {
  business: string;
  accuracy: { label: string; pct: number }[];
  candidates: { id: number; text: string }[];
  rules: { id: number; text: string; meta: string; enabled: boolean }[];
  segment: { text: string; usage: string }[];
  segment_min: number;
}

const H2 = "m-0 font-display text-[19px] font-bold";
const CARD = "flex flex-col rounded-card border border-border bg-surface px-[22px] py-5";

function Accuracy({ weeks }: { weeks: KnowledgePage["accuracy"] }) {
  const max = Math.max(1, ...weeks.map((w) => w.pct));
  const label = weeks.map((w) => `${w.label} ${w.pct}%`).join(", ");
  return (
    <section
      aria-label="Prognoz aniqligi"
      className="flex flex-wrap items-center gap-5 rounded-card bg-ink px-6 py-[22px] text-white"
    >
      <div className="flex flex-[1_1_300px] flex-col gap-1.5">
        <span className="text-13 font-bold uppercase tracking-[0.04em] text-[#B2CCFF]">
          AI qanchalik aniq bo&apos;lib bormoqda
        </span>
        <span className="text-17 leading-normal">
          Prognoz va haqiqiy natija orasidagi farq har hafta o&apos;lchanadi. Siz o&apos;rgatgan qoidalar bilan xato
          kamaydi.
        </span>
      </div>
      {weeks.length > 0 && (
        <div className="flex items-end gap-3.5" role="img" aria-label={`Haftalik prognoz xatosi: ${label}`}>
          {weeks.map((w, i) => (
            <div key={w.label} className="flex flex-col items-center gap-1.5">
              <span className="text-13 font-bold">{w.pct}%</span>
              <span
                className={cn("w-9 rounded-[6px]", i >= weeks.length / 2 ? "bg-primary-border" : "bg-text-3")}
                style={{ height: Math.max(12, Math.round((84 * w.pct) / max)) }}
              />
              <span className="text-12 text-[#98A2B3]">{w.label}</span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

function RuleForm({ onDone }: { onDone: () => void }) {
  const [text, setText] = useState("");
  const qc = useQueryClient();
  const m = useMutation({
    mutationFn: (t: string) => apiPost<{ ok: boolean; text: string }>("/api/knowledge/rules", { text: t }),
    onSuccess: () => {
      void qc.invalidateQueries();
      setText("");
      onDone();
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    if (text.trim().length >= 5) m.mutate(text.trim());
  };
  const err = m.error instanceof ApiError ? (m.error.body as { message?: string } | null)?.message : null;
  return (
    <form onSubmit={submit} className="flex flex-col gap-2 border-t border-border-subtle py-3.5">
      <label htmlFor="rule-text" className="text-14 font-semibold text-text-2">
        Qoidani oddiy so&apos;z bilan yozing
      </label>
      <input
        id="rule-text"
        autoFocus
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Masalan: Agro Go'shtga doim 15 kun kechiktirib to'laymiz"
        className="min-h-tap rounded-btn border border-border-input px-3 text-15"
      />
      {(err || m.isError) && <span className="text-13 text-danger">{err ?? "Saqlab bo'lmadi. Qayta urinib ko'ring."}</span>}
      <div className="flex flex-wrap gap-2.5">
        <button type="submit" className={BTN_PRIMARY} disabled={m.isPending || text.trim().length < 5}>
          {m.isPending ? "Saqlanmoqda…" : "Saqlash"}
        </button>
        <button type="button" className={BTN_SECONDARY} onClick={onDone}>
          Bekor qilish
        </button>
      </div>
    </form>
  );
}

export default function KnowledgePage() {
  const qc = useQueryClient();
  const [writing, setWriting] = useState(false);
  const q = useQuery({ queryKey: ["knowledge"], queryFn: () => apiGet<KnowledgePage>("/api/knowledge") });
  const decide = useMutation({
    mutationFn: ({ id, ok }: { id: number; ok: boolean }) =>
      apiPost(`/api/knowledge/candidates/${id}/${ok ? "accept" : "reject"}`, {}),
    onSuccess: () => void qc.invalidateQueries(),
  });
  const toggle = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) =>
      apiPost(`/api/knowledge/rules/${id}/toggle`, { enabled }),
    onSuccess: () => void qc.invalidateQueries(),
  });

  if (q.isLoading)
    return (
      <AppShell active="knowledge">
        <PageSkeleton />
      </AppShell>
    );
  if (q.isError || !q.data)
    return (
      <AppShell active="knowledge">
        <ErrorState error={q.error} onRetry={() => void q.refetch()} />
      </AppShell>
    );
  const d = q.data;

  return (
    <AppShell active="knowledge">
      <header className="flex flex-col gap-1.5">
        <h1 className="m-0 font-display text-30 font-bold">AI bilimi</h1>
        <span className="text-16 text-text-3">
          AI sizning biznesingiz qanday ishlashini shu yerda o&apos;rganadi. Siz tuzatgan har bir narsa keyingi
          prognozga ta&apos;sir qiladi.
        </span>
      </header>

      <Accuracy weeks={d.accuracy} />

      <div className="flex flex-wrap items-start gap-5">
        <div className="flex min-w-0 flex-[999_1_560px] flex-col gap-5">
          {d.candidates.map((c) => (
            <section
              key={c.id}
              aria-label="Tasdiqlash kutilmoqda"
              className="flex flex-col gap-3 rounded-card border-2 border-primary-border bg-surface px-[22px] py-5"
            >
              <div className="flex items-center gap-2.5">
                <h2 className={H2}>AI sezdi — to&apos;g&apos;rimi?</h2>
                <span className="rounded-pill bg-primary-soft px-2.5 py-[3px] text-12 font-bold text-primary">
                  1 ta yangi
                </span>
              </div>
              <p className="m-0 text-16 leading-[1.55]">{c.text}</p>
              <div className="flex flex-wrap gap-2.5">
                <button
                  type="button"
                  className={BTN_PRIMARY}
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: c.id, ok: true })}
                >
                  Ha, to&apos;g&apos;ri
                </button>
                <button
                  type="button"
                  className={BTN_SECONDARY}
                  disabled={decide.isPending}
                  onClick={() => decide.mutate({ id: c.id, ok: false })}
                >
                  Yo&apos;q
                </button>
              </div>
            </section>
          ))}

          <section aria-label="Siz o'rgatgan qoidalar" className={cn(CARD, "gap-1")}>
            <div className="flex flex-wrap items-center justify-between gap-2.5 pb-2">
              <h2 className={H2}>{d.business} qoidalari</h2>
              {!writing && (
                <button type="button" className={BTN_SECONDARY} onClick={() => setWriting(true)}>
                  + Qoida yozish
                </button>
              )}
            </div>
            {writing && <RuleForm onDone={() => setWriting(false)} />}
            {d.rules.length === 0 && !writing && (
              <p className="m-0 border-t border-border-subtle py-3.5 text-14 text-text-3">
                Hali qoida yo&apos;q. AI CFO bilan suhbatda tuzatish yozing yoki &quot;+ Qoida yozish&quot;ni bosing.
              </p>
            )}
            {d.rules.map((r) => (
              <article
                key={r.id}
                className="flex flex-wrap items-center gap-3.5 border-t border-border-subtle py-3.5"
              >
                <div className="flex flex-[1_1_320px] flex-col gap-1">
                  <span className={cn("text-16 font-semibold", !r.enabled && "text-text-3")}>{r.text}</span>
                  <span className="text-13 text-text-4">{r.meta}</span>
                </div>
                <label className="inline-flex min-h-tap cursor-pointer items-center gap-2 text-14 font-semibold">
                  <input
                    type="checkbox"
                    checked={r.enabled}
                    disabled={toggle.isPending}
                    onChange={(e) => toggle.mutate({ id: r.id, enabled: e.target.checked })}
                    className="h-5 w-5 accent-primary"
                  />
                  {r.enabled ? "Yoqilgan" : "O'chirilgan"}
                </label>
              </article>
            ))}
          </section>
        </div>

        <aside
          aria-label="Boshqa kafelar tajribasi"
          className="flex min-w-0 flex-[1_1_320px] flex-col gap-3.5 rounded-card border border-border bg-surface p-5"
        >
          <h2 className={H2}>Boshqa kafelar tajribasi</h2>
          <span className="text-14 leading-normal text-text-3">
            Toshkentdagi shunga o&apos;xshash kafelardan olingan umumiy xulosalar. Ularning ma&apos;lumoti sizga,
            sizniki ularga hech qachon ko&apos;rinmaydi.
          </span>
          {d.segment.map((s) => (
            <article key={s.text} className="flex flex-col gap-1.5 rounded-inner bg-bg p-3.5">
              <span className="text-15 font-semibold leading-[1.45]">{s.text}</span>
              {s.usage && <span className="text-13 text-text-4">{s.usage}</span>}
            </article>
          ))}
          <div className="flex gap-2.5 rounded-btn border border-border-subtle p-3 text-13 leading-normal text-text-3">
            <ShieldCheck size={18} aria-hidden="true" className="shrink-0" />
            <span>Faqat kamida {d.segment_min} ta biznesdan olingan, nom va summasiz xulosalar ishlatiladi.</span>
          </div>
        </aside>
      </div>
    </AppShell>
  );
}
