import {
  CalendarDays,
  ChevronDown,
  Database,
  FileSpreadsheet,
  House,
  Lightbulb,
  Lock,
  MessageCircle,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  TrendingUp,
} from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useMe, useSwitchBusiness } from "@/lib/auth";
import { appConfig } from "@/lib/config";
import { cn } from "@/lib/utils";

import { LogoMark } from "./LogoMark";

export type NavKey = "main" | "chat" | "forecast" | "calendar" | "knowledge" | "sources" | "files";

export const NAV: { key: NavKey; to: string; label: string; short: string; Icon: typeof House }[] = [
  { key: "main", to: "/dashboard", label: "Bosh sahifa", short: "Bosh", Icon: House },
  { key: "chat", to: "/chat", label: "AI CFO", short: "AI CFO", Icon: MessageCircle },
  { key: "forecast", to: "/forecast", label: "Prognoz", short: "Prognoz", Icon: TrendingUp },
  { key: "calendar", to: "/calendar", label: "To'lovlar kalendari", short: "Kalendar", Icon: CalendarDays },
  { key: "files", to: "/files", label: "Fayl tahlili", short: "Fayl", Icon: FileSpreadsheet },
  { key: "knowledge", to: "/knowledge", label: "AI bilimi", short: "Bilim", Icon: Lightbulb },
  { key: "sources", to: "/sources", label: "Ma'lumotlar", short: "Ma'lumot", Icon: Database },
];

/** "+ Yangi chat" always opens a fresh conversation on the AI CFO page. */
export const newChatHref = () => `/chat?new=${Date.now()}`;

function DemoBadge() {
  return <span className="ml-2 rounded-pill bg-warning-bg px-2 py-[2px] text-12 font-bold text-warning">Demo</span>;
}

function BusinessSwitcher({ compact = false }: { compact?: boolean }) {
  const me = useMe();
  const switchBusiness = useSwitchBusiness();
  const [open, setOpen] = useState(false);
  const current = me.data?.business;
  const others = (me.data?.businesses ?? []).filter((b) => b.id !== current?.id);
  if (compact)
    return (
      <span
        title={current ? `${current.name} · ${current.city}` : ""}
        className="mx-auto grid size-10 place-items-center rounded-full bg-primary-soft text-14 font-bold text-primary"
      >
        {(current?.name ?? "?").slice(0, 1).toUpperCase()}
      </span>
    );
  return (
    <div className="relative flex flex-col gap-1">
      <button
        type="button"
        aria-haspopup="listbox"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className="flex min-h-tap w-full items-center justify-between gap-2 rounded-inner border-0 bg-transparent px-2 text-left text-14 font-semibold text-ink hover:bg-[#F2F4F7]"
      >
        <span className="flex min-w-0 items-center gap-2">
          <span className="grid size-8 shrink-0 place-items-center rounded-full bg-primary-soft text-13 font-bold text-primary">
            {(current?.name ?? "?").slice(0, 1).toUpperCase()}
          </span>
          <span className="truncate">
            {current ? `${current.name} · ${current.city}` : "…"}
            {current?.is_demo && <DemoBadge />}
          </span>
        </span>
        <ChevronDown size={16} aria-hidden="true" className="shrink-0" />
      </button>
      {open && (
        <ul
          role="listbox"
          aria-label="Biznesni tanlash"
          className="absolute bottom-full left-0 right-0 z-30 m-0 mb-1 flex list-none flex-col gap-1 rounded-inner border border-border bg-surface p-1 shadow-lg"
        >
          {others.length === 0 && <li className="px-3 py-2 text-13 text-text-4">Boshqa biznes yo'q</li>}
          {others.map((b) => (
            <li key={b.id}>
              <button
                type="button"
                role="option"
                aria-selected={false}
                className="flex min-h-tap w-full items-center rounded-lg border-0 bg-surface px-3 text-left text-14 text-text-2 hover:bg-bg"
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
    </div>
  );
}

/**
 * The one app sidebar: logo, "+ Yangi chat", navigation, chat history (AI CFO page only), business.
 * `rail`: 64px icon-only version. `locked`: no data yet — every item except "Ma'lumotlar" is disabled.
 */
export function AppSidebar({
  active,
  locked = false,
  rail = false,
  history,
  onToggle,
  onNavigate,
}: {
  active: NavKey;
  locked?: boolean;
  rail?: boolean;
  history?: ReactNode;
  onToggle?: () => void;
  onNavigate?: () => void;
}) {
  return (
    <nav
      aria-label="Asosiy menyu"
      className={cn("flex h-full min-h-0 flex-col gap-1 bg-surface py-3", rail ? "w-16 items-center px-2" : "w-full px-3")}
    >
      <div className={cn("flex items-center pb-2", rail ? "flex-col gap-2" : "justify-between gap-2 px-1")}>
        <Link to="/dashboard" onClick={onNavigate} className="flex min-h-tap items-center gap-[10px] no-underline">
          <LogoMark />
          {!rail && <span className="font-display text-[19px] font-bold text-[#0A3B22]">{appConfig.appName}</span>}
        </Link>
        {onToggle && (
          <button
            type="button"
            onClick={onToggle}
            aria-label={rail ? "Menyuni ochish" : "Menyuni yig'ish"}
            className="grid size-tap place-items-center rounded-btn text-text-3 hover:bg-[#F2F4F7]"
          >
            {rail ? <PanelLeftOpen size={20} /> : <PanelLeftClose size={20} />}
          </button>
        )}
      </div>
      {!locked && (
        <Link
          to={newChatHref()}
          onClick={onNavigate}
          aria-label="Yangi chat"
          title="Yangi chat"
          className={cn(
            "mb-2 flex min-h-tap shrink-0 items-center gap-2 rounded-btn border border-border bg-surface text-15 font-semibold text-ink no-underline hover:bg-[#F2F4F7] hover:text-ink",
            rail ? "w-tap justify-center" : "w-full px-3",
          )}
        >
          <Plus size={18} aria-hidden="true" />
          {!rail && "Yangi chat"}
        </Link>
      )}
      {NAV.map(({ key, to, label, Icon }) =>
        locked && key !== "sources" ? (
          <span
            key={key}
            aria-disabled="true"
            title={label}
            className={cn("flex min-h-tap items-center gap-3 rounded-btn text-15 text-[#98A2B3]", rail ? "w-tap justify-center" : "px-3")}
          >
            <Lock size={18} strokeWidth={2} aria-hidden="true" />
            {!rail && label}
          </span>
        ) : (
          <Link
            key={key}
            to={to}
            onClick={onNavigate}
            title={rail ? label : undefined}
            aria-label={rail ? label : undefined}
            aria-current={key === active ? "page" : undefined}
            className={cn(
              "flex min-h-tap shrink-0 items-center gap-3 rounded-btn text-15 no-underline",
              rail ? "w-tap justify-center" : "px-3",
              key === active
                ? "bg-primary-soft font-semibold text-primary hover:text-primary"
                : "text-text-2 hover:bg-[#F2F4F7] hover:text-ink",
            )}
          >
            <Icon size={20} strokeWidth={2} aria-hidden="true" />
            {!rail && label}
          </Link>
        ),
      )}
      {!rail && history ? (
        <div className="mt-3 flex min-h-0 flex-1 flex-col border-t border-border-subtle pt-3">{history}</div>
      ) : (
        <div className="min-h-6 grow" />
      )}
      <div className={cn("border-t border-border-subtle pt-2", rail && "w-full")}>
        <BusinessSwitcher compact={rail} />
      </div>
    </nav>
  );
}
