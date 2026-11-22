import { Ellipsis, Menu, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";

import { useMe } from "@/lib/auth";
import { cn } from "@/lib/utils";

import { AppSidebar, NAV, type NavKey } from "./AppSidebar";
import { Gate } from "./Gate";
import { ReviewGate } from "./Reconciliation";

const RAIL_KEY = "sidebar-rail";
const TABS: NavKey[] = ["main", "chat", "forecast", "calendar"];

function readRail(): boolean {
  try {
    return localStorage.getItem(RAIL_KEY) === "1";
  } catch {
    return false;
  }
}

/** Left drawer (tablet history / mobile ☰) with the full sidebar inside. */
function Drawer({ open, onClose, children }: { open: boolean; onClose: () => void; children: ReactNode }) {
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 lg:hidden" role="dialog" aria-modal="true" aria-label="Menyu">
      <button type="button" aria-label="Yopish" onClick={onClose} className="absolute inset-0 border-0 bg-black/40" />
      <div className="absolute inset-y-0 left-0 flex w-[300px] max-w-[85vw] flex-col bg-surface shadow-xl">
        <button
          type="button"
          onClick={onClose}
          aria-label="Menyuni yopish"
          className="absolute right-2 top-2 z-10 grid size-tap place-items-center rounded-btn text-text-3 hover:bg-[#F2F4F7]"
        >
          <X size={20} />
        </button>
        {children}
      </div>
    </div>
  );
}

/** "Ko'proq" bottom sheet on mobile: the nav items that don't fit the tab bar. */
function MoreSheet({ open, onClose, active }: { open: boolean; onClose: () => void; active: NavKey }) {
  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 md:hidden" role="dialog" aria-modal="true" aria-label="Ko'proq">
      <button type="button" aria-label="Yopish" onClick={onClose} className="absolute inset-0 border-0 bg-black/40" />
      <div className="absolute inset-x-0 bottom-0 flex flex-col gap-1 rounded-t-card bg-surface p-4 pb-[calc(16px+env(safe-area-inset-bottom))]">
        <span className="mx-auto mb-2 h-1 w-10 rounded-full bg-border" aria-hidden="true" />
        {NAV.filter((n) => !TABS.includes(n.key)).map(({ key, to, label, Icon }) => (
          <Link
            key={key}
            to={to}
            onClick={onClose}
            aria-current={key === active ? "page" : undefined}
            className={cn(
              "flex min-h-12 items-center gap-3 rounded-btn px-3 text-16 no-underline",
              key === active ? "bg-primary-soft font-semibold text-primary" : "text-ink hover:bg-[#F2F4F7]",
            )}
          >
            <Icon size={20} aria-hidden="true" />
            {label}
          </Link>
        ))}
      </div>
    </div>
  );
}

function TabBar({ active, onMore }: { active: NavKey; onMore: () => void }) {
  const more = !TABS.includes(active);
  return (
    <nav
      aria-label="Pastki menyu"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-border bg-surface pb-[env(safe-area-inset-bottom)] md:hidden"
    >
      {NAV.filter((n) => TABS.includes(n.key)).map(({ key, to, short, Icon }) => (
        <Link
          key={key}
          to={to}
          aria-current={key === active ? "page" : undefined}
          className={cn(
            "flex h-tabbar flex-1 flex-col items-center justify-center gap-0.5 text-12 font-semibold no-underline",
            key === active ? "text-primary hover:text-primary" : "text-text-3 hover:text-ink",
          )}
        >
          <Icon size={22} aria-hidden="true" />
          {short}
        </Link>
      ))}
      <button
        type="button"
        onClick={onMore}
        className={cn(
          "flex h-tabbar flex-1 flex-col items-center justify-center gap-0.5 border-0 bg-transparent text-12 font-semibold",
          more ? "text-primary" : "text-text-3",
        )}
      >
        <Ellipsis size={22} aria-hidden="true" />
        Ko'proq
      </button>
    </nav>
  );
}

