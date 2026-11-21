/**
 * /live: full-screen live voice mode (design/pages/Live.html).
 *
 * The browser talks to Gemini Live directly (VoiceClient). Django only mints the token
 * (`takeLiveToken`, usually prefetched on hover in Chat), runs tools and stores the finished
 * conversation (`POST /api/live/finish`). Audio never passes through our server.
 */
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { LiveCaptions, type AiCaption } from "@/components/live/LiveCaptions";
import { LiveCardStack, type LiveCard, type PlanState } from "@/components/live/LiveCardStack";
import { LiveControls, LiveTextForm } from "@/components/live/LiveControls";
import { LiveHeader } from "@/components/live/LiveHeader";
import {
  LIVE_CLOSE_NOTE,
  LIVE_IDLE_CLOSE_MS,
  LIVE_MAX_SESSION_MS,
  type LiveCloseReason,
} from "@/components/live/limits";
import { LiveOrb } from "@/components/live/LiveOrb";
import type { UiBlock } from "@/components/UiBlockRenderer";
import { apiPost } from "@/lib/api";
import type { ApproveResult } from "@/lib/chatTypes";
import { appConfig } from "@/lib/config";
import { track } from "@/lib/telemetry";
import {
  liveBudgetMessage,
  prefetchLiveToken,
  SESSION_URL,
  takeLiveToken,
  type LiveSession,
} from "@/live/tokenCache";
import { VoiceClient, type Metric, type Status, type ToolResult } from "@/live/voiceClient";

type Phase = "connecting" | "reconnecting" | "ready" | "error" | "budget" | "closed" | "finishing";

interface Caption {
  key: string;
  who: "user" | "ai";
  turn: number;
  text: string;
  /** Typed with "Yozib so'rash" (not a transcription). */
  typed?: boolean;
}

interface Snapshot {
  captions: Caption[];
  cards: LiveCard[];
  plans: Record<number, PlanState>;
}

const BLOCK_TYPES: ReadonlySet<string> = new Set<UiBlock["type"]>([
  "verdict",
  "compare_bars",
  "steps",
  "kpi",
  "forecast_chart",
  "day_breakdown",
  "approval",
  "plan_timeline",
  "payback_chart",
  "scenario_table",
  "debt_list",
  "metric_grid",
]);
const CONNECT_FAILED = "Jonli suhbatni ochib bo'lmadi. Yozib so'rang.";
const FINISH_TIMEOUT_MS = 4000;
/** Player "drained" gaps shorter than this do not stop the orb (network jitter). */
const SPEAKING_TAIL_MS = 250;
/** keepalive bodies are limited to 64 KB by the browser. */
const KEEPALIVE_MAX_BYTES = 60_000;

// --- helpers -------------------------------------------------------------------------------
function asRecord(v: unknown): Record<string, unknown> | null {
  return v && typeof v === "object" && !Array.isArray(v) ? (v as Record<string, unknown>) : null;
}

function toBlocks(raw: unknown): UiBlock[] {
  if (!Array.isArray(raw)) return [];
  const out: UiBlock[] = [];
  raw.forEach((b, i) => {
    const r = asRecord(b);
    if (!r || typeof r.type !== "string" || !BLOCK_TYPES.has(r.type)) return;
    out.push({ ...r, id: typeof r.id === "string" && r.id ? r.id : `b${i}` } as UiBlock);
  });
  return out;
}

function toPlan(raw: unknown): { id: number; summary: string; status: string } | null {
  const r = asRecord(raw);
  const id = Number(r?.id);
  if (!r || !Number.isInteger(id) || id <= 0) return null;
  return { id, summary: typeof r.summary === "string" ? r.summary : "", status: String(r.status ?? "") };
}

/** The plan card lists the answer's steps (Live.html "Taklif: reja"), else the plan summary. */
function planItems(result: ToolResult, summary: string): string[] {
  const steps = asRecord(result.answer)?.steps;
  const list = Array.isArray(steps) ? steps.filter((s): s is string => typeof s === "string" && s.trim() !== "") : [];
  return list.length > 0 ? list.slice(0, 3) : [summary];
}

