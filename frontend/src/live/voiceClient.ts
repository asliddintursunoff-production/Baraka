/**
 * Browser <-> Gemini Live voice client.
 *
 * - On `prepare()`: mic permission, token fetch and AudioWorklet loading run in parallel,
 *   then the WebSocket is opened, so the session is ready before the user speaks.
 * - Mic: AudioWorklet -> 16 kHz PCM16, 20 ms frames, streamed continuously.
 * - Playback: 24 kHz ring-buffer worklet, starts on the first chunk; cleared on `interrupted`
 *   and on `stopPlayback()`.
 * - Tool calls: POST to the backend (same origin, session cookie), render the ui_blocks right
 *   away, then `sendToolResponse` (without `ui_blocks` / `answer`).
 * - Reconnect: when the server closes an established session, a new token (`getToken`) is
 *   taken and the session is resumed with the last resumption handle.
 * Audio never passes through Django; Django only mints the token and runs tools.
 */
import {
  FunctionResponseScheduling,
  GoogleGenAI,
  Modality,
  type LiveServerMessage,
  type Session,
} from "@google/genai";

import { ApiError, apiPost } from "@/lib/api";

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
  /** Token source for `prepare()` (when no token promise is passed) and for reconnects.
   * Default: POST `tokenUrl`. */
  getToken?: () => Promise<TokenResponse>;
  /** Add `_user_utterance` (latest user input) and `_channel: "voice"` to every tool body. */
  annotateToolCalls?: boolean;
  /** Keep the session (text in, voice out) when the microphone is unavailable. Default false:
   * `prepare()` rejects. */
  micOptional?: boolean;
  onMicError?: (err: unknown) => void;
  /** A tool call arrived (before the HTTP request). */
  onToolCall?: (name: string, args: Record<string, unknown>) => void;
  /** Mic voice activity (frame RMS, with a short hangover). */
  onUserSpeaking?: (speaking: boolean) => void;
  /** A model turn ended (`turnComplete` or `interrupted`); `turn` is the finished turn. */
  onTurnComplete?: (turn: number, interrupted: boolean) => void;
}

