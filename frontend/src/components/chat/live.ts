import { prefetchLiveToken } from "@/live/tokenCache";

/**
 * Warm up the live session on hover/focus of a "Jonli" link (fire and forget, P3). The token
 * cache deduplicates repeated calls and refreshes the token in the background.
 */
export function prefetchLive(): void {
  void prefetchLiveToken();
}
