import { afterEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./api";
import { postSse, readSse, SseParser, type SseFrame } from "./sse";

function parseChunks(chunks: string[]): SseFrame[] {
  const frames: SseFrame[] = [];
  const p = new SseParser((f) => frames.push(f));
  chunks.forEach((c) => p.push(c));
  p.end();
  return frames;
}

function byteStream(chunks: Uint8Array[]): ReadableStream<Uint8Array> {
  return new ReadableStream({
    start(controller) {
      chunks.forEach((c) => controller.enqueue(c));
      controller.close();
    },
  });
}

/** Splits a string into byte chunks of `size` bytes (so multi-byte characters get cut). */
function bytesOf(text: string, size: number): Uint8Array[] {
  const all = new TextEncoder().encode(text);
  const out: Uint8Array[] = [];
  for (let i = 0; i < all.length; i += size) out.push(all.slice(i, i + size));
  return out;
}

const STREAM =
  'event: meta\ndata: {"conversation_id": 12, "user_message_id": 40}\n\n' +
  'event: status\ndata: {"text": "Hisoblayapman…"}\n\n' +
  ": keep-alive comment\n\n" +
  'event: blocks\ndata: {"blocks": [{"id": "b1", "type": "kpi"}], "replace": true}\n\n' +
  'event: answer\ndata: {"headline": "Yo\'q, hozir olmang.",\ndata:  "verdict": "no"}\n\n' +
  'event: done\ndata: {"message_id": 41, "latency_ms": 900, "model": "template"}\n\n';

describe("SseParser", () => {
  it("parses whole frames", () => {
    const frames = parseChunks([STREAM]);
    expect(frames.map((f) => f.event)).toEqual(["meta", "status", "blocks", "answer", "done"]);
    expect(JSON.parse(frames[3]!.data)).toEqual({ headline: "Yo'q, hozir olmang.", verdict: "no" });
  });

  it("gives the same result for every possible split point", () => {
    const whole = parseChunks([STREAM]);
    for (let i = 1; i < STREAM.length; i++) {
      expect(parseChunks([STREAM.slice(0, i), STREAM.slice(i)])).toEqual(whole);
    }
  });

  it("handles one-character chunks", () => {
    expect(parseChunks(STREAM.split(""))).toEqual(parseChunks([STREAM]));
  });

  it("joins multi-line data with newlines and strips one leading space", () => {
    const frames = parseChunks(["data: a\ndata:b\ndata:  c\n\n"]);
    expect(frames).toEqual([{ event: "message", data: "a\nb\n c" }]);
  });

  it("accepts CRLF and CR line endings, including CRLF split across chunks", () => {
    const frames = parseChunks(["event: x\r", "\ndata: 1\r", "\r", "event: y\rdata: 2\r\r"]);
    expect(frames).toEqual([
      { event: "x", data: "1" },
      { event: "y", data: "2" },
    ]);
  });

  it("ignores frames without data and resets the event name after each frame", () => {
    const frames = parseChunks(["event: ping\n\n", "data: 3\n\n"]);
    expect(frames).toEqual([{ event: "message", data: "3" }]);
  });

  it("dispatches a last frame that has no closing blank line", () => {
    expect(parseChunks(['event: done\ndata: {"message_id": 1}'])).toEqual([
      { event: "done", data: '{"message_id": 1}' },
    ]);
  });

  it("strips a leading BOM", () => {
    expect(parseChunks(["﻿data: 1\n\n"])).toEqual([{ event: "message", data: "1" }]);
  });
});

describe("readSse", () => {
  it("decodes UTF-8 characters cut between byte chunks", async () => {
    const frames: SseFrame[] = [];
    await readSse(byteStream(bytesOf(STREAM, 3)), (f) => frames.push(f));
    expect(frames).toEqual(parseChunks([STREAM]));
    expect(JSON.parse(frames[1]!.data)).toEqual({ text: "Hisoblayapman…" });
  });

  it("rejects with AbortError when aborted", async () => {
    const ctrl = new AbortController();
    const never = new ReadableStream<Uint8Array>({
      start(c) {
        c.enqueue(new TextEncoder().encode("data: 1\n\n"));
      },
    });
    const p = readSse(never, () => ctrl.abort(), ctrl.signal);
    await expect(p).rejects.toMatchObject({ name: "AbortError" });
  });
});

describe("postSse", () => {
  afterEach(() => vi.unstubAllGlobals());

  it("posts JSON and calls handlers with decoded data", async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(byteStream(bytesOf(STREAM, 7)), {
          status: 200,
          headers: { "Content-Type": "text/event-stream" },
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const seen: [string, unknown][] = [];
    await postSse<{ meta: unknown; status: unknown; answer: unknown; done: unknown }>(
      "/api/chat/messages",
      { text: "salom", conversation_id: 12 },
      {
        meta: (d) => seen.push(["meta", d]),
        status: (d) => seen.push(["status", d]),
        answer: (d) => seen.push(["answer", d]),
        done: (d) => seen.push(["done", d]),
      },
    );
    expect(seen).toEqual([
      ["meta", { conversation_id: 12, user_message_id: 40 }],
      ["status", { text: "Hisoblayapman…" }],
      ["answer", { headline: "Yo'q, hozir olmang.", verdict: "no" }],
      ["done", { message_id: 41, latency_ms: 900, model: "template" }],
    ]);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe("/api/chat/messages");
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ text: "salom", conversation_id: 12 });
    expect(init.headers).toMatchObject({ "Content-Type": "application/json", "X-CSRFToken": "" });
  });

  it("skips frames with invalid JSON and unknown event names", async () => {
    const body =
      'event: status\ndata: {broken\n\nevent: toString\ndata: 1\n\nevent: status\ndata: {"text": "ok"}\n\n';
    vi.stubGlobal("fetch", async () => new Response(body, { status: 200 }));
    const status = vi.fn();
    await postSse<{ status: unknown }>("/x", {}, { status });
    expect(status).toHaveBeenCalledTimes(1);
    expect(status).toHaveBeenCalledWith({ text: "ok" });
  });

  it("throws ApiError with the JSON body on HTTP errors", async () => {
    vi.stubGlobal(
      "fetch",
      async () => new Response(JSON.stringify({ message: "Xato" }), { status: 403 }),
    );
    const err = await postSse("/x", {}, {}).catch((e: unknown) => e);
    expect(err).toBeInstanceOf(ApiError);
    expect(err).toMatchObject({ status: 403, body: { message: "Xato" } });
  });
});
