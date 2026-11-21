import { apiGet } from "@/lib/api";

const PREFETCH_EVERY_MS = 10_000;
let lastPrefetch = 0;

/** Warm up the live session on hover/focus of a "Jonli" link (fire and forget, M4). */
export function prefetchLive(): void {
  const now = Date.now();
  if (now - lastPrefetch < PREFETCH_EVERY_MS) return;
  lastPrefetch = now;
  apiGet("/api/live/session/prefetch").catch(() => undefined);
}
