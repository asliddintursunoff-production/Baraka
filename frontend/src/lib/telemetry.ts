/** Batches latency events and sends them to POST /api/telemetry (LatencyEvent). */
import { apiPost } from "./api";

export type Channel = "voice" | "chat" | "api";
interface Event {
  channel: Channel;
  name: string;
  ms: number;
  meta?: Record<string, unknown>;
}

const queue: Event[] = [];
let timer: number | undefined;

export function track(channel: Channel, name: string, ms: number, meta?: Record<string, unknown>) {
  queue.push({ channel, name, ms: Math.round(ms * 10) / 10, meta });
  if (timer === undefined) timer = window.setTimeout(flush, 2000);
}

export function flush(): void {
  timer = undefined;
  if (queue.length === 0) return;
  const events = queue.splice(0, queue.length);
  apiPost("/api/telemetry", { events }, { keepalive: true }).catch(() => {
    /* telemetry is best-effort */
  });
}

window.addEventListener("pagehide", flush);
