import { useStartDemo } from "@/components/Gate";
import { useEffect, useRef } from "react";
import { Link } from "react-router-dom";

import type { Proposals } from "@/lib/sourcesTypes";

import { CheckIcon } from "./icons";
import { BTN_PRIMARY, BTN_SECONDARY, ErrorBox, PICK_NEXT, PrivacyNote, Spinner, startGoogleAuth } from "./shared";
import { usePickFiles, type PickError, type PickPhase } from "./usePickFiles";

const CARD =
  "flex max-w-[640px] flex-col gap-4 rounded-card border border-border bg-surface p-5 sm:p-6";
const H2 = "m-0 font-display text-20 font-bold outline-none";

/** Moves focus to the step heading when the user moved to this step (not on page load). */
export function useFocusHeading(enabled: boolean) {
  const ref = useRef<HTMLHeadingElement>(null);
  useEffect(() => {
    if (enabled) ref.current?.focus({ preventScroll: true });
  }, [enabled]);
  return ref;
}

const CALLBACK_ERRORS: Record<string, string> = {
  access_denied: "Google ruxsat bermadi. Qaytadan urinib ko'ring.",
};
const CALLBACK_FALLBACK = "Google bilan ulanib bo'lmadi. Qaytadan urinib ko'ring.";

/** `?error=<code>&message=<uz text>` from the OAuth callback. */
export function callbackError(code: string, message: string | null): string {
  const text = message?.trim().slice(0, 300);
  return text || CALLBACK_ERRORS[code] || CALLBACK_FALLBACK;
}

export function GoogleStep({
  error,
  needsReauth,
  businessName,
}: {
  error: string | null;
  needsReauth: boolean;
  businessName: string | null | undefined;
}) {
  return (
    <section aria-labelledby="connect-google" className={CARD}>
      <h2 id="connect-google" className={H2}>
        Google hisobingizni ulang
      </h2>
      <p className="m-0 text-15 leading-normal text-text-3">
        Faqat siz tanlagan jadvallarni o'qiymiz — Google Drive'dagi boshqa fayllaringizga kirmaymiz.
      </p>
      {error ? (
        <ErrorBox
          action={
            <button
              type="button"
              onClick={() => startGoogleAuth(PICK_NEXT)}
              className={`${BTN_PRIMARY} self-start`}
            >
              Qayta urinish
            </button>
          }
        >
          {error}
        </ErrorBox>
      ) : (
        <>
          {needsReauth && (
            <p className="m-0 rounded-inner bg-warning-bg p-[14px] text-15 font-semibold text-warning">
              Google ulanishi eskirdi. Davom etish uchun qayta ulang.
            </p>
          )}
          <button
            type="button"
            onClick={() => startGoogleAuth(PICK_NEXT)}
            className={`${BTN_PRIMARY} self-start`}
          >
            {needsReauth ? "Qayta ulash" : "Google bilan ulash"}
          </button>
          {!needsReauth && <DemoLink />}
        </>
      )}
      <PrivacyNote businessName={businessName} />
    </section>
  );
}

export function PickErrorBox({ error }: { error: PickError }) {
  return (
    <ErrorBox
      action={
        error.reauth ? (
          <button
            type="button"
            onClick={() => startGoogleAuth(PICK_NEXT)}
            className={`${BTN_PRIMARY} self-start`}
          >
            Qayta ulash
          </button>
        ) : undefined
      }
    >
      {error.message}
    </ErrorBox>
  );
}

export function PickStatus({ phase }: { phase: PickPhase }) {
  if (phase === "idle" || phase === "picking") return null;
  return (
    <span className="flex items-center gap-2 text-14 font-semibold text-text-2">
      <Spinner />
      {phase === "reading" ? "AI ustunlarni o'qiyapti…" : "Google Drive ochilmoqda…"}
    </span>
  );
}

export function PickStep({
  email,
  businessName,
  onProposals,
  autoFocus,
}: {
  email: string | null;
  businessName: string | null | undefined;
  onProposals: (p: Proposals) => void;
  autoFocus: boolean;
}) {
  const heading = useFocusHeading(autoFocus);
  const { phase, error, pick } = usePickFiles(onProposals);
  const busy = phase !== "idle";
  return (
    <section aria-labelledby="connect-pick" aria-busy={busy} className={CARD}>
      <h2 id="connect-pick" ref={heading} tabIndex={-1} className={H2}>
        Jadvallaringizni belgilang
      </h2>
      <p className="m-0 text-15 leading-normal text-text-3">
        Google Drive'da kassa, kirim-chiqim, oylik yoki kredit jadvallaringizni belgilang. Bir
        nechta faylni birdaniga tanlash mumkin.
      </p>
      {email && (
        <span className="flex items-center gap-2 text-14 font-semibold text-success">
          <CheckIcon strokeWidth={2.5} />
          <span className="min-w-0 break-all">{email}</span>
        </span>
      )}
      <button
        type="button"
        onClick={() => void pick()}
        disabled={busy}
        className={`${BTN_PRIMARY} self-start`}
      >
        Fayllarni tanlash
      </button>
      <div aria-live="polite">
        <PickStatus phase={phase} />
      </div>
      {error && <PickErrorBox error={error} />}
      <PrivacyNote businessName={businessName} />
    </section>
  );
}

export function DoneStep({ text, to }: { text: string; to: string }) {
  const heading = useFocusHeading(true);
  return (
    <section
      role="status"
      aria-labelledby="connect-done"
      className="flex max-w-[640px] flex-col items-start gap-4 rounded-card border border-border bg-surface p-5 sm:p-6"
    >
      <span className="flex h-11 w-11 items-center justify-center rounded-[22px] bg-success">
        <CheckIcon size={22} strokeWidth={2.6} color="#FFFFFF" />
      </span>
      <h2 id="connect-done" ref={heading} tabIndex={-1} className={H2}>
        {text}
      </h2>
      <Link to={to} replace className={BTN_PRIMARY}>
        Davom etish
      </Link>
    </section>
  );
}


function DemoLink() {
  const { startDemo, busy, error } = useStartDemo();
  return (
    <div className="flex flex-col gap-1">
      <button type="button" onClick={() => void startDemo()} disabled={busy} className={`${BTN_SECONDARY} self-start`}>
        {busy ? "Demo tayyorlanmoqda…" : "Demo kafe bilan sinab ko'rish"}
      </button>
      {error && <span className="text-13 text-danger">{error}</span>}
    </div>
  );
}
