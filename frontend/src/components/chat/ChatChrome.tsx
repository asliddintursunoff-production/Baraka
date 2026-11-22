import { CalendarClock, ChevronDown, CircleCheck, LineChart, PiggyBank, Wallet } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";

import { RichText } from "@/components/RichText";
import { useMe } from "@/lib/auth";
import type { Basis, Brief } from "@/lib/chatTypes";
import { cn } from "@/lib/utils";

import { WaveIcon } from "./icons";
import { prefetchLive } from "./live";

const TONE = { high: "text-success", medium: "text-warning", low: "text-danger" } as const;

function asOfLabel(iso?: string): string {
  if (!iso) return "";
  const d = new Date(`${iso.slice(0, 10)}T00:00:00`);
  const m = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avgust", "sentyabr", "oktyabr", "noyabr", "dekabr"];
  return Number.isNaN(d.getTime()) ? "" : `${d.getDate()}-${m[d.getMonth()]}`;
}

/** "Sheets ✓ · yangilangan 21-noyabr" — click: data sources, confidence, k-anonymity note. */
export function DataChip({ basis }: { basis: Basis | null }) {
  const me = useMe();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => !ref.current?.contains(e.target as Node) && setOpen(false);
    document.addEventListener("mousedown", onDoc);
    return () => document.removeEventListener("mousedown", onDoc);
  }, [open]);
  const asOf = asOfLabel(me.data?.freshness?.as_of);
  const conf = basis?.confidence ?? null;
  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="inline-flex min-h-tap items-center gap-1.5 rounded-pill border border-border bg-surface px-3 text-13 font-semibold text-text-2 hover:bg-[#F2F4F7]"
      >
        <CircleCheck size={16} className="text-success" aria-hidden="true" />
        Sheets{asOf && <span className="hidden font-normal text-text-3 sm:inline"> · yangilangan {asOf}</span>}
        <ChevronDown size={14} aria-hidden="true" />
      </button>
      {open && (
        <div className="absolute right-0 top-full z-40 mt-2 flex w-[320px] max-w-[calc(100vw-32px)] flex-col gap-3 rounded-card border border-border bg-surface p-4 shadow-xl">
          <span className="text-14 font-bold">Ma'lumot manbalari</span>
          {(basis?.items ?? []).map((it, i) => (
            <div key={i} className="flex flex-col text-14 leading-normal">
              <span>{it.title}</span>
              {it.note && <span className="text-13 text-text-4">{it.note}</span>}
            </div>
          ))}
          {conf && (
            <div className="flex flex-col gap-0.5 border-t border-border-subtle pt-3 text-14">
              <span className="text-13 text-text-4">Javobga ishonch</span>
              <span className={cn("font-bold", TONE[conf.level] ?? TONE.medium)}>{conf.label}</span>
              {conf.note && <span className="text-13 text-text-3">{conf.note}</span>}
            </div>
          )}
          <p className="m-0 text-12 text-text-4">
            Boshqa bizneslar tajribasi faqat anonim va kamida 5 ta biznes bo'lsa ishlatiladi (k-anonimlik).
          </p>
          <Link to="/sources" className="text-14 font-semibold">
            Ma'lumotlarni boshqarish →
          </Link>
        </div>
      )}
    </div>
  );
}

/** 56px sticky header (tablet/desktop): "AI CFO · business" left; data chip + "Jonli gaplashish" right. */
export function ChatHeader({ businessName, basis }: { businessName: string; basis: Basis | null }) {
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const on = () => setScrolled(window.scrollY > 4);
    on();
    window.addEventListener("scroll", on, { passive: true });
    return () => window.removeEventListener("scroll", on);
  }, []);
  return (
    <header
      className={cn(
        "sticky top-topbar z-20 flex h-14 items-center justify-between gap-3 bg-bg/95 px-4 backdrop-blur md:top-0 md:px-6",
        scrolled ? "border-b border-border" : "border-b border-transparent",
      )}
    >
      <div className="flex min-w-0 items-baseline gap-2">
        <h1 className="m-0 hidden font-display text-17 font-bold md:block">AI CFO</h1>
        {businessName && <span className="truncate text-14 text-text-3">{businessName}</span>}
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <DataChip basis={basis} />
        <Link
          to="/live"
          onMouseEnter={prefetchLive}
          onFocus={prefetchLive}
          className="hidden min-h-tap items-center gap-2 rounded-pill bg-ink px-4 text-14 font-semibold text-white no-underline hover:text-white md:inline-flex"
        >
          <WaveIcon size={18} />
          Jonli gaplashish
        </Link>
      </div>
    </header>
  );
}

const SUGGESTIONS = [
  { text: "Bugun qancha pul bor?", Icon: Wallet },
  { text: "Keyingi oy prognozi", Icon: LineChart },
  { text: "Kredit qachon tugaydi?", Icon: PiggyBank },
  { text: "Bu hafta qanday o'tdi?", Icon: CalendarClock },
];

/** Empty chat: greeting (+ the morning brief) and 4 suggestion cards (2×2). */
export function SuggestionGrid({
  brief,
  disabled,
  onAsk,
  questions,
}: {
  brief: Brief | null;
  disabled: boolean;
  onAsk: (t: string) => void;
  questions?: { intent: string; text: string }[];
}) {
  const icons = [Wallet, LineChart, PiggyBank, CalendarClock];
  const items = questions?.length ? questions.map((q, i) => ({ text: q.text, Icon: icons[i % 4] ?? Wallet })) : SUGGESTIONS;
  const me = useMe();
  const name = me.data?.user.first_name;
  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 py-10 text-center">
      <div className="flex flex-col gap-2">
        <h2 className="m-0 font-display text-22 font-bold sm:text-26">{name ? `Salom, ${name}!` : "Salom!"} Bugun nimani hisoblaymiz?</h2>
        {brief && (
          <p className="m-0 text-15 leading-relaxed text-text-3">
            <RichText text={brief.lead} /> <strong className="text-ink">{brief.strong}</strong> <RichText text={brief.rest} />
          </p>
        )}
      </div>
      <div className="grid w-full grid-cols-2 gap-2 sm:gap-3">
        {items.map(({ text, Icon }) => (
          <button
            key={text}
            type="button"
            disabled={disabled}
            onClick={() => onAsk(text)}
            className="flex min-h-[88px] flex-col items-start justify-center gap-2 rounded-card border border-border bg-surface p-3 text-left text-14 font-semibold text-ink hover:bg-[#F9FAFB] disabled:opacity-60 sm:min-h-[72px] sm:flex-row sm:items-center sm:gap-3 sm:px-4 sm:text-15"
          >
            <Icon size={20} className="shrink-0 text-text-3" aria-hidden="true" />
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
