import { CalendarDays, ChevronDown, Database, FileSpreadsheet, House, Lightbulb, Lock, MessageCircle, TrendingUp } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import { useMe, useSwitchBusiness } from "@/lib/auth";
import { appConfig } from "@/lib/config";
import { cn } from "@/lib/utils";

import { LogoMark } from "./LogoMark";

export type NavKey = "main" | "chat" | "forecast" | "calendar" | "knowledge" | "sources" | "files";

const NAV: { key: NavKey; to: string; label: string; Icon: typeof House }[] = [
  { key: "main", to: "/dashboard", label: "Bosh sahifa", Icon: House },
  { key: "chat", to: "/chat", label: "AI CFO", Icon: MessageCircle },
  { key: "forecast", to: "/forecast", label: "Prognoz", Icon: TrendingUp },
  { key: "calendar", to: "/calendar", label: "To'lovlar kalendari", Icon: CalendarDays },
  { key: "files", to: "/files", label: "Fayl tahlili", Icon: FileSpreadsheet },
  { key: "knowledge", to: "/knowledge", label: "AI bilimi", Icon: Lightbulb },
  { key: "sources", to: "/sources", label: "Ma'lumotlar", Icon: Database },
];

function DemoBadge() {
  return (
    <span className="ml-2 rounded-pill bg-warning-bg px-2 py-[2px] text-12 font-bold text-warning">Demo</span>
  );
}

/** `locked`: no data yet (Gate.html) — every item except "Ma'lumotlar" is disabled. */
export function AppSidebar({ active, locked = false }: { active: NavKey; locked?: boolean }) {
  const me = useMe();
  const switchBusiness = useSwitchBusiness();
  const [open, setOpen] = useState(false);
  const current = me.data?.business;
  const others = (me.data?.businesses ?? []).filter((b) => b.id !== current?.id);

  return (
    <nav
      aria-label="Asosiy menyu"
      className="box-border flex max-w-full flex-[1_1_240px] flex-col gap-1 border-r border-border bg-surface px-4 py-6"
    >
      <div className="flex items-center gap-[10px] px-2 pb-6">
        <LogoMark />
        <span className="font-display text-[19px] font-bold text-[#0A3B22]">{appConfig.appName}</span>
      </div>
      {NAV.map(({ key, to, label, Icon }) =>
        locked && key !== "sources" ? (
          <span
            key={key}
            aria-disabled="true"
            className="flex min-h-tap items-center gap-3 rounded-btn px-3 text-15 text-[#98A2B3]"
          >
            <Lock size={18} strokeWidth={2} aria-hidden="true" />
            {label}
          </span>
        ) : (
        <Link
          key={key}
          to={to}
          aria-current={key === active ? "page" : undefined}
          className={cn(
            "flex min-h-tap items-center gap-3 rounded-btn px-3 text-15 no-underline",
            key === active
              ? "bg-primary-soft font-semibold text-primary hover:text-primary"
              : "text-text-2 hover:bg-[#F2F4F7] hover:text-ink",
          )}
        >
          <Icon size={20} strokeWidth={2} aria-hidden="true" />
          {label}
        </Link>
        ),
      )}
      <div className="min-h-6 grow" />
      <div className="relative flex flex-col gap-[6px] rounded-inner border border-border p-3">
        <span className="text-12 font-semibold uppercase tracking-label text-text-4">Biznes</span>
        <button
          type="button"
          aria-haspopup="listbox"
          aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
          className="flex min-h-tap items-center justify-between rounded-lg border-0 bg-bg px-[10px] text-14 font-semibold text-ink"
        >
          <span>
            {current ? `${current.name} · ${current.city}` : "…"}
            {current?.is_demo && <DemoBadge />}
          </span>
          <ChevronDown size={16} aria-hidden="true" />
        </button>
        {open && others.length > 0 && (
          <ul
            role="listbox"
            aria-label="Biznesni tanlash"
            className="m-0 flex list-none flex-col gap-1 p-0"
          >
            {others.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  className="flex min-h-tap w-full items-center rounded-lg border-0 bg-surface px-[10px] text-left text-14 text-text-2 hover:bg-bg"
                  onClick={async () => {
                    setOpen(false);
                    await switchBusiness(b.id);
                  }}
                >
                  {b.name} · {b.city}
                  {b.is_demo && <DemoBadge />}
                </button>
              </li>
            ))}
          </ul>
        )}
        {open && others.length === 0 && (
          <span className="text-13 text-text-4">Boshqa biznes yo'q</span>
        )}
      </div>
    </nav>
  );
}