function findLast<T>(arr: T[], pred: (x: T) => boolean): T | undefined {
  for (let i = arr.length - 1; i >= 0; i--) {
    const x = arr[i];
    if (x !== undefined && pred(x)) return x;
  }
  return undefined;
}

/** Resolves after the next frame (the card is painted); a hidden tab has no frames. */
function nextPaint(): Promise<void> {
  return new Promise((resolve) => {
    const t = window.setTimeout(resolve, 100);
    requestAnimationFrame(() => {
      window.clearTimeout(t);
      resolve();
    });
  });
}

function finishPayload(s: Snapshot): { transcript: { who: "user" | "ai"; text: string }[]; blocks: UiBlock[] } {
  // Transcriptions can arrive late: order by turn, the user's words before the answer.
  const transcript = [...s.captions]
    .sort((a, b) => a.turn - b.turn || (a.who === b.who ? 0 : a.who === "user" ? -1 : 1))
    .map((c) => ({ who: c.who, text: c.text.trim() }))
    .filter((t) => t.text);
  const blocks: UiBlock[] = [];
  for (const c of s.cards) {
    if (c.kind === "blocks") {
      // Block ids repeat across tool calls ("cash", "fc"): make them unique for the chat history.
      blocks.push(...c.blocks.map((b) => ({ ...b, id: `${c.key}-${b.id}` })));
    } else if (s.plans[c.planId]?.status !== "done") {
      // Still open: keep it approvable from the chat.
      blocks.push({ id: c.key, type: "approval", plan_id: String(c.planId), summary: c.summary, approve_label: "Tasdiqlash" });
    }
  }
  return { transcript, blocks };
}

function WarnIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#FEC84B" strokeWidth="2" className="mt-[2px] shrink-0" aria-hidden="true">
      <path d="M12 3l10 18H2z" />
      <path d="M12 10v4M12 17.5v.5" />
    </svg>
  );
}

const NOTICE =
  "flex w-full max-w-[600px] gap-[10px] rounded-inner border border-[#93370D] bg-[#2A1F0B] px-[14px] py-3 text-14 leading-normal text-[#FEDF89]";

