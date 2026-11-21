import type { ReactNode } from "react";

import { useMe } from "@/lib/auth";

import { AppSidebar, type NavKey } from "./AppSidebar";
import { Gate } from "./Gate";
import { ReviewGate } from "./Reconciliation";

/** Sidebar `flex: 1 1 240px` + content `flex: 999 1 560px` in a wrapping row (DESIGN.md). */
export function AppShell({ active, children }: { active: NavKey; children: ReactNode }) {
  const me = useMe();
  // "No data, no answer": until a source is confirmed + synced, only "Ma'lumotlar" works.
  const status = me.data?.data_status;
  const locked = (status === "no_data" || status === "needs_review") && active !== "sources";
  return (
    <div className="flex min-h-screen flex-wrap bg-bg font-sans text-ink">
      <AppSidebar active={active} locked={status === "no_data" || status === "needs_review"} />
      <main className="box-border flex min-w-0 flex-[999_1_560px] flex-col gap-6 px-4 pb-12 pt-7 md:px-9">
        {locked ? status === "needs_review" ? <ReviewGate /> : <Gate state="nodata" /> : children}
      </main>
    </div>
  );
}
