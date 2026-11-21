import type { ReactNode } from "react";

import { useMe } from "@/lib/auth";

import { AppSidebar, type NavKey } from "./AppSidebar";
import { Gate } from "./Gate";

/** Sidebar `flex: 1 1 240px` + content `flex: 999 1 560px` in a wrapping row (DESIGN.md). */
export function AppShell({ active, children }: { active: NavKey; children: ReactNode }) {
  const me = useMe();
  // "No data, no answer": until a source is confirmed + synced, only "Ma'lumotlar" works.
  const locked = me.data?.data_status === "no_data" && active !== "sources";
  return (
    <div className="flex min-h-screen flex-wrap bg-bg font-sans text-ink">
      <AppSidebar active={active} locked={me.data?.data_status === "no_data"} />
      <main className="box-border flex min-w-0 flex-[999_1_560px] flex-col gap-6 px-4 pb-12 pt-7 md:px-9">
        {locked ? <Gate state="nodata" /> : children}
      </main>
    </div>
  );
}
