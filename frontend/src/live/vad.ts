/**
 * Adaptive voice detector for the Live mic (same behaviour on every device).
 *
 * - Works in dB relative to a noise floor that is tracked all the time (falls fast, rises
 *   slowly and only outside speech), so a sensitive mic / aggressive AGC (high floor) and a
 *   quiet mic (low floor) behave alike.
 * - Opens on >= 8 of the last 12 frames (20 ms each) clearly above the floor: clicks, knocks
 *   and dishes (short bursts) never open it.
 * - Closes after HANGOVER_MS below the lower threshold, so pauses between words are kept.
 * - While our own audio plays (clip / AI) it needs ECHO_EXTRA_DB more: echo is not a question,
 *   but the user's voice close to the mic still is (barge-in).
 */
export const FRAME_MS = 20;
const SNR_ON_DB = 11;
const SNR_OFF_DB = 6;
const ECHO_EXTRA_DB = 9;
const ABS_MIN_DB = -62; // nothing below this is speech, however quiet the room
const FLOOR_MIN_DB = -80;
const FLOOR_MAX_DB = -28;
const OPEN_WINDOW = 12;
const OPEN_NEED = 8;
const HANGOVER_MS = 800;
const FLOOR_RISE_DB_PER_S = 1.5;
const INIT_MS = 400;
const STEADY_FRAMES = 50; // 1 s
const STEADY_STD_DB = 2.5; // speech moves > 5 dB within a second; a fan / hood / hum does not

export const toDb = (x: number): number => 20 * Math.log10(Math.max(x, 1e-6));

export class Vad {
  floor = -60;
  open = false;
  private recent: boolean[] = [];
  private belowMs = 0;
  private initLevels: number[] = [];
  private t = 0;
  private hist: number[] = [];

  /** One 20 ms frame. `level` = speech-band RMS (0..1); `playing` = our audio is audible. */
  push(level: number, playing = false): boolean {
    const db = toDb(level);
    this.t += FRAME_MS;
    if (this.t <= INIT_MS) {
      this.initLevels.push(db);
      const s = [...this.initLevels].sort((a, b) => a - b);
      // the quietest third of the first 400 ms: the user may already be talking
      this.floor = clamp(s[Math.floor(s.length / 3)] ?? db, FLOOR_MIN_DB, FLOOR_MAX_DB);
    }
    const extra = playing ? ECHO_EXTRA_DB : 0;
    const on = db > Math.max(this.floor + SNR_ON_DB + extra, ABS_MIN_DB + extra);
    const stillOn = db > Math.max(this.floor + SNR_OFF_DB + extra, ABS_MIN_DB);
    this.recent.push(on);
    if (this.recent.length > OPEN_WINDOW) this.recent.shift();
    if (!this.open) {
      if (this.recent.filter(Boolean).length >= OPEN_NEED) {
        this.open = true;
        this.belowMs = 0;
      }
    } else if (stillOn) {
      this.belowMs = 0;
    } else {
      this.belowMs += FRAME_MS;
      if (this.belowMs >= HANGOVER_MS) {
        this.open = false;
        this.recent = [];
      }
    }
    this.hist.push(db);
    if (this.hist.length > STEADY_FRAMES) this.hist.shift();
    const steady = this.hist.length === STEADY_FRAMES && std(this.hist) < STEADY_STD_DB;
    // noise floor: down fast whenever quieter; up slowly outside speech; a steady sound (not
    // speech) pulls it up fast, even while open, so a fan switched on can't keep the mic open
    if (steady && db > this.floor) {
      this.floor = Math.min(FLOOR_MAX_DB, this.floor + (db - this.floor) * 0.1);
      if (this.open && db < this.floor + SNR_ON_DB) {
        this.open = false;
        this.recent = [];
      }
    } else if (db < this.floor)
      this.floor = Math.max(FLOOR_MIN_DB, this.floor + (db - this.floor) * 0.2);
    else if (!this.open && !on)
      this.floor = Math.min(FLOOR_MAX_DB, this.floor + (FLOOR_RISE_DB_PER_S * FRAME_MS) / 1000);
    return this.open;
  }

  /** 0..1 for the level meter: 0 at the floor, 1 at floor + 30 dB. */
  meter(level: number): number {
    return clamp((toDb(level) - this.floor) / 30, 0, 1);
  }
}

/**
 * Digital gain for quiet mics: speech peaks are brought towards -20 dBFS (max x6, never above
 * 1), so Live's transcription hears a quiet phone as well as a loud laptop.
 */
export class AutoGain {
  peakDb = -30;
  gain(): number {
    return clamp(10 ** ((-20 - this.peakDb) / 20), 1, 6);
  }
  /** Feed the full-band frame RMS of frames the VAD classed as speech. */
  speech(rms: number): void {
    const db = toDb(rms);
    this.peakDb =
      db > this.peakDb
        ? this.peakDb + (db - this.peakDb) * 0.3
        : this.peakDb + (db - this.peakDb) * 0.01;
  }
  apply(pcm: ArrayBuffer): ArrayBuffer {
    const g = this.gain();
    if (g <= 1.01) return pcm;
    const src = new Int16Array(pcm);
    const out = new Int16Array(src.length);
    for (let i = 0; i < src.length; i++)
      out[i] = clamp(Math.round((src[i] ?? 0) * g), -32768, 32767);
    return out.buffer;
  }
}

const std = (xs: number[]): number => {
  const m = xs.reduce((a, b) => a + b, 0) / xs.length;
  return Math.sqrt(xs.reduce((a, b) => a + (b - m) ** 2, 0) / xs.length);
};

const clamp = (x: number, lo: number, hi: number): number => Math.min(hi, Math.max(lo, x));
