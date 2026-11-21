/**
 * /dev/voice — M0 voice spike page (not part of the design; DEBUG backend only).
 * Ephemeral token -> gemini-3.8-live -> mic -> Uzbek answer, one fake tool.
 * Shows and records: session ready, speech_end -> first_audio, tool round trip.
 */
import { useCallback, useEffect, useRef, useState } from "react";

import { appConfig } from "@/lib/config";
import { track } from "@/lib/telemetry";
import {
  VoiceClient,
  type Metric,
  type Scheduling,
  type Status,
  type ToolBehavior,
  type ToolResult,
} from "@/live/voiceClient";

interface Caption {
  who: "user" | "ai";
  turn: number;
  text: string;
}

declare global {
  interface Window {
    /** Read by the headless browser check (dev page only). */
    __devVoice?: { status: Status; metrics: Metric[]; captions: Caption[]; tools: number };
  }
}

const STATUS_UZ: Record<Status, string> = {
  idle: "Tayyor emas",
  preparing: "Tayyorlanmoqda…",
  connecting: "Ulanmoqda…",
  ready: "Gapiring",
  closed: "Tugadi",
  error: "Xato",
};

export default function DevVoice() {
  const tOpen = useRef(0);
  const client = useRef<VoiceClient | null>(null);
  const [behavior, setBehavior] = useState<ToolBehavior>("blocking");
  const [scheduling, setScheduling] = useState<Scheduling>("WHEN_IDLE");
  const [status, setStatus] = useState<Status>("idle");
  const [detail, setDetail] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [metrics, setMetrics] = useState<Metric[]>([]);
  const [tools, setTools] = useState<{ name: string; args: Record<string, unknown>; result: ToolResult }[]>([]);
  const [text, setText] = useState("");

  const onCaption = useCallback((who: "user" | "ai", chunk: string, turn: number) => {
    setCaptions((prev) => {
      const last = prev[prev.length - 1];
      if (last && last.who === who && last.turn === turn) {
        return [...prev.slice(0, -1), { ...last, text: last.text + chunk }];
      }
      return [...prev, { who, turn, text: chunk }];
    });
  }, []);

  const onMetric = useCallback(
    (m: Metric) => {
      setMetrics((prev) => [...prev, m]);
      track("voice", m.name, m.ms, { ...m.meta, behavior, scheduling, spike: true });
    },
    [behavior, scheduling],
  );

  const start = useCallback(
    async (fromPageOpen: boolean) => {
      await client.current?.stop();
      setCaptions([]);
      setTools([]);
      const c = new VoiceClient({
        tokenUrl: "/api/dev/live/session",
        toolUrl: (name) => `/api/dev/tools/${name}`,
        behavior,
        scheduling,
        onStatus: (s, d) => {
          setStatus(s);
          setDetail(d ?? "");
        },
        onCaption,
        onMetric,
        onSpeaking: setSpeaking,
        onToolResult: async (name, args, result) => {
          setTools((prev) => [...prev, { name, args, result }]);
          // resolve after the card is painted (tool_response_to_card)
          await new Promise<void>((r) => requestAnimationFrame(() => r()));
        },
      });
      client.current = c;
      try {
        await c.prepare(fromPageOpen ? tOpen.current : performance.now());
      } catch (err) {
        setStatus("error");
        setDetail(err instanceof Error ? err.message : String(err));
      }
    },
    [behavior, scheduling, onCaption, onMetric],
  );

  // Prepare the session as soon as the page opens (mic + token + worklets in parallel).
  useEffect(() => {
    tOpen.current = performance.now();
    document.title = `${appConfig.appName} — ovoz sinovi`;
    // Opening the Live session is subscribing to an external system; state updates come
    // from its callbacks, which is the intended use of an effect.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void start(true);
    return () => {
      void client.current?.stop();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    window.__devVoice = { status, metrics, captions, tools: tools.length };
  }, [status, metrics, captions, tools]);

  const summary = summarize(metrics);

  return (
    <main className="min-h-screen bg-live-bg px-4 py-7 text-white md:px-9">
      <header className="flex flex-wrap items-center gap-3">
        <h1 className="m-0 font-display text-22 font-bold">{appConfig.appName} · ovoz sinovi (M0)</h1>
        <span
          className={`rounded-pill px-3 py-1 text-13 font-bold ${
            status === "ready" ? "bg-success-bg text-success" : status === "error" ? "bg-danger-bg text-danger" : "bg-live-surface text-[#98A2B3]"
          }`}
          aria-live="polite"
        >
          {STATUS_UZ[status]}
          {speaking ? " · AI gapiryapti" : ""}
          {detail ? ` · ${detail}` : ""}
        </span>
      </header>

      <section className="mt-5 flex flex-wrap items-end gap-3" aria-label="Sozlamalar">
        <label className="flex flex-col gap-1 text-13 text-[#98A2B3]">
          Tool rejimi
          <select
            className="min-h-tap rounded-btn border border-live-border bg-live-surface px-3 text-15 text-white"
            value={behavior}
            onChange={(e) => setBehavior(e.target.value as ToolBehavior)}
          >
            <option value="blocking">BLOCKING</option>
            <option value="non_blocking">NON_BLOCKING</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-13 text-[#98A2B3]">
          Scheduling (NON_BLOCKING)
          <select
            className="min-h-tap rounded-btn border border-live-border bg-live-surface px-3 text-15 text-white"
            value={scheduling}
            onChange={(e) => setScheduling(e.target.value as Scheduling)}
          >
            <option value="WHEN_IDLE">WHEN_IDLE</option>
            <option value="INTERRUPT">INTERRUPT</option>
          </select>
        </label>
        <button
          type="button"
          className="min-h-tap rounded-btn bg-primary px-4 text-15 font-semibold text-white hover:bg-primary-hover"
          onClick={() => void start(false)}
        >
          Qayta ulanish
        </button>
        <button
          type="button"
          className="min-h-tap rounded-btn bg-danger-strong px-4 text-15 font-semibold text-white"
          onClick={() => void client.current?.stop()}
        >
          Tugatish
        </button>
      </section>

      <div className="mt-6 grid gap-5 lg:grid-cols-2">
        <section className="rounded-card border border-live-border bg-live-surface p-5" aria-label="Subtitr">
          <h2 className="m-0 mb-3 text-13 font-bold uppercase tracking-label text-[#98A2B3]">Suhbat</h2>
          <ol className="m-0 flex list-none flex-col gap-3 p-0">
            {captions.map((c, i) => (
              <li key={i} className={c.who === "ai" ? "text-white" : "text-[#98A2B3]"}>
                <span className="text-12 font-bold uppercase tracking-label">{c.who === "ai" ? "AI CFO" : "Siz"}</span>
                <p className="m-0 text-17">{c.text}</p>
              </li>
            ))}
          </ol>
          <form
            className="mt-4 flex gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              if (text.trim()) client.current?.sendText(text.trim());
              setText("");
            }}
          >
            <input
              className="min-h-tap flex-1 rounded-btn border border-live-border bg-live-bg px-3 text-15 text-white"
              placeholder="Yozib so'rash"
              aria-label="Yozib so'rash"
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
            <button type="submit" className="min-h-tap rounded-btn bg-primary px-4 text-15 font-semibold">
              Yuborish
            </button>
          </form>
        </section>

        <section className="rounded-card border border-live-border bg-live-surface p-5" aria-label="O'lchovlar">
          <h2 className="m-0 mb-3 text-13 font-bold uppercase tracking-label text-[#98A2B3]">Kechikish (ms)</h2>
          <table className="w-full text-15">
            <tbody>
              {summary.map(([name, vals]) => (
                <tr key={name} className="border-b border-live-border">
                  <td className="py-2 pr-3 text-[#98A2B3]">{name}</td>
                  <td className="py-2 text-right font-display">{vals.map((v) => Math.round(v)).join(", ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {tools.map((t, i) => (
            <details key={i} className="mt-3 rounded-inner border border-live-border p-3">
              <summary className="cursor-pointer text-15">
                tool: {t.name} {JSON.stringify(t.args)}
              </summary>
              <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-12 text-[#98A2B3]">
                {JSON.stringify(t.result.ui_blocks ?? t.result, null, 1)}
              </pre>
            </details>
          ))}
        </section>
      </div>
    </main>
  );
}

function summarize(metrics: Metric[]): [string, number[]][] {
  const by = new Map<string, number[]>();
  for (const m of metrics) {
    if (m.name === "interrupted" || m.name === "go_away") continue;
    by.set(m.name, [...(by.get(m.name) ?? []), m.ms]);
  }
  return [...by.entries()];
}
