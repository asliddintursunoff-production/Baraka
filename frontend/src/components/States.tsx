import { Link } from "react-router-dom";

import { ApiError } from "@/lib/api";

import { Gate, isNoData } from "./Gate";
import { type QualityPayload, ReviewGate } from "./Reconciliation";

export function Skeleton({ className = "" }: { className?: string }) {
  return <div className={`animate-pulse rounded-inner bg-[#EAECF0] ${className}`} aria-hidden="true" />;
}

export function PageSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Yuklanmoqda">
      <Skeleton className="h-10 w-80 max-w-full" />
      <Skeleton className="h-28" />
      <div className="grid grid-cols-[repeat(auto-fit,minmax(220px,1fr))] gap-4">
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
        <Skeleton className="h-28" />
      </div>
      <Skeleton className="h-80" />
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  if (isNoData(error)) return <Gate state="nodata" />;
  if (error instanceof ApiError && error.status === 409 && (error.body as { code?: string } | null)?.code === "needs_review") {
    const body = error.body as { message?: string; recon?: QualityPayload["recon"] };
    return <ReviewGate message={body.message} recon={body.recon} />;
  }
  const offline = !(error instanceof ApiError);
  return (
    <section
      role="alert"
      className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6"
    >
      <h2 className="m-0 font-display text-20 font-bold">Ma'lumotni yuklab bo'lmadi</h2>
      <p className="m-0 text-15 text-text-3">
        {offline
          ? "Internet aloqasini tekshiring va qaytadan urinib ko'ring."
          : "Serverda xato yuz berdi. Bir daqiqadan keyin qaytadan urinib ko'ring."}
      </p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="min-h-tap self-start rounded-btn bg-primary px-[18px] text-15 font-semibold text-white hover:bg-primary-hover"
        >
          Qayta urinish
        </button>
      )}
    </section>
  );
}

export function EmptyState() {
  return (
    <section className="flex flex-col gap-3 rounded-card border border-border bg-surface p-6">
      <h2 className="m-0 font-display text-20 font-bold">Jadvalingizni ulang</h2>
      <p className="m-0 text-15 text-text-3">
        Google Sheets jadvalingizni bir marta ulang — keyin prognoz o'zi yangilanib boradi.
      </p>
      <Link
        to="/onboarding/connect"
        className="inline-flex min-h-tap items-center self-start rounded-btn bg-primary px-[18px] text-15 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white"
      >
        Jadvalni ulash
      </Link>
    </section>
  );
}

export function InsufficientData() {
  return (
    <p className="m-0 rounded-inner bg-warning-bg p-4 text-15 font-semibold text-warning">
      Ishonchli prognoz uchun kamida 2 haftalik ma'lumot kerak
    </p>
  );
}