const VOICE_RMS = 0.02; // frame RMS above this counts as speech (for speech_end timing)
const VOICE_HANGOVER_MS = 700; // onUserSpeaking(false) after this much silence

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

  // latest user input (for `_user_utterance`), keyed by turn so late chunks still append
  private utterance = "";
  private utteranceTurn = -1;
  private userVoice = false;
  /** `stopPlayback()` was pressed: drop the rest of this model turn's audio. */
  private muteTurn = false;

  constructor(opts: VoiceClientOptions) {
    this.opts = opts;
  }

  /** Parallel: mic + token + worklets; then connect. Resolves when the session is ready
   * (or quietly when `stop()` was called meanwhile). */
  async prepare(tOpen = performance.now(), prefetchedToken?: Promise<TokenResponse>): Promise<void> {
    this.tOpen = tOpen;
    this.closedByUser = false;
    this.opts.onStatus("preparing");
    let micP: Promise<MediaStream | null> | undefined;
    try {
      const tokenP = prefetchedToken ?? this.nextToken();
      micP = this.openMic();
      this.micCtx = new AudioContext();
      this.playCtx = new AudioContext({ sampleRate: 24000 });
      const workletsP = Promise.all([
        this.micCtx.audioWorklet.addModule("/worklets/mic-processor.js"),
        this.playCtx.audioWorklet.addModule("/worklets/pcm-player.js"),
      ]);
      const [token, stream] = await Promise.all([tokenP, micP, workletsP]);
      if (this.closedByUser) return;
      this.metric("token_ready", performance.now() - this.tOpen, { mint_ms: token.mint_ms, mic: !!stream });
      this.setupPlayer();
      if (stream) this.setupMic(stream);
      await this.connect(token, false);
    } catch (err) {
      if (this.closedByUser) return;
      this.releaseMedia();
      // The token can fail while the permission prompt is still open: release a late stream.
      void micP?.then(
        (s) => s?.getTracks().forEach((t) => t.stop()),
        () => undefined,
      );
      this.opts.onStatus("error", errorText(err));
      throw err;
    }
  }

  fetchToken(): Promise<TokenResponse> {
    return apiPost<TokenResponse>(this.opts.tokenUrl, { behavior: this.opts.behavior });
  }

  private nextToken(): Promise<TokenResponse> {
    return this.opts.getToken ? this.opts.getToken() : this.fetchToken();
  }

  /** getUserMedia; the stream is stored at once so `stop()` can always release it. */
  private async openMic(): Promise<MediaStream | null> {
    try {
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Mikrofon mavjud emas");
      const stream = await navigator.mediaDevices.getUserMedia({
        audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      });
      if (this.closedByUser) {
        stream.getTracks().forEach((t) => t.stop());
        return null;
      }
      this.stream = stream;
      return stream;
    } catch (err) {
      if (!this.opts.micOptional) throw err;
      this.metric("mic_unavailable", 0, { error: err instanceof Error ? err.name : String(err) });
      this.opts.onMicError?.(err);
      return null;
    }
  }

  private async connect(token: TokenResponse, isReconnect: boolean): Promise<void> {
    this.opts.onStatus("connecting", isReconnect ? "qayta ulanmoqda" : undefined);
    const ai = new GoogleGenAI({ apiKey: token.token, httpOptions: { apiVersion: "v1beta" } });
    const tConnect = performance.now();
    const tStart = isReconnect ? tConnect : this.tOpen;
    let resolveReady: () => void = () => {};
    let rejectReady: (e: Error) => void = () => {};
    const readyP = new Promise<void>((res, rej) => {
      resolveReady = res;
      rejectReady = rej;
    });
    this.ready = false;
    const session = await ai.live.connect({
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
            this.metric(isReconnect ? "reconnect_ready" : "session_ready", performance.now() - tStart, {
              connect_ms: Math.round(performance.now() - tConnect),
            });
            this.opts.onStatus("ready");
            resolveReady();
          }
          void this.onMessage(m);
        },
        onerror: (e: ErrorEvent) => {
          if (this.closedByUser) return;
          // Before setup: prepare()/reconnect() report it. After: onclose reconnects.
          rejectReady(new Error(e.message || "Live xatosi"));
          this.metric("ws_error", 0, { message: e.message, ready: this.ready });
        },
        onclose: (e: CloseEvent) => {
          const wasReady = this.ready;
          this.ready = false;
          this.session = null;
          if (this.closedByUser) {
            rejectReady(new Error("closed"));
          } else if (!wasReady) {
            // prepare()/reconnect() report the failure.
            rejectReady(new Error(e.reason || "ulanib bo'lmadi"));
          } else {
            // Server closed an established session (goAway / ~10 min limit): new token, resume.
            this.opts.onStatus("connecting", e.reason || "qayta ulanmoqda");
            void this.reconnect();
          }
        },
      },
    });
    if (this.closedByUser) {
      session.close();
      return;
    }
    this.session = session;
    try {
      await readyP;
    } catch (err) {
      if (this.closedByUser) return;
      throw err;
    }
  }

  private async reconnect(): Promise<void> {
    try {
      const token = await this.nextToken();
      if (this.closedByUser) return;
      await this.connect(token, true);
    } catch (err) {
      if (!this.closedByUser) this.opts.onStatus("error", errorText(err));
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
      const now = performance.now();
      if (e.data.rms > VOICE_RMS) {
        this.lastVoiceAt = now;
        this.userSpokeSinceModel = true;
        if (!this.userVoice) {
          this.userVoice = true;
          this.opts.onUserSpeaking?.(true);
        }
      } else if (this.userVoice && now - this.lastVoiceAt > VOICE_HANGOVER_MS) {
        this.userVoice = false;
        this.opts.onUserSpeaking?.(false);
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
        if (this.muteTurn) continue;
        const buf = base64ToBuffer(data);
        this.player?.port.postMessage({ type: "push", data: buf }, [buf]);
      }
      const heard = sc.inputTranscription?.text;
      if (heard) {
        if (this.utteranceTurn !== this.turn) {
          this.utterance = "";
          this.utteranceTurn = this.turn;
        }
        this.utterance += heard;
        this.opts.onCaption("user", heard, this.turn);
      }
      if (sc.outputTranscription?.text) this.opts.onCaption("ai", sc.outputTranscription.text, this.turn);
      if (sc.turnComplete || sc.interrupted) {
        const done = this.turn;
        this.modelAudioThisTurn = false;
        this.muteTurn = false;
        this.turn += 1;
        this.opts.onTurnComplete?.(done, !!sc.interrupted);
      }
    }

    for (const call of m.toolCall?.functionCalls ?? []) {
      const name = call.name ?? "";
      const args = (call.args ?? {}) as Record<string, unknown>;
      const t0 = performance.now();
      this.opts.onToolCall?.(name, args);
      // "ha" may be transcribed after the model already called confirm_plan: wait briefly
      // for this turn's transcription so the backend sees the real answer.
      for (let i = 0; i < 6 && name === "confirm_plan" && this.utteranceTurn !== this.turn; i++) {
        await new Promise((r) => setTimeout(r, 100));
      }
      const body = this.opts.annotateToolCalls
        ? { ...args, _user_utterance: this.utterance.trim(), _channel: "voice" }
        : args;
      let result: ToolResult;
      try {
        result = await apiPost<ToolResult>(this.opts.toolUrl(name), body, { keepalive: true });
      } catch (err) {
        // A 4xx body ({ok:false, error:"bad_args", detail}) tells the model what was wrong.
        result =
          err instanceof ApiError && err.body && typeof err.body === "object"
            ? { ok: false, ...(err.body as Record<string, unknown>) }
            : { ok: false, error: "tool_failed", detail: String(err) };
      }
      const tFetched = performance.now();
      this.metric("tool_http", tFetched - t0, { tool: name, ok: result.ok !== false });
      try {
        await this.opts.onToolResult(name, args, result);
      } catch {
        /* a rendering problem must not block the model's answer */
      }
      this.metric("tool_response_to_card", performance.now() - tFetched, { tool: name });
      // The model only needs facts/speech/say: no UI blocks, no long answer templates.
      const { ui_blocks: _blocks, answer: _answer, ...forModel } = result;
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
    if (this.utteranceTurn !== this.turn) this.utterance = "";
    this.utterance = this.utterance ? `${this.utterance} ${text}` : text;
    this.utteranceTurn = this.turn;
    this.session?.sendRealtimeInput({ text });
  }

  /** True when a session is open (text can be sent). */
  get connected(): boolean {
    return this.session !== null && this.ready;
  }

  /** "To'xtatish": silence the AI now. The rest of the current model turn is dropped too,
   * so playback does not restart with the next chunk. */
  stopPlayback(): void {
    if (this.modelAudioThisTurn) this.muteTurn = true;
    this.player?.port.postMessage({ type: "clear" });
  }

  /** Browsers start an AudioContext suspended without a user gesture (e.g. a page reload). */
  get audioSuspended(): boolean {
    return [this.micCtx, this.playCtx].some((c) => c?.state === "suspended");
  }

  /** Call from a user gesture (click / key press) when `audioSuspended` is true. */
  async resumeAudio(): Promise<void> {
    await Promise.allSettled([this.micCtx?.resume(), this.playCtx?.resume()]);
  }

  private releaseMedia(): void {
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    const ctxs = [this.micCtx, this.playCtx];
    this.micCtx = this.playCtx = null;
    this.player = this.mic = null;
    for (const c of ctxs) c?.close().catch(() => undefined);
  }

  async stop(): Promise<void> {
    this.closedByUser = true;
    this.session?.close();
    this.session = null;
    this.ready = false;
    this.stream?.getTracks().forEach((t) => t.stop());
    this.stream = null;
    const ctxs = [this.micCtx, this.playCtx];
    this.micCtx = this.playCtx = null;
    this.player = this.mic = null;
    await Promise.allSettled(ctxs.map((c) => c?.close()));
    this.opts.onStatus("closed");
  }
}

function errorText(err: unknown): string {
  if (err instanceof ApiError) {
    const body = err.body as { message?: unknown } | null;
    if (body && typeof body.message === "string") return body.message;
  }
  return err instanceof Error ? err.message : String(err);
}
