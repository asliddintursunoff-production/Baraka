import type { ReactNode } from "react";
import { Link } from "react-router-dom";

import { LogoMark } from "@/components/LogoMark";
import { ApiError } from "@/lib/api";
import { appConfig } from "@/lib/config";

/** Login / Register: form column + dark aside (Login.html, Register.html). */
export function AuthLayout({
  children,
  aside,
  asideLabel,
}: {
  children: ReactNode;
  aside: ReactNode;
  asideLabel: string;
}) {
  return (
    <div className="flex min-h-screen flex-wrap bg-surface font-sans text-ink">
      <main className="box-border flex min-w-0 flex-[1_1_520px] flex-col px-4 py-10 md:px-8">
        <Link to="/" className="flex items-center gap-[10px] text-ink no-underline hover:text-ink">
          <LogoMark />
          <span className="font-display text-[19px] font-bold text-[#0A3B22]">{appConfig.appName}</span>
        </Link>
        <div className="flex grow items-center justify-center py-10">{children}</div>
      </main>
      <aside
        aria-label={asideLabel}
        className="box-border flex min-w-0 flex-[1_1_420px] flex-col justify-center gap-7 bg-ink px-6 py-14 text-white md:px-12"
      >
        {aside}
      </aside>
    </div>
  );
}

export const INPUT =
  "min-h-12 rounded-btn border border-border-input px-[14px] font-sans text-16 font-normal text-ink";
export const LABEL = "text-14 font-semibold text-text-2";
export const SUBMIT =
  "inline-flex min-h-[50px] items-center justify-center gap-[10px] rounded-btn-lg border-0 bg-primary px-6 text-16 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white disabled:opacity-60";

/** Uzbek message from an API error body, or the offline text. */
export function apiMessage(err: unknown, fallback: string): string {
  if (err instanceof ApiError) {
    const msg = (err.body as { message?: string } | null)?.message;
    if (msg) return msg;
  }
  return fallback;
}
