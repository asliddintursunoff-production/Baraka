/**
 * Browser <-> Gemini Live voice client.
 *
 * - On `prepare()`: mic permission, token fetch and AudioWorklet loading run in parallel,
 *   then the WebSocket is opened, so the session is ready before the user speaks.
 * - Mic: AudioWorklet -> 16 kHz PCM16, 20 ms frames, streamed continuously.
 * - Playback: 24 kHz ring-buffer worklet, starts on the first chunk; cleared on `interrupted`.
 * - Tool calls: POST to the backend (same origin, session cookie), render the ui_blocks right
 *   away, then `sendToolResponse`.
 * Audio never passes through Django; Django only mints the token and runs tools.
 */
import {
  FunctionResponseScheduling,
  GoogleGenAI,
  Modality,
  type LiveServerMessage,
  type Session,
} from "@google/genai";

import { apiPost } from "@/lib/api";

import { base64ToBuffer, bufferToBase64 } from "./pcm";

export type ToolBehavior = "blocking" | "non_blocking";
export type Scheduling = "WHEN_IDLE" | "INTERRUPT";
export type Status = "idle" | "preparing" | "connecting" | "ready" | "closed" | "error";

export interface TokenResponse {
  ok: boolean;
  token: string;
  model: string;
  expires_at: string;
  behavior: ToolBehavior;
  mint_ms?: number;
}

export interface ToolResult {
  ok?: boolean;
  ui_blocks?: unknown[];
  [key: string]: unknown;
}

export interface Metric {
  name: string;
  ms: number;
  meta?: Record<string, unknown>;
}

export interface VoiceClientOptions {
  tokenUrl: string;
  toolUrl: (name: string) => string;
  behavior: ToolBehavior;
  scheduling: Scheduling;
  onStatus: (s: Status, detail?: string) => void;
  onCaption: (who: "user" | "ai", text: string, turn: number) => void;
  onToolResult: (name: string, args: Record<string, unknown>, result: ToolResult) => Promise<void>;
  onMetric: (m: Metric) => void;
  onSpeaking?: (speaking: boolean) => void;
}

const VOICE_RMS = 0.02; // frame RMS above this counts as speech (for speech_end timing)

export class VoiceClient {
  private opts: VoiceClientOptions;
  private session: Session | null = null;
  private stream: MediaStream | null = null;
  private micCtx: AudioContext | null = null;
  private playCtx: AudioContext | null = null;
  private player: AudioWorkletNode | null = null;
  private mic: AudioWorkletNode | null = null;
  private tOpen = 0;
  private ready = false;
  private resumeHandle: string | undefined;

  // per-turn measurement state
  private lastVoiceAt = 0;
  private userSpokeSinceModel = false;
  private modelAudioThisTurn = false;
  private toolRespondedAt = 0;
  private turn = 0;
  private closedByUser = false;

  constructor(opts: VoiceClientOptions) {
    this.opts = opts;
  }

