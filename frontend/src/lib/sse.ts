/**
 * Server-Sent Events over POST. `EventSource` can only GET, so the chat uses fetch + a
 * ReadableStream reader and this small parser (WHATWG "event stream" rules: `event:`/`data:`
 * fields, multi-line data joined with "\n", `:` comments, CRLF/CR/LF line endings, frames
 * dispatched on a blank line, chunk boundaries anywhere — even inside a UTF-8 character).
 */
import { ApiError } from "./api";

export interface SseFrame {
  event: string;
  data: string;
}

/** Same cookie logic as `api.ts` (Django's `csrftoken`). */
export function csrfToken(): string {
  if (typeof document === "undefined") return "";
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match?.[1] ? decodeURIComponent(match[1]) : "";
}

export class SseParser {
  private buf = "";
  private event = "";
  private data: string[] = [];
  private started = false;

  constructor(private readonly onFrame: (frame: SseFrame) => void) {}

  push(chunk: string): void {
    if (!this.started && chunk.length > 0) {
      this.started = true;
      if (chunk.charCodeAt(0) === 0xfeff) chunk = chunk.slice(1);
    }
    this.buf += chunk;
    let start = 0;
    for (let i = 0; i < this.buf.length; i++) {
      const c = this.buf[i];
      if (c !== "\n" && c !== "\r") continue;
      // A trailing "\r" may be the first half of "\r\n": wait for the next chunk.
      if (c === "\r" && i === this.buf.length - 1) break;
      this.line(this.buf.slice(start, i));
      if (c === "\r" && this.buf[i + 1] === "\n") i++;
      start = i + 1;
    }
    this.buf = this.buf.slice(start);
  }

  /** End of stream. Unlike EventSource, a last frame without the closing blank line is still dispatched. */
  end(): void {
    if (this.buf) this.line(this.buf.replace(/\r$/, ""));
    this.buf = "";
    this.dispatch();
  }

  private line(line: string): void {
    if (line === "") {
      this.dispatch();
      return;
    }
    if (line.startsWith(":")) return;
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    let value = colon === -1 ? "" : line.slice(colon + 1);
    if (value.startsWith(" ")) value = value.slice(1);
    if (field === "event") this.event = value;
    else if (field === "data") this.data.push(value);
    // `id` and `retry` only matter for EventSource reconnection; ignored here.
  }

  private dispatch(): void {
    if (this.data.length > 0) this.onFrame({ event: this.event || "message", data: this.data.join("\n") });
    this.event = "";
    this.data = [];
  }
}

function abortError(): DOMException {
  return new DOMException("The operation was aborted.", "AbortError");
}

/** Reads a byte stream to the end, calling `onFrame` for every SSE frame. */
export async function readSse(
  stream: ReadableStream<Uint8Array>,
  onFrame: (frame: SseFrame) => void,
  signal?: AbortSignal,
): Promise<void> {
  const reader = stream.getReader();
  const decoder = new TextDecoder("utf-8");
  const parser = new SseParser(onFrame);
  const cancel = () => void reader.cancel().catch(() => undefined);
  signal?.addEventListener("abort", cancel, { once: true });
  try {
    for (;;) {
      if (signal?.aborted) throw abortError();
      const { done, value } = await reader.read();
      if (signal?.aborted) throw abortError();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    parser.end();
  } finally {
    signal?.removeEventListener("abort", cancel);
    reader.releaseLock();
  }
}

export type SseHandlers<E> = { [K in keyof E]?: (data: E[K]) => void };

/**
 * POST `body` as JSON and stream the SSE response. Each frame's data is JSON-decoded and passed
 * to `handlers[event]`; frames with unknown names or invalid JSON are skipped. Resolves when the
 * stream ends; rejects with `ApiError` on a non-2xx response and with an `AbortError` when `signal` aborts.
 */
export async function postSse<E extends object>(
  url: string,
  body: unknown,
  handlers: SseHandlers<E>,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(url, {
    method: "POST",
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "X-CSRFToken": csrfToken(),
    },
    body: JSON.stringify(body ?? {}),
    signal,
  });
  if (!res.ok) {
    const data: unknown = await res.json().catch(() => null);
    throw new ApiError(res.status, data);
  }
  if (!res.body) throw new Error("Empty event stream");
  const table = handlers as Record<string, ((data: unknown) => void) | undefined>;
  await readSse(
    res.body,
    ({ event, data }) => {
      if (!Object.prototype.hasOwnProperty.call(table, event)) return;
      let parsed: unknown;
      try {
        parsed = data === "" ? null : JSON.parse(data);
      } catch {
        return;
      }
      table[event]?.(parsed);
    },
    signal,
  );
}
