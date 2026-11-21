/**
 * Live session token cache (LATENCY.md P3: pre-warm).
 *
 * - `prefetchLiveToken()`: GET /api/live/session/prefetch (deduplicated), keeps the result in
 *   module memory and refreshes it in the background ~60 s before `new_session_expires_at`.
 * - `takeLiveToken()`: hands out the cached token, or mints a fresh one with
 *   POST /api/live/session. A token opens only ONE session, so it is cleared once taken.
 *
 * - Budget: HTTP 429 from either endpoint ({error:"budget", message}) is remembered for the
 *   page's lifetime; no more prefetches or mints, `takeLiveToken()` throws `LiveBudgetError`.
 *
 * No React and no `window` access at import time: the Chat page imports this on hover.
 */
import { ApiError, apiGet, apiPost } from "@/lib/api";

import type { TokenResponse } from "./voiceClient";

export interface LiveSession extends TokenResponse {
  /** A new session must be opened with this token before this time (ISO). */
  new_session_expires_at: string;
  business_name: string;
  cash: { label: string; display: string };
  /** Set by `takeLiveToken()` (client side only): true when the token came from the cache. */
  from_cache?: boolean;
}

export const PREFETCH_URL = "/api/live/session/prefetch";
export const SESSION_URL = "/api/live/session";
/** Refresh a cached token this long before its new-session window closes. */
export const REFRESH_LEAD_MS = 60_000;
/** A cached token is handed out only with at least this much of its window left. */
export const MIN_VALID_MS = 15_000;
/** Background refreshes after the last explicit prefetch (bounds minting on an idle tab). */
export const MAX_AUTO_REFRESHES = 3;
/** After a failed prefetch, hover/focus does not retry for this long. */
export const RETRY_AFTER_FAIL_MS = 10_000;

let ready: LiveSession | null = null;
let pending: Promise<LiveSession | null> | null = null;
let timer: ReturnType<typeof setTimeout> | undefined;
/** Bumped whenever the cache is dropped, so a late response is not stored. */
let generation = 0;
let refreshesLeft = 0;
let failedAt = Number.NEGATIVE_INFINITY;
/** Message of a 429 budget response (daily voice limit reached); null = allowed. */
let budget: string | null = null;

const BUDGET_FALLBACK = "Bugungi ovoz limiti tugadi";

/** The daily voice limit was reached: show `message`, do not connect, do not retry. */
export class LiveBudgetError extends Error {}

/** Records a 429 and returns its message, or null for any other error. */
function noteBudget(err: unknown): string | null {
  if (!(err instanceof ApiError) || err.status !== 429) return null;
  const body = err.body as { message?: unknown } | null;
  budget = body && typeof body.message === "string" && body.message ? body.message : BUDGET_FALLBACK;
  return budget;
}

/** Set once the backend answered 429 (budget); the Live page shows it instead of connecting. */
export function liveBudgetMessage(): string | null {
  return budget;
}

function remainingMs(s: LiveSession, now = Date.now()): number {
  const until = Date.parse(s.new_session_expires_at);
  return Number.isFinite(until) ? until - now : -1;
}

/** True when the token can still open a new session (with a safety margin). */
export function isUsable(s: LiveSession | null | undefined, now = Date.now()): s is LiveSession {
  return !!s && s.ok !== false && !!s.token && remainingMs(s, now) > MIN_VALID_MS;
}

function scheduleRefresh(s: LiveSession): void {
  if (timer !== undefined) clearTimeout(timer);
  timer = undefined;
  if (refreshesLeft <= 0) return;
  const left = remainingMs(s);
  // Normally 60 s before the window closes; with a short window, halfway through it.
  const delay = Math.max(left - REFRESH_LEAD_MS, left / 2, 0);
  timer = setTimeout(() => {
    timer = undefined;
    refreshesLeft -= 1;
    void load();
  }, delay);
}

/** One GET. Resolves to the session (or null on failure); never rejects. */
function load(): Promise<LiveSession | null> {
  const gen = generation;
  const p = apiGet<LiveSession>(PREFETCH_URL).then(
    (s) => {
      if (gen === generation) {
        pending = null;
        if (isUsable(s)) {
          ready = s;
          scheduleRefresh(s);
        }
      }
      return s;
    },
    (err: unknown) => {
      noteBudget(err);
      if (gen === generation) {
        pending = null;
        failedAt = Date.now();
      }
      return null;
    },
  );
  pending = p;
  return p;
}

/** Drop the cached token, any in-flight prefetch and the refresh timer. */
function drop(): void {
  generation += 1;
  ready = null;
  pending = null;
  if (timer !== undefined) clearTimeout(timer);
  timer = undefined;
}

/**
 * Warm up a Live token (hover/focus of "Jonli gaplashish"). Fire and forget: resolves to the
 * cached session, or null when the prefetch failed. Repeated calls do not mint again.
 */
export function prefetchLiveToken(): Promise<LiveSession | null> {
  if (budget) return Promise.resolve(null);
  refreshesLeft = MAX_AUTO_REFRESHES;
  if (isUsable(ready)) return Promise.resolve(ready);
  if (pending) return pending;
  if (Date.now() - failedAt < RETRY_AFTER_FAIL_MS) return Promise.resolve(null);
  ready = null;
  return load();
}

/**
 * A valid, unused token for a new Live session: the prefetched one (also when its prefetch is
 * still in flight) or a freshly minted one. The cache is cleared synchronously, so two callers
 * never get the same single-use token.
 */
export async function takeLiveToken(): Promise<LiveSession> {
  if (budget) throw new LiveBudgetError(budget);
  const claimed: LiveSession | Promise<LiveSession | null> | null = isUsable(ready) ? ready : pending;
  drop();
  const cachedSession = await claimed;
  if (isUsable(cachedSession)) return { ...cachedSession, from_cache: true };
  if (budget) throw new LiveBudgetError(budget); // the prefetch got 429: do not mint
  let fresh: LiveSession;
  try {
    fresh = await apiPost<LiveSession>(SESSION_URL, {});
  } catch (err) {
    const msg = noteBudget(err);
    throw msg ? new LiveBudgetError(msg) : err;
  }
  if (!fresh?.ok || !fresh.token) throw new Error("Jonli suhbatni ochib bo'lmadi");
  return { ...fresh, from_cache: false };
}

/** Tests and logout: forget everything. */
export function resetLiveTokenCache(): void {
  drop();
  refreshesLeft = 0;
  failedAt = Number.NEGATIVE_INFINITY;
  budget = null;
}