// --- page ----------------------------------------------------------------------------------
export default function LivePage() {
  const navigate = useNavigate();
  const clientRef = useRef<VoiceClient | null>(null);
  const stopTimer = useRef<number | undefined>(undefined);
  const speakTimer = useRef<number | undefined>(undefined);
  const everReady = useRef(false);
  const finishing = useRef(false);
  const saved = useRef(false);
  const seq = useRef(0);
  const latest = useRef<Snapshot>({ captions: [], cards: [], plans: {} });
  // budget rules (limits.ts): session clock, activity clock, total open time for `seconds`
  const sessionStart = useRef(0);
  const usedMs = useRef(0);
  const lastActivity = useRef(0);
  const aiAudio = useRef(false);
  const userVoice = useRef(false);
  const turnRef = useRef(0);
  const turnBase = useRef(0);

  const [phase, setPhase] = useState<Phase>("connecting");
  const [session, setSession] = useState<LiveSession | null>(null);
  const [connected, setConnected] = useState(false);
  const [micOk, setMicOk] = useState(true);
  const [audioSuspended, setAudioSuspended] = useState(false);
  const [aiSpeaking, setAiSpeaking] = useState(false);
  const [userSpeaking, setUserSpeaking] = useState(false);
  const [level, setLevel] = useState(0);
  const [gateOpen, setGateOpen] = useState(false);
  const [ptt, setPtt] = useState(false);
  const [talking, setTalking] = useState(false);
  const [toolsPending, setToolsPending] = useState(0);
  const [turn, setTurn] = useState(0);
  const [captions, setCaptions] = useState<Caption[]>([]);
  const [cards, setCards] = useState<LiveCard[]>([]);
  const [plans, setPlans] = useState<Record<number, PlanState>>({});
  const [textOpen, setTextOpen] = useState(false);
  const [closeReason, setCloseReason] = useState<LiveCloseReason | null>(null);
  const [budgetMsg, setBudgetMsg] = useState("");

  useEffect(() => {
    latest.current = { captions, cards, plans };
  }, [captions, cards, plans]);

  useEffect(() => {
    const prev = document.title;
    document.title = appConfig.appName ? `${appConfig.appName} — Jonli suhbat` : "Jonli suhbat";
    return () => {
      document.title = prev;
    };
  }, []);

  // --- VoiceClient callbacks ---
  const onCaption = useCallback((who: "user" | "ai", chunk: string, clientTurn: number) => {
    // Turn numbers restart with every client ("Qayta boshlash"): keep them unique on the page.
    const t = turnBase.current + clientTurn;
    const key = `${who}-${t}`;
    setCaptions((prev) => {
      const i = prev.findIndex((c) => c.key === key);
      const cur = i >= 0 ? prev[i] : undefined;
      if (!cur) return [...prev, { key, who, turn: t, text: chunk }];
      const next = prev.slice();
      next[i] = { ...cur, text: cur.text + chunk };
      return next;
    });
  }, []);

  const onSpeaking = useCallback((speaking: boolean) => {
    aiAudio.current = speaking;
    lastActivity.current = performance.now();
    window.clearTimeout(speakTimer.current);
    if (speaking) setAiSpeaking(true);
    else speakTimer.current = window.setTimeout(() => setAiSpeaking(false), SPEAKING_TAIL_MS);
  }, []);

  const onMetric = useCallback((m: Metric) => {
    track("voice", m.name, m.ms, { ...m.meta, behavior: "blocking", page: "live" });
    // The server will close this connection soon: have a token ready for the reconnect.
    if (m.name === "go_away") void prefetchLiveToken();
  }, []);

  const addToolResult = useCallback((name: string, args: Record<string, unknown>, result: ToolResult) => {
    const group = seq.current++;
    const blocks = toBlocks(result.ui_blocks);
    const plan = toPlan(result.proposed_plan);
    const items = plan ? planItems(result, plan.summary) : [];
    setCards((prev) => {
      const next = [...prev];
      if (blocks.length > 0) next.push({ kind: "blocks", key: `g${group}`, group, blocks });
      if (plan && !prev.some((c) => c.kind === "plan" && c.planId === plan.id)) {
        next.push({ kind: "plan", key: `plan-${plan.id}`, group, planId: plan.id, summary: plan.summary, items });
      }
      return next;
    });
    if (plan?.status === "approved") {
      setPlans((p) => ({ ...p, [plan.id]: { status: "done", summary: plan.summary } }));
    }
    // "Ha" by voice: the backend approved the plan inside confirm_plan.
    if (name === "confirm_plan" && result.ok !== false) {
      const id = Number(asRecord(result.facts)?.plan_id ?? args.plan_id);
      const summary = asRecord(result.display)?.summary;
      if (Number.isInteger(id) && id > 0) {
        setPlans((p) => ({
          ...p,
          [id]: { status: "done", summary: typeof summary === "string" && summary ? summary : p[id]?.summary },
        }));
      }
    }
  }, []);

  /** Close the session and release the mic; adds its open time to `seconds`. */
  const endSession = useCallback((): Promise<void> => {
    const c = clientRef.current;
    clientRef.current = null;
    if (sessionStart.current) {
      usedMs.current += performance.now() - sessionStart.current;
      sessionStart.current = 0;
    }
    window.clearTimeout(speakTimer.current);
    aiAudio.current = userVoice.current = false;
    setAiSpeaking(false);
    setUserSpeaking(false);
    setConnected(false);
    setToolsPending(0);
    return c ? c.stop() : Promise.resolve();
  }, []);

  const autoClose = useCallback(
    (reason: LiveCloseReason) => {
      if (!clientRef.current || finishing.current) return;
      track("voice", "auto_close", sessionStart.current ? performance.now() - sessionStart.current : 0, {
        reason,
        page: "live",
      });
      void endSession();
      setCloseReason(reason);
      setPhase("closed");
    },
    [endSession],
  );

  const takeToken = useCallback((): Promise<LiveSession> => {
    const t0 = performance.now();
    return takeLiveToken().then((s) => {
      track("voice", "token_take", performance.now() - t0, { from_cache: s.from_cache, mint_ms: s.mint_ms, page: "live" });
      setSession(s);
      return s;
    });
  }, []);

  const start = useCallback(async (base: number) => {
    // The daily voice limit is already known (prefetch got 429): no mic prompt, no connect.
    const blocked = liveBudgetMessage();
    if (blocked) {
      await Promise.resolve();
      setBudgetMsg(blocked);
      setPhase("budget");
      return;
    }
    const tOpen = performance.now();
    everReady.current = false;
    turnBase.current = base;
    turnRef.current = base;
    sessionStart.current = tOpen;
    lastActivity.current = tOpen;
    const c: VoiceClient = new VoiceClient({
      tokenUrl: SESSION_URL,
      toolUrl: (name) => `/api/tools/${encodeURIComponent(name)}`,
      behavior: "blocking",
      scheduling: "WHEN_IDLE",
      getToken: takeToken,
      annotateToolCalls: true,
      micOptional: true,
      onStatus: (s: Status) => {
        if (clientRef.current !== c) return; // an old client after a retry / finish
        if (s === "preparing" || s === "connecting") {
          setConnected(false);
          setPhase(everReady.current ? "reconnecting" : "connecting");
        } else if (s === "ready") {
          everReady.current = true;
          lastActivity.current = performance.now();
          setConnected(true);
          setPhase("ready");
        } else if (s === "error") {
          const budget = liveBudgetMessage();
          track("voice", budget ? "budget_blocked" : "session_error", 0, {
            stage: everReady.current ? "reconnect" : "connect",
            page: "live",
          });
          void endSession(); // also releases the mic after a failed reconnect
          if (budget) {
            setBudgetMsg(budget);
            setPhase("budget");
          } else {
            setPhase("error");
            setTextOpen(true);
          }
        } else if (s === "closed") {
          setConnected(false);
        }
      },
      onCaption,
      onMetric,
      onSpeaking,
      onLevel: (lv, open) => {
        setLevel(Math.round(lv * 20) / 20);
        setGateOpen(open);
      },
      onUserSpeaking: (speaking) => {
        userVoice.current = speaking;
        lastActivity.current = performance.now();
        setUserSpeaking(speaking);
      },
      onMicError: () => {
        setMicOk(false);
        setTextOpen(true);
      },
      onToolCall: () => {
        lastActivity.current = performance.now();
        setToolsPending((n) => n + 1);
      },
      onToolResult: (name, args, result) => {
        lastActivity.current = performance.now();
        addToolResult(name, args, result);
        setToolsPending((n) => Math.max(0, n - 1));
        return nextPaint();
      },
      onTurnComplete: (done) => {
        turnRef.current = base + done + 1;
        setTurn(base + done + 1);
      },
    });
    clientRef.current = c;
    try {
      await c.prepare(tOpen, takeToken());
      if (clientRef.current === c) setAudioSuspended(c.audioSuspended);
    } catch {
      /* shown through onStatus("error") */
    }
  }, [takeToken, onCaption, onMetric, onSpeaking, addToolResult, endSession]);

  /** Saves the transcript + shown blocks once (Tugatish, leaving the page, closing the tab). */
  const save = useCallback((keepalive: boolean): Promise<unknown> => {
    if (saved.current) return Promise.resolve();
    const open = sessionStart.current ? performance.now() - sessionStart.current : 0;
    const seconds = Math.round((usedMs.current + open) / 1000);
    const payload = { ...finishPayload(latest.current), seconds };
    if (payload.transcript.length === 0 && seconds === 0) return Promise.resolve();
    saved.current = true;
    let body: unknown = payload;
    if (keepalive && JSON.stringify(payload).length > KEEPALIVE_MAX_BYTES) body = { ...payload, blocks: [] };
    return apiPost("/api/live/finish", body, { keepalive }).catch(() => undefined);
  }, []);

  // Start on mount. Under StrictMode the effect runs twice: the stop is deferred one tick so
  // the immediate re-mount keeps the same session (and the single-use token).
  useEffect(() => {
    if (stopTimer.current !== undefined) {
      window.clearTimeout(stopTimer.current);
      stopTimer.current = undefined;
    } else {
      void start(0);
    }
    const onPageHide = () => {
      void endSession();
      void save(true);
    };
    window.addEventListener("pagehide", onPageHide);
    return () => {
      window.removeEventListener("pagehide", onPageHide);
      stopTimer.current = window.setTimeout(() => {
        stopTimer.current = undefined;
        void endSession();
        void save(false);
      }, 0);
    };
  }, [start, save, endSession]);

  // Budget rules: close after LIVE_IDLE_CLOSE_MS without user speech or model audio, and after
  // LIVE_MAX_SESSION_MS in total.
  useEffect(() => {
    if (phase !== "connecting" && phase !== "reconnecting" && phase !== "ready") return;
    const id = window.setInterval(() => {
      const now = performance.now();
      if (!sessionStart.current) return;
      if (now - sessionStart.current >= LIVE_MAX_SESSION_MS) return autoClose("max");
      if (aiAudio.current || userVoice.current) lastActivity.current = now;
      else if (phase === "ready" && now - lastActivity.current >= LIVE_IDLE_CLOSE_MS) autoClose("idle");
    }, 1000);
    return () => window.clearInterval(id);
  }, [phase, autoClose]);

  // ... and as soon as the tab is hidden.
  useEffect(() => {
    const onVisibility = () => {
      if (document.visibilityState === "hidden") autoClose("hidden");
    };
    document.addEventListener("visibilitychange", onVisibility);
    return () => document.removeEventListener("visibilitychange", onVisibility);
  }, [autoClose]);

  // Audio started suspended (no user gesture yet, e.g. after a reload): resume on any input.
  useEffect(() => {
    if (!audioSuspended) return;
    const resume = () => {
      const c = clientRef.current;
      if (c) void c.resumeAudio().then(() => setAudioSuspended(c.audioSuspended));
    };
    window.addEventListener("pointerdown", resume);
    window.addEventListener("keydown", resume);
    return () => {
      window.removeEventListener("pointerdown", resume);
      window.removeEventListener("keydown", resume);
    };
  }, [audioSuspended]);

  useEffect(() => () => window.clearTimeout(speakTimer.current), []);

  // --- user actions ---
  useEffect(() => {
    if (!ptt) return;
    const down = (e: KeyboardEvent) => {
      if (e.code !== "Space" || e.repeat || (e.target as HTMLElement)?.tagName === "INPUT") return;
      e.preventDefault();
      setTalking(true);
      if (clientRef.current) clientRef.current.talking = true;
    };
    const up = (e: KeyboardEvent) => {
      if (e.code !== "Space") return;
      setTalking(false);
      if (clientRef.current) clientRef.current.talking = false;
    };
    window.addEventListener("keydown", down);
    window.addEventListener("keyup", up);
    return () => {
      window.removeEventListener("keydown", down);
      window.removeEventListener("keyup", up);
    };
  }, [ptt]);

  const stopPlayback = useCallback(() => {
    clientRef.current?.stopPlayback();
    window.clearTimeout(speakTimer.current);
    setAiSpeaking(false);
    track("voice", "stop_playback", 0, { page: "live" });
  }, []);

  const sendText = useCallback(
    (text: string) => {
      const c = clientRef.current;
      if (!c?.connected) return;
      lastActivity.current = performance.now();
      c.sendText(text);
      setCaptions((prev) => [...prev, { key: `typed-${seq.current++}`, who: "user", turn, text, typed: true }]);
    },
    [turn],
  );

  const approve = useCallback((id: number) => {
    setPlans((p) => ({ ...p, [id]: { ...p[id], status: "pending" } }));
    apiPost<ApproveResult>(`/api/actions/${id}/approve`, {})
      .then((r) => setPlans((p) => ({ ...p, [id]: { status: "done", summary: r?.summary || p[id]?.summary } })))
      .catch(() => setPlans((p) => ({ ...p, [id]: { status: "error" } })));
  }, []);

  const finish = useCallback(async () => {
    if (finishing.current) return;
    finishing.current = true;
    setPhase("finishing");
    await endSession();
    await Promise.race([save(false), new Promise((r) => window.setTimeout(r, FINISH_TIMEOUT_MS))]);
    navigate("/chat");
  }, [navigate, save, endSession]);

  /** "Qayta urinish" after an error, "Qayta boshlash" after an auto-close. */
  const retry = useCallback(() => {
    void endSession();
    const base = turnRef.current + 1;
    setTurn(base);
    setMicOk(true);
    setTextOpen(false);
    setCloseReason(null);
    setPhase("connecting");
    void start(base);
  }, [start, endSession]);

  // --- derived view state ---
  const lastUser = findLast(captions, (c) => c.who === "user");
  const lastAi = findLast(captions, (c) => c.who === "ai");
  const ai: AiCaption | null = lastAi
    ? { text: lastAi.text, final: lastAi.turn < turn, old: !!lastUser && lastUser.turn > lastAi.turn }
    : null;
  const awaitingAnswer = !!lastUser && !lastUser.typed && lastUser.turn === turn && lastAi?.turn !== turn;
  const listening = userSpeaking || awaitingAnswer;

  let status = "Ulanmoqda…";
  let hint = "";
  if (phase === "reconnecting") status = "Qayta ulanmoqda…";
  else if (phase === "error") status = "Ulanib bo'lmadi";
  else if (phase === "finishing") status = "Suhbat saqlanmoqda…";
  else if (phase === "closed") status = "Suhbat yopildi";
  else if (phase === "budget") status = budgetMsg;
  else if (phase === "ready") {
    if (toolsPending > 0) status = "Hozir hisoblayman…";
    else if (aiSpeaking) {
      status = "AI gapiryapti…";
      hint = micOk ? "Istalgan payt gapirib, uni to'xtatishingiz mumkin" : "";
    } else if (!micOk) status = "Yozib so'rang";
    else if (listening) status = "Eshityapman…";
    else {
      status = "Gapiring";
      hint = "Gapiring yoki pastdagi tugmani bosing";
    }
  }

  return (
    <div className="flex min-h-screen flex-col bg-live-bg font-sans text-white">
      <LiveHeader businessName={session?.business_name ?? ""} onClose={() => void finish()} />

      <div className="mx-auto box-border flex w-full max-w-[1360px] grow flex-wrap gap-8 p-4 sm:p-8">
        <section aria-label="Ovozli suhbat" className="flex min-w-0 flex-[1_1_460px] flex-col items-center gap-[26px] pt-2">
          <LiveOrb speaking={aiSpeaking} level={level} listening={gateOpen && !aiSpeaking} thinking={toolsPending > 0} />

          <div className="flex flex-col items-center gap-[6px] text-center">
            <span className="font-display text-22 font-bold" role="status">
              {status}
            </span>
            {hint && <span className="text-14 text-[#98A2B3]">{hint}</span>}
          </div>

          <LiveCaptions user={lastUser?.text ?? ""} ai={ai} />

          {phase === "error" && (
            <div role="alert" className={NOTICE}>
              <WarnIcon />
              <div className="flex min-w-0 flex-col gap-3">
                <span>{CONNECT_FAILED}</span>
                <div className="flex flex-wrap gap-[10px]">
                  <Link
                    to="/chat"
                    className="inline-flex min-h-tap items-center rounded-btn bg-primary px-[18px] text-15 font-semibold text-white no-underline hover:bg-primary-hover hover:text-white"
                  >
                    Yozib so'rash
                  </Link>
                  <button
                    type="button"
                    onClick={retry}
                    className="min-h-tap rounded-btn border-0 bg-live-border px-[18px] text-15 font-semibold text-white"
                  >
                    Qayta urinish
                  </button>
                </div>
              </div>
            </div>
          )}
          {phase === "closed" && closeReason && (
            <div role="status" className={NOTICE}>
              <WarnIcon />
              <div className="flex min-w-0 flex-col gap-3">
                <span>{LIVE_CLOSE_NOTE[closeReason]}</span>
                <button
                  type="button"
                  onClick={retry}
                  className="min-h-tap self-start rounded-btn border-0 bg-primary px-[18px] text-15 font-semibold text-white hover:bg-primary-hover"
                >
                  Qayta boshlash
                </button>
              </div>
            </div>
          )}
          {phase !== "error" && phase !== "closed" && phase !== "budget" && !micOk && (
            <div role="status" className={NOTICE}>
              <WarnIcon />
              <span>Mikrofon ishlamadi. Savolingizni yozib yuboring, javobni ovozda eshitasiz.</span>
            </div>
          )}
          {audioSuspended && phase === "ready" && (
            <div role="status" className={NOTICE}>
              <WarnIcon />
              <span>Ovozni yoqish uchun ekranning istalgan joyiga bosing.</span>
            </div>
          )}

          {connected && (
            <div className="flex w-full max-w-[600px] flex-col items-center gap-2">
              <div className="flex w-full items-center gap-2 text-12 text-[#98A2B3]">
                <span>Mikrofon</span>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-[#1D2939]" aria-label="Mikrofon darajasi">
                  <div
                    className={gateOpen ? "h-full bg-[#32D583]" : "h-full bg-[#475467]"}
                    style={{ width: `${Math.round(level * 100)}%`, transition: "width 80ms linear" }}
                  />
                </div>
                <span>{gateOpen ? "eshityapman" : "shovqin e'tiborsiz"}</span>
              </div>
              <label className="flex items-center gap-2 text-13 text-[#D0D5DD]">
                <input
                  type="checkbox"
                  checked={ptt}
                  onChange={(e) => {
                    setPtt(e.target.checked);
                    if (clientRef.current) clientRef.current.pushToTalk = e.target.checked;
                  }}
                />
                Bosib gapirish (shovqinli joy, masalan oshxona)
              </label>
              {ptt && (
                <button
                  type="button"
                  onPointerDown={() => {
                    setTalking(true);
                    if (clientRef.current) clientRef.current.talking = true;
                  }}
                  onPointerUp={() => {
                    setTalking(false);
                    if (clientRef.current) clientRef.current.talking = false;
                  }}
                  onPointerLeave={() => {
                    setTalking(false);
                    if (clientRef.current) clientRef.current.talking = false;
                  }}
                  className={
                    "rounded-full px-6 py-3 text-15 font-semibold " +
                    (talking ? "bg-[#32D583] text-[#0C111D]" : "bg-[#1D2939] text-white")
                  }
                >
                  {talking ? "Gapiring…" : "Bosib turing va gapiring (yoki Probel)"}
                </button>
              )}
            </div>
          )}

          {textOpen && connected && <LiveTextForm onSend={sendText} />}
        </section>

        <LiveCardStack cash={session?.cash ?? null} cards={cards} plans={plans} onApprove={approve} />
      </div>

      <LiveControls
        speaking={aiSpeaking}
        onStop={stopPlayback}
        textMode={connected ? "inline" : "chat"}
        textOpen={textOpen && connected}
        onToggleText={() => setTextOpen((o) => !o)}
        onFinish={() => void finish()}
        finishing={phase === "finishing"}
      />
    </div>
  );
}
