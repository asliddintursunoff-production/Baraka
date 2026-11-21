import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Bell } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { apiGet, apiPost } from "@/lib/api";
import { cn } from "@/lib/utils";

interface AlertRow {
  id: number;
  kind: string;
  severity: "info" | "warn" | "danger";
  text: string;
  date: string;
  new: boolean;
}

const DOT: Record<AlertRow["severity"], string> = {
  info: "bg-primary",
  warn: "bg-warning",
  danger: "bg-danger",
};

/** Bell + popover: template alerts and the 08:00 brief (`GET/POST /api/alerts`). */
export function AlertsBell({ count }: { count: number }) {
  const [open, setOpen] = useState(false);
  const qc = useQueryClient();
  const box = useRef<HTMLDivElement>(null);
  const q = useQuery({
    queryKey: ["alerts"],
    queryFn: () => apiGet<{ alerts: AlertRow[] }>("/api/alerts"),
    enabled: open,
  });

  useEffect(() => {
    if (!open) return;
    const close = (e: MouseEvent) => {
      if (box.current && !box.current.contains(e.target as Node)) setOpen(false);
    };
    const esc = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    document.addEventListener("mousedown", close);
    document.addEventListener("keydown", esc);
    return () => {
      document.removeEventListener("mousedown", close);
      document.removeEventListener("keydown", esc);
    };
  }, [open]);

  const toggle = () => {
    const next = !open;
    setOpen(next);
    if (next && count > 0) {
      void apiPost("/api/alerts", {}).then(() => qc.invalidateQueries({ queryKey: ["dashboard"] }));
    }
  };

  return (
    <div ref={box} className="relative">
      <button
        type="button"
        aria-label={`Bildirishnomalar, ${count} ta yangi`}
        aria-expanded={open}
        onClick={toggle}
        className="relative flex h-11 w-11 items-center justify-center rounded-inner border border-border bg-surface text-text-2"
      >
        <Bell size={20} aria-hidden="true" />
        {count > 0 && (
          <span className="absolute right-[6px] top-[6px] flex h-[18px] min-w-[18px] items-center justify-center rounded-[9px] bg-danger text-[11px] font-bold text-white">
            {count}
          </span>
        )}
      </button>
      {open && (
        <div
          role="dialog"
          aria-label="Bildirishnomalar"
          className="absolute right-0 top-12 z-30 w-[min(360px,calc(100vw-32px))] rounded-card border border-border bg-surface p-4 shadow-lg"
        >
          <div className="mb-2 text-15 font-semibold text-text-1">Bildirishnomalar</div>
          {q.isLoading && <div className="text-13 text-text-3">Yuklanmoqda…</div>}
          {q.data && q.data.alerts.length === 0 && (
            <div className="text-13 text-text-3">Hozircha ogohlantirish yo&apos;q.</div>
          )}
          <ul className="flex max-h-[360px] flex-col gap-3 overflow-y-auto">
            {q.data?.alerts.map((a) => (
              <li key={a.id} className="flex gap-2 text-13 leading-snug text-text-2">
                <span className={cn("mt-[6px] h-2 w-2 shrink-0 rounded-full", DOT[a.severity])} aria-hidden="true" />
                <span className={cn(a.new && "font-semibold text-text-1")}>{a.text}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