/**
 * App frame. lg (≥1024): one 260px sidebar (collapsible to a 64px rail, remembered).
 * md (768–1023): 64px rail + drawer. sm (<768): 52px top bar + ☰ drawer + bottom tab bar.
 * `bleed`: the page draws its own header/padding (AI CFO). `history`: chat list for the sidebar.
 * `action`: the page's main action in the mobile top bar. `hideTabs`: no tab bar (open chat thread).
 */
export function AppShell({
  active,
  children,
  history,
  bleed = false,
  action,
  hideTabs = false,
}: {
  active: NavKey;
  children: ReactNode;
  history?: ReactNode;
  bleed?: boolean;
  action?: ReactNode;
  hideTabs?: boolean;
}) {
  const me = useMe();
  const [rail, setRail] = useState(readRail);
  const [drawer, setDrawer] = useState(false);
  const [more, setMore] = useState(false);
  // "No data, no answer": until a source is confirmed + synced, only "Ma'lumotlar" works.
  const status = me.data?.data_status;
  const noData = status === "no_data" || status === "needs_review";
  const locked = noData && active !== "sources";
  const title = NAV.find((n) => n.key === active)?.label ?? "";
  const toggleRail = () =>
    setRail((v) => {
      try {
        localStorage.setItem(RAIL_KEY, v ? "0" : "1");
      } catch {
        /* private mode: the toggle just isn't remembered */
      }
      return !v;
    });
  const close = () => setDrawer(false);

  return (
    <div className="flex min-h-dvh bg-bg font-sans text-ink">
      {/* desktop sidebar / tablet rail */}
      <aside
        className={cn(
          "sticky top-0 hidden h-dvh shrink-0 border-r border-border md:block",
          rail ? "lg:w-rail" : "lg:w-sidebar",
          "md:w-rail",
        )}
      >
        <div className="hidden h-full lg:block">
          <AppSidebar active={active} locked={noData} rail={rail} history={history} onToggle={toggleRail} />
        </div>
        <div className="h-full lg:hidden">
          <AppSidebar active={active} locked={noData} rail onToggle={() => setDrawer(true)} />
        </div>
      </aside>

      <Drawer open={drawer} onClose={close}>
        <AppSidebar active={active} locked={noData} history={history} onNavigate={close} />
      </Drawer>
      <MoreSheet open={more} onClose={() => setMore(false)} active={active} />

      <div className="flex min-w-0 flex-1 flex-col">
        {/* mobile top bar */}
        <header className="sticky top-0 z-30 grid h-topbar grid-cols-[44px_1fr_auto] items-center gap-2 border-b border-border bg-surface px-2 md:hidden">
          <button
            type="button"
            onClick={() => setDrawer(true)}
            aria-label="Menyu"
            className="grid size-tap place-items-center rounded-btn border-0 bg-transparent text-ink"
          >
            <Menu size={22} />
          </button>
          <span className="truncate text-center text-16 font-semibold">{title}</span>
          <div className="flex min-w-tap justify-end">{action}</div>
        </header>

        <main
          className={cn(
            "box-border flex min-w-0 flex-1 flex-col",
            !bleed && "gap-6 px-4 pb-12 pt-6 md:px-6 lg:px-9 lg:pt-7",
            !hideTabs && "pb-[calc(theme(spacing.tabbar)+env(safe-area-inset-bottom)+16px)] md:pb-12",
          )}
        >
          {me.data?.freshness?.banner && (
            <div
              role="status"
              className={cn(
                "rounded-inner border border-[#FEDF89] bg-warning-bg px-4 py-3 text-14 font-semibold text-warning",
                bleed && "m-4",
              )}
            >
              {me.data.freshness.banner}
            </div>
          )}
          {locked ? status === "needs_review" ? <ReviewGate /> : <Gate state="nodata" /> : children}
        </main>
      </div>
      {!hideTabs && <TabBar active={active} onMore={() => setMore(true)} />}
    </div>
  );
}
