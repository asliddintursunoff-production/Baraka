import { describe, expect, it } from "vitest";

import { base64ToBuffer, bufferToBase64 } from "./pcm";

describe("pcm base64", () => {
  it("round-trips PCM16 frames", () => {
    const pcm = new Int16Array([0, 1, -1, 32767, -32768, 1234]);
    const back = new Int16Array(base64ToBuffer(bufferToBase64(pcm.buffer)));
    expect(Array.from(back)).toEqual(Array.from(pcm));
  });

  it("handles 40 ms frames (640 samples)", () => {
    const pcm = new Int16Array(640).map((_, i) => (i * 37) % 30000);
    const back = new Int16Array(base64ToBuffer(bufferToBase64(pcm.buffer)));
    expect(back.length).toBe(640);
    expect(back[639]).toBe(pcm[639]);
  });
});
