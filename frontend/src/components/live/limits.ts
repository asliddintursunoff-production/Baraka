/** Live voice budget rules: the session (and the mic) closes automatically. */

/** No user speech and no model audio for this long. */
export const LIVE_IDLE_CLOSE_MS = 30_000;
/** Hard cap on one Live session. */
export const LIVE_MAX_SESSION_MS = 300_000;

export type LiveCloseReason = "idle" | "hidden" | "max";

export const LIVE_CLOSE_NOTE: Record<LiveCloseReason, string> = {
  idle: `${LIVE_IDLE_CLOSE_MS / 1000} soniya jimlik bo'ldi, mikrofon o'chirildi.`,
  hidden: "Boshqa oynaga o'tdingiz, mikrofon o'chirildi.",
  max: `Suhbat ${LIVE_MAX_SESSION_MS / 60_000} daqiqaga yetdi, mikrofon o'chirildi.`,
};
