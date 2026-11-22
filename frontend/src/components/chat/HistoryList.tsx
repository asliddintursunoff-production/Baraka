import { useQueryClient } from "@tanstack/react-query";
import { MoreHorizontal, Search } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import { apiDelete, apiPatch } from "@/lib/api";
import { cn } from "@/lib/utils";

export interface ConvRow {
  id: number;
  title: string;
  channel: string;
  date: string;
}

const GREETING = /^\W*(salom|assalomu?\s*alaykum|assalom|qalaysiz|qanaysan|qalaysan|hello|hi|privet|rahmat)\W*$/i;

function group(date: string): string {
  const d = new Date(`${date}T00:00:00`);
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const days = Math.round((today.getTime() - d.getTime()) / 86_400_000);
  if (days <= 0) return "Bugun";
  if (days === 1) return "Kecha";
  if (days < 7) return "Oxirgi 7 kun";
  return "Oldinroq";
}

const ORDER = ["Bugun", "Kecha", "Oxirgi 7 kun", "Oldinroq"];

/** Chat history in the sidebar: grouped by day, one line each, ⋯ → rename / delete. */
export function HistoryList({ items, activeId, onNavigate }: { items: ConvRow[]; activeId?: number; onNavigate?: () => void }) {
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [menu, setMenu] = useState<number | null>(null);
  const [hidden, setHidden] = useState<Set<number>>(new Set());
  const [renamed, setRenamed] = useState<Record<number, string>>({});

  const groups = useMemo(() => {
    const out: Record<string, ConvRow[]> = {};
    for (const c of items) {
      const title = renamed[c.id] ?? c.title;
      if (hidden.has(c.id) || GREETING.test(title)) continue;
      if (q && !title.toLowerCase().includes(q.toLowerCase())) continue;
      (out[group(c.date)] ??= []).push({ ...c, title });
    }
    return ORDER.filter((g) => out[g]?.length).map((g) => [g, out[g] ?? []] as const);
  }, [items, q, hidden, renamed]);

  const rename = async (c: ConvRow) => {
    setMenu(null);
    const title = window.prompt("Chat nomi", c.title)?.trim();
    if (!title) return;
    setRenamed((r) => ({ ...r, [c.id]: title }));
    await apiPatch(`/api/chat/conversations/${c.id}`, { title }).catch(() => undefined);
  };
  const remove = async (c: ConvRow) => {
    setMenu(null);
    if (!window.confirm(`"${c.title}" chatini o'chirasizmi?`)) return;
    setHidden((h) => new Set(h).add(c.id));
    await apiDelete(`/api/chat/conversations/${c.id}`).catch(() => undefined);
    void qc.invalidateQueries({ queryKey: ["chat", "bootstrap"] });
  };

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-2">
      <label className="flex min-h-10 items-center gap-2 rounded-btn bg-[#F2F4F7] px-3 text-text-3">
        <Search size={16} aria-hidden="true" />
        <span className="sr-only">Chatlarni qidirish</span>
        <input
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Chatlarni qidirish"
          className="min-w-0 flex-1 border-0 bg-transparent text-16 text-ink outline-none placeholder:text-text-4 md:text-14"
        />
      </label>
      <div className="-mx-1 flex min-h-0 flex-1 flex-col gap-3 overflow-y-auto px-1 pb-2">
        {groups.length === 0 && <span className="px-2 text-13 text-text-4">Hali chat yo'q</span>}
        {groups.map(([label, rows]) => (
          <div key={label} className="flex flex-col gap-0.5">
            <span className="px-2 pb-1 text-12 font-semibold text-text-4">{label}</span>
            {rows.map((c) => (
              <div
                key={c.id}
                className={cn(
                  "group relative flex min-h-10 items-center rounded-btn",
                  c.id === activeId ? "bg-[#EEF2F6]" : "hover:bg-[#F2F4F7]",
                )}
              >
                <Link
                  to={`/chat?c=${c.id}`}
                  onClick={onNavigate}
                  title={c.title}
                  aria-current={c.id === activeId ? "page" : undefined}
                  className={cn(
                    "flex min-h-10 min-w-0 flex-1 items-center gap-2 truncate px-2 text-14 no-underline",
                    c.id === activeId ? "font-semibold text-ink hover:text-ink" : "text-text-2 hover:text-ink",
                  )}
                >
                  <span className="truncate">{c.title}</span>
                  {c.channel === "voice" && (
                    <span className="shrink-0 rounded-pill bg-[#F0FDFA] px-1.5 text-11 font-bold text-[#0F766E]">Live</span>
                  )}
                </Link>
                <button
                  type="button"
                  aria-label={`${c.title}: amallar`}
                  aria-expanded={menu === c.id}
                  onClick={() => setMenu((m) => (m === c.id ? null : c.id))}
                  className={cn(
                    "grid size-10 shrink-0 place-items-center rounded-btn border-0 bg-transparent text-text-3 hover:text-ink",
                    menu === c.id ? "opacity-100" : "opacity-100 md:opacity-0 md:group-hover:opacity-100 md:focus-visible:opacity-100",
                  )}
                >
                  <MoreHorizontal size={16} />
                </button>
                {menu === c.id && (
                  <div className="absolute right-0 top-full z-40 flex w-48 flex-col rounded-inner border border-border bg-surface p-1 shadow-lg">
                    <button type="button" onClick={() => void rename(c)} className="min-h-10 rounded-lg border-0 bg-transparent px-3 text-left text-14 hover:bg-bg">
                      Nomini o'zgartirish
                    </button>
                    <button type="button" onClick={() => void remove(c)} className="min-h-10 rounded-lg border-0 bg-transparent px-3 text-left text-14 text-danger hover:bg-danger-bg">
                      O'chirish
                    </button>
                  </div>
                )}
              </div>
            ))}
          </div>
        ))}
      </div>
    </div>
  );
}
