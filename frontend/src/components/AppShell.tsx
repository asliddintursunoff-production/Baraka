import type { ReactNode } from "react";

import { AppSidebar, type NavKey } from "./AppSidebar";

/** Sidebar `flex: 1 1 240px` + content `flex: 999 1 560px` in a wrapping row (DESIGN.md). */
export function AppShell({ active, children }: { active: NavKey; children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-wrap bg-bg font-sans text-ink">
      <AppSidebar active={active} />
      <main className="box-border flex min-w-0 flex-[999_1_560px] flex-col gap-6 px-4 pb-12 pt-7 md:px-9">
        {children}
      </main>
    </div>
  );
}