  /** Parallel: mic + token + worklets; then connect. Resolves when the session is ready. */
  async prepare(tOpen = performance.now(), prefetchedToken?: Promise<TokenResponse>): Promise<void> {
    this.tOpen = tOpen;
    this.closedByUser = false;
    this.opts.onStatus("preparing");
    const tokenP = prefetchedToken ?? this.fetchToken();
    const micP = navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
    });
    this.micCtx = new AudioContext();
    this.playCtx = new AudioContext({ sampleRate: 24000 });
    const workletsP = Promise.all([
      this.micCtx.audioWorklet.addModule("/worklets/mic-processor.js"),
      this.playCtx.audioWorklet.addModule("/worklets/pcm-player.js"),
    ]);
    const [token, stream] = await Promise.all([tokenP, micP, workletsP]);
    this.stream = stream;
    this.metric("token_ready", performance.now() - this.tOpen, { mint_ms: token.mint_ms });
    this.setupPlayer();
    this.setupMic(stream);
    await this.connect(token);
  }

  fetchToken(): Promise<TokenResponse> {
    return apiPost<TokenResponse>(this.opts.tokenUrl, { behavior: this.opts.behavior });
  }

  private async connect(token: TokenResponse): Promise<void> {
    this.opts.onStatus("connecting");
    const ai = new GoogleGenAI({ apiKey: token.token, httpOptions: { apiVersion: "v1beta" } });
    const tConnect = performance.now();
    let resolveReady: () => void = () => {};
    let rejectReady: (e: Error) => void = () => {};
    const readyP = new Promise<void>((res, rej) => {
      resolveReady = res;
      rejectReady = rej;
    });
    this.ready = false;
    this.session = await ai.live.connect({
      model: token.model,
      config: {
        responseModalities: [Modality.AUDIO],
        sessionResumption: this.resumeHandle ? { handle: this.resumeHandle } : {},
      },
      callbacks: {
        onopen: () => this.metric("ws_open", performance.now() - tConnect),
        onmessage: (m: LiveServerMessage) => {
          if (m.setupComplete && !this.ready) {
            this.ready = true;
            this.metric("session_ready", performance.now() - this.tOpen, {
              connect_ms: Math.round(performance.now() - tConnect),
            });
            this.opts.onStatus("ready");
            resolveReady();
          }
          void this.onMessage(m);
        },
        onerror: (e: ErrorEvent) => {
          this.opts.onStatus("error", e.message);
          rejectReady(new Error(e.message || "Live xatosi"));
        },
        onclose: (e: CloseEvent) => {
          const wasReady = this.ready;
          this.ready = false;
          this.session = null;
          if (!wasReady) {
            rejectReady(new Error(e.reason || "Live yopildi"));
            this.opts.onStatus("error", e.reason || "ulanib bo'lmadi");
          } else if (this.closedByUser) {
            this.opts.onStatus("closed");
          } else {
            // Server closed an established session (goAway / ~10 min limit): new token, resume.
            this.opts.onStatus("connecting", e.reason || "qayta ulanmoqda");
            void this.reconnect();
          }
        },
      },
    });
    await readyP;
  }

  private async reconnect(): Promise<void> {
    try {
      const token = await this.fetchToken();
      await this.connect(token);
    } catch (err) {
      this.opts.onStatus("error", err instanceof Error ? err.message : String(err));
    }
  }

  private setupPlayer(): void {
    if (!this.playCtx) return;
    this.player = new AudioWorkletNode(this.playCtx, "pcm-player", { outputChannelCount: [1] });
    this.player.connect(this.playCtx.destination);
    this.player.port.onmessage = (e: MessageEvent<{ type: string }>) => {
      if (e.data.type === "playing") this.opts.onSpeaking?.(true);
      if (e.data.type === "drained" || e.data.type === "cleared") this.opts.onSpeaking?.(false);
    };
  }

  private setupMic(stream: MediaStream): void {
    if (!this.micCtx) return;
    const src = this.micCtx.createMediaStreamSource(stream);
    this.mic = new AudioWorkletNode(this.micCtx, "mic-processor", {
      processorOptions: { frameMs: 20 },
    });
    this.mic.port.onmessage = (e: MessageEvent<{ pcm: ArrayBuffer; rms: number }>) => {
      if (e.data.rms > VOICE_RMS) {
        this.lastVoiceAt = performance.now();
        this.userSpokeSinceModel = true;
      }
      if (!this.session || !this.ready) return;
      this.session.sendRealtimeInput({
        audio: { data: bufferToBase64(e.data.pcm), mimeType: "audio/pcm;rate=16000" },
      });
    };
    src.connect(this.mic);
    // The worklet must be pulled by the graph; route it to a muted gain so nothing is heard.
    const mute = this.micCtx.createGain();
    mute.gain.value = 0;
    this.mic.connect(mute).connect(this.micCtx.destination);
  }

  private async onMessage(m: LiveServerMessage): Promise<void> {
    if (m.sessionResumptionUpdate?.resumable && m.sessionResumptionUpdate.newHandle) {
      this.resumeHandle = m.sessionResumptionUpdate.newHandle;
    }
    if (m.goAway) this.metric("go_away", 0, { time_left: m.goAway.timeLeft });

    const sc = m.serverContent;
    if (sc) {
      if (sc.interrupted) {
        this.player?.port.postMessage({ type: "clear" });
        this.metric("interrupted", 0, { turn: this.turn });
      }
      for (const part of sc.modelTurn?.parts ?? []) {
        const data = part.inlineData?.data;
        if (!data) continue;
        const now = performance.now();
        if (!this.modelAudioThisTurn) {
          this.modelAudioThisTurn = true;
          if (this.userSpokeSinceModel && this.lastVoiceAt > 0) {
            this.metric("speech_end_to_first_audio", now - this.lastVoiceAt, {
              turn: this.turn,
              with_tool: this.toolRespondedAt > 0,
            });
            this.userSpokeSinceModel = false;
          }
        }
        if (this.toolRespondedAt > 0) {
          this.metric("tool_response_to_first_audio", now - this.toolRespondedAt, { turn: this.turn });
          this.toolRespondedAt = 0;
        }
        const buf = base64ToBuffer(data);
        this.player?.port.postMessage({ type: "push", data: buf }, [buf]);
      }
      if (sc.inputTranscription?.text) this.opts.onCaption("user", sc.inputTranscription.text, this.turn);
      if (sc.outputTranscription?.text) this.opts.onCaption("ai", sc.outputTranscription.text, this.turn);
      if (sc.turnComplete || sc.interrupted) {
        this.modelAudioThisTurn = false;
        this.turn += 1;
      }
    }

    for (const call of m.toolCall?.functionCalls ?? []) {
      const name = call.name ?? "";
      const args = (call.args ?? {}) as Record<string, unknown>;
      const t0 = performance.now();
      let result: ToolResult;
      try {
        result = await apiPost<ToolResult>(this.opts.toolUrl(name), args, { keepalive: true });
      } catch (err) {
        result = { ok: false, error: "tool_failed", detail: String(err) };
      }
      const tFetched = performance.now();
      this.metric("tool_http", tFetched - t0, { tool: name });
      await this.opts.onToolResult(name, args, result);
      this.metric("tool_response_to_card", performance.now() - tFetched, { tool: name });
      // Strip ui_blocks: the model only needs facts/speech; keeps the payload small.
      const { ui_blocks: _blocks, ...forModel } = result;
      this.session?.sendToolResponse({
        functionResponses: [
          {
            id: call.id,
            name,
            response: forModel,
            ...(this.opts.behavior === "non_blocking"
              ? { scheduling: FunctionResponseScheduling[this.opts.scheduling] }
              : {}),
          },
        ],
      });
      this.toolRespondedAt = performance.now();
      this.metric("tool_call_to_response", this.toolRespondedAt - t0, { tool: name });
    }
  }

  private metric(name: string, ms: number, meta?: Record<string, unknown>): void {
    this.opts.onMetric({ name, ms, meta });
  }

  /** Text fallback ("Yozib so'rash"). */
  sendText(text: string): void {
    this.userSpokeSinceModel = true;
    this.lastVoiceAt = performance.now();
    this.session?.sendRealtimeInput({ text });
  }

  async stop(): Promise<void> {
    this.closedByUser = true;
    this.session?.close();
    this.session = null;
    this.stream?.getTracks().forEach((t) => t.stop());
    await Promise.allSettled([this.micCtx?.close(), this.playCtx?.close()]);
    this.micCtx = this.playCtx = null;
    this.opts.onStatus("closed");
  }
}
