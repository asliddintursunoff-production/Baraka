import { AppShell } from "@/components/AppShell";
import type { NavKey } from "@/components/AppSidebar";

/** Routes whose screens arrive in later milestones. */
export default function Placeholder({ active, title }: { active: NavKey; title: string }) {
  return (
    <AppShell active={active}>
      <h1 className="m-0 font-display text-30 font-bold">{title}</h1>
      <p className="m-0 text-16 text-text-3">Bu sahifa keyingi bosqichda tayyor bo'ladi.</p>
    </AppShell>
  );
}
