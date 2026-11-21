import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, apiGet, apiPost } from "@/lib/api";

import {
  LiveBudgetError,
  liveBudgetMessage,
  MAX_AUTO_REFRESHES,
  PREFETCH_URL,
  prefetchLiveToken,
  REFRESH_LEAD_MS,
  resetLiveTokenCache,
  RETRY_AFTER_FAIL_MS,
  SESSION_URL,
  takeLiveToken,
  type LiveSession,
} from "./tokenCache";

vi.mock("@/lib/api", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api")>()),
  apiGet: vi.fn(),
  apiPost: vi.fn(),
}));

const get = vi.mocked(apiGet);
const post = vi.mocked(apiPost);
const WINDOW_MS = 600_000; // backend LIVE_NEW_SESSION_WINDOW_S

function session(token: string, windowMs = WINDOW_MS): LiveSession {
  const now = Date.now();
  return {
    ok: true,
    token,
    model: "gemini-3.8-live",
    expires_at: new Date(now + 30 * 60_000).toISOString(),
    new_session_expires_at: new Date(now + windowMs).toISOString(),
    behavior: "blocking",
    mint_ms: 400,
    business_name: "Test",
    cash: { label: "Hozirgi kassa", display: "1,0 mln so'm" },
  };
}

/** Each GET mints a new token: t1, t2, … */
function mintOnGet(windowMs = WINDOW_MS): void {
  let n = 0;
  get.mockImplementation(() => Promise.resolve(session(`t${++n}`, windowMs)) as never);
}

beforeEach(() => {
  vi.useFakeTimers();
  vi.setSystemTime(new Date("2026-11-21T09:00:00Z"));
  resetLiveTokenCache();
  get.mockReset();
  post.mockReset();
  post.mockImplementation(() => Promise.resolve(session("fresh")) as never);
});

afterEach(() => {
  vi.useRealTimers();
});

describe("prefetchLiveToken / takeLiveToken", () => {
  it("dedupes prefetches, hands the token out once, then mints a fresh one", async () => {
    mintOnGet();
    void prefetchLiveToken();
    void prefetchLiveToken();
    await vi.advanceTimersByTimeAsync(0);
    expect(await prefetchLiveToken()).toMatchObject({ token: "t1" });
    expect(get).toHaveBeenCalledTimes(1);
    expect(get).toHaveBeenCalledWith(PREFETCH_URL);

    expect(await takeLiveToken()).toMatchObject({ token: "t1", from_cache: true });
    // single use: the next session gets a freshly minted token
    expect(await takeLiveToken()).toMatchObject({ token: "fresh", from_cache: false });
    expect(post).toHaveBeenCalledWith(SESSION_URL, {});
  });

  it("refreshes in the background 60 s before the new-session window closes", async () => {
    mintOnGet();
    await prefetchLiveToken();
    expect(get).toHaveBeenCalledTimes(1);

    await vi.advanceTimersByTimeAsync(WINDOW_MS - REFRESH_LEAD_MS - 1);
    expect(get).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(get).toHaveBeenCalledTimes(2);

    // the refreshed token replaces the old one
    expect(await takeLiveToken()).toMatchObject({ token: "t2", from_cache: true });
    expect(post).not.toHaveBeenCalled();
  });

  it("stops auto-refreshing after MAX_AUTO_REFRESHES, and after a take", async () => {
    mintOnGet();
    await prefetchLiveToken();
    await vi.advanceTimersByTimeAsync((WINDOW_MS - REFRESH_LEAD_MS) * (MAX_AUTO_REFRESHES + 3));
    expect(get).toHaveBeenCalledTimes(1 + MAX_AUTO_REFRESHES);

    resetLiveTokenCache();
    get.mockClear();
    await prefetchLiveToken();
    await takeLiveToken();
    await vi.advanceTimersByTimeAsync(WINDOW_MS * 2);
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("does not hand out a token whose window has (almost) closed", async () => {
    mintOnGet();
    await prefetchLiveToken();
    // the clock jumps (laptop asleep) without the refresh timer firing
    vi.setSystemTime(Date.now() + WINDOW_MS - 5_000);
    expect(await takeLiveToken()).toMatchObject({ token: "fresh", from_cache: false });
  });

  it("refreshes halfway through a short window instead of looping", async () => {
    mintOnGet(60_000);
    await prefetchLiveToken();
    await vi.advanceTimersByTimeAsync(29_999);
    expect(get).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(1);
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("a take during an in-flight prefetch waits for it; a second take does not reuse it", async () => {
    let resolve: (s: LiveSession) => void = () => {};
    get.mockImplementation(() => new Promise<LiveSession>((r) => (resolve = r)) as never);
    void prefetchLiveToken();
    const first = takeLiveToken();
    const second = takeLiveToken();
    resolve(session("slow"));
    expect(await first).toMatchObject({ token: "slow", from_cache: true });
    expect(await second).toMatchObject({ token: "fresh", from_cache: false });
    expect(get).toHaveBeenCalledTimes(1);
  });

  it("falls back to POST when the prefetch failed and backs off hover retries", async () => {
    get.mockImplementation(() => Promise.reject(new Error("502")) as never);
    expect(await prefetchLiveToken()).toBeNull();
    expect(await prefetchLiveToken()).toBeNull();
    expect(get).toHaveBeenCalledTimes(1);

    expect(await takeLiveToken()).toMatchObject({ token: "fresh" });

    await vi.advanceTimersByTimeAsync(RETRY_AFTER_FAIL_MS);
    await prefetchLiveToken();
    expect(get).toHaveBeenCalledTimes(2);
  });

  it("429 budget: shows the backend message, never mints or prefetches again", async () => {
    const limit = { error: "budget", message: "Bugungi ovoz limiti tugadi" };
    get.mockImplementation(() => Promise.reject(new ApiError(429, limit)) as never);
    expect(await prefetchLiveToken()).toBeNull();
    expect(liveBudgetMessage()).toBe("Bugungi ovoz limiti tugadi");
    await expect(takeLiveToken()).rejects.toBeInstanceOf(LiveBudgetError);
    expect(post).not.toHaveBeenCalled();
    await vi.advanceTimersByTimeAsync(RETRY_AFTER_FAIL_MS * 10);
    await prefetchLiveToken();
    expect(get).toHaveBeenCalledTimes(1);

    resetLiveTokenCache();
    post.mockImplementation(() => Promise.reject(new ApiError(429, limit)) as never);
    await expect(takeLiveToken()).rejects.toThrow("Bugungi ovoz limiti tugadi");
    await expect(takeLiveToken()).rejects.toBeInstanceOf(LiveBudgetError);
    expect(post).toHaveBeenCalledTimes(1);
  });

  it("rejects when the mint itself fails", async () => {
    post.mockImplementation(() => Promise.resolve({ ok: false, error: "token_failed" }) as never);
    await expect(takeLiveToken()).rejects.toThrow();
  });
});
