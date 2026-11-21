import { useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { BTN_SECONDARY } from "@/components/sources/shared";
import { ApiError, apiPost } from "@/lib/api";
import type { Me } from "@/lib/types";

/** True for the backend's `409 {"code": "no_data"}` (no confirmed + synced source yet). */
export function isNoData(error: unknown): boolean {
  return (
    error instanceof ApiError &&
    error.status === 409 &&
    (error.body as { code?: string } | null)?.code === "no_data"
  );
}

const BIG_PRIMARY =
  "inline-flex min-h-[52px] items-center gap-[10px] rounded-btn-lg bg-primary px-6 text-16 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white";
const BIG_SECONDARY = `${BTN_SECONDARY} min-h-[52px] rounded-btn-lg px-[22px] text-16`;

/** "Demo kafe bilan sinab ko'rish": the user's own separate demo business (POST /api/demo/start). */
export function useStartDemo() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const startDemo = async () => {
    setBusy(true);
    setError(null);
    try {
      const next = await apiPost<Me>("/api/demo/start", {});
      qc.setQueryData(["me"], next);
      await qc.invalidateQueries({ predicate: (q) => q.queryKey[0] !== "me" });
      navigate("/dashboard");
    } catch (err) {
      const msg = err instanceof ApiError ? (err.body as { message?: string } | null)?.message : null;
      setError(msg ?? "Internet aloqasini tekshiring va qaytadan urinib ko'ring.");
    } finally {
      setBusy(false);
    }
  };
  return { startDemo, busy, error };
}

function NoDataGate() {
  const { startDemo, busy, error } = useStartDemo();

  return (
    <div className="flex w-full flex-col items-center gap-6">
      <section
        aria-label="Ma'lumot ulanmagan"
        className="box-border flex w-full max-w-[760px] flex-col items-center gap-[18px] rounded-[20px] border border-border bg-surface p-10 text-center"
      >
        <span className="flex h-16 w-16 items-center justify-center rounded-[32px] bg-primary-soft">
          <svg width="30" height="30" viewBox="0 0 24 24" aria-hidden="true">
            <rect x="4" y="2" width="16" height="20" rx="2" fill="#067647" />
            <path d="M8 9h8M8 13h8M8 17h8M12 9v8" stroke="#FFFFFF" strokeWidth="1.6" />
          </svg>
        </span>
        <h1 className="m-0 font-display text-30 font-bold">Avval jadvallaringizni ulang</h1>
        <p className="m-0 max-w-[540px] text-17 leading-[1.6] text-text-2">
          AI faqat sizning haqiqiy ma'lumotingiz asosida javob beradi. Ma'lumotsiz u taxmin qilmaydi — shuning
          uchun prognoz, chat va ovoz ulanishdan keyin ochiladi.
        </p>
        <div className="flex flex-wrap justify-center gap-3 pt-[6px]">
          <Link to="/onboarding/connect" className={BIG_PRIMARY}>
            Google Sheets ulash
          </Link>
          <button type="button" disabled={busy} onClick={() => void startDemo()} className={BIG_SECONDARY}>
            Demo kafe bilan sinab ko'rish
          </button>
        </div>
        {error && (
          <p role="alert" className="m-0 text-14 text-danger">
            {error}
          </p>
        )}
        <span className="text-14 text-text-4">
          Excel faylingiz bo'lsa, uni Google Drive'ga yuklang va ulashda tanlang.
        </span>
      </section>
      <div className="box-border flex w-full max-w-[760px] items-center gap-[10px] rounded-card border border-dashed border-border-input bg-surface py-2 pl-4 pr-2">
        <label htmlFor="gate-ask" className="sr-only">
          AI CFO'ga savol
        </label>
        <input
          id="gate-ask"
          type="text"
          disabled
          placeholder="AI jadvalingiz ulangandan keyin javob beradi"
          className="min-h-tap min-w-0 grow border-0 bg-transparent font-sans text-15 text-text-4"
        />
      </div>
    </div>
  );
}

function ShortGate({ days }: { days: number }) {
  const pct = Math.round((Math.min(Math.max(days, 0), 14) / 14) * 100);
  return (
    <section
      aria-label="Ma'lumot yetarli emas"
      className="box-border flex w-full max-w-[760px] flex-col gap-4 self-center rounded-[20px] border border-[#FEDF89] bg-surface p-8"
    >
      <span className="self-start rounded-pill bg-warning-bg px-3 py-[5px] text-14 font-bold text-warning">
        Ma'lumot hali kam
      </span>
      <h1 className="m-0 font-display text-26 font-bold">Ishonchli prognoz uchun kamida 2 haftalik ma'lumot kerak</h1>
      <p className="m-0 text-16 leading-[1.6] text-text-2">
        Jadvalingizda hozir {days} kunlik yozuv bor. AI taxminiy raqam ko'rsatmaydi — yetarli ma'lumot yig'ilganda
        prognoz o'zi ochiladi.
      </p>
      <div
        role="progressbar"
        aria-label="Yig'ilgan ma'lumot"
        aria-valuemin={0}
        aria-valuemax={14}
        aria-valuenow={days}
        className="h-[10px] overflow-hidden rounded-[5px] bg-border"
      >
        <div className="h-full bg-warning-accent" style={{ width: `${pct}%` }} />
      </div>
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-3">
        <div className="flex flex-col gap-1 rounded-inner bg-success-bg p-[14px]">
          <span className="text-13 font-bold text-success">Hozir ishlaydi</span>
          <span className="text-15 leading-[1.45]">To'lovlar kalendari, kelgusi majburiy to'lovlar, joriy kassa</span>
        </div>
        <div className="flex flex-col gap-1 rounded-inner bg-bg p-[14px]">
          <span className="text-13 font-bold text-text-3">Keyin ochiladi</span>
          <span className="text-15 leading-[1.45]">60 kunlik prognoz, "Agar...?" va xarid qarorlari</span>
        </div>
      </div>
      <span className="text-14 text-text-3">Tezlashtirish: eski oylar jadvali bo'lsa, uni ham ulang.</span>
    </section>
  );
}

/** Gate.html: `nodata` (nothing connected) or `short` (under 14 days of history). */
export function Gate({ state, days = 0 }: { state: "nodata" | "short"; days?: number }) {
  return state === "nodata" ? <NoDataGate /> : <ShortGate days={days} />;
}
