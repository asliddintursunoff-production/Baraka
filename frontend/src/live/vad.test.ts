import { describe, expect, it } from "vitest";

import { AutoGain, Vad } from "./vad";

const db = (d: number) => 10 ** (d / 20);
const run = (v: Vad, level: number, frames: number, playing = false) => {
  let open = false;
  for (let i = 0; i < frames; i++) open = v.push(level, playing) || open;
  return open;
};
/** speech: syllables ~120 ms loud / 60 ms softer (real speech is never a steady level) */
const talk = (v: Vad, level: number, frames: number, playing = false) => {
  let open = false;
  for (let i = 0; i < frames; i++) open = v.push(i % 9 < 6 ? level : level / 3, playing) || open;
  return open;
};

describe("Vad", () => {
  for (const [name, noise] of [
    ["quiet phone", -70],
    ["normal laptop", -55],
    ["sensitive mic / loud room", -35],
  ] as const) {
    it(`${name}: room noise stays closed, speech above it opens`, () => {
      const v = new Vad();
      expect(run(v, db(noise), 150)).toBe(false); // 3 s of steady noise
      expect(talk(v, db(noise + 18), 20)).toBe(true); // 400 ms of speech
    });
  }

  it("clicks and knocks (short bursts) never open", () => {
    const v = new Vad();
    run(v, db(-60), 50);
    for (let k = 0; k < 10; k++) {
      expect(run(v, db(-20), 4)).toBe(false); // 80 ms bang
      run(v, db(-60), 30);
    }
  });

  it("pauses between words are kept; closes after silence", () => {
    const v = new Vad();
    run(v, db(-60), 50);
    talk(v, db(-35), 20);
    expect(run(v, db(-60), 25)).toBe(true); // 500 ms pause: still open
    run(v, db(-60), 30);
    expect(v.open).toBe(false);
  });

  it("our own echo while a clip plays does not open; a close voice does (barge-in)", () => {
    const v = new Vad();
    run(v, db(-60), 50);
    expect(run(v, db(-52), 40, true)).toBe(false);
    expect(talk(v, db(-30), 20, true)).toBe(true);
  });

  it("noise floor follows a room that gets louder", () => {
    const v = new Vad();
    run(v, db(-65), 50);
    run(v, db(-50), 1500); // 30 s: a fan was switched on
    expect(v.open).toBe(false);
    expect(run(v, db(-48), 40)).toBe(false);
    expect(talk(v, db(-30), 30)).toBe(true); // the user still gets through over the fan
  });

  it("a long sentence is not cut by the steady-noise rule", () => {
    const v = new Vad();
    run(v, db(-60), 50);
    talk(v, db(-30), 20);
    talk(v, db(-30), 400); // 8 s
    expect(v.open).toBe(true);
  });
});

describe("AutoGain", () => {
  it("boosts a quiet mic, leaves a loud one", () => {
    const g = new AutoGain();
    for (let i = 0; i < 100; i++) g.speech(db(-38));
    expect(g.gain()).toBeGreaterThan(4);
    const h = new AutoGain();
    for (let i = 0; i < 100; i++) h.speech(db(-15));
    expect(h.gain()).toBe(1);
  });
});
