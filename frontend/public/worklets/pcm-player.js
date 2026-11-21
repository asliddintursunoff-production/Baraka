// AudioWorklet: 24 kHz PCM16 playback through a ring buffer. Plays as soon as the first
// chunk arrives; {type:"clear"} empties the buffer instantly (barge-in).
class PcmPlayer extends AudioWorkletProcessor {
  constructor() {
    super();
    this.buf = new Float32Array(sampleRate * 60); // 60 s capacity
    this.r = 0;
    this.w = 0;
    this.playing = false;
    this.port.onmessage = (e) => {
      const msg = e.data;
      if (msg.type === "push") {
        const pcm = new Int16Array(msg.data);
        for (let i = 0; i < pcm.length; i++) {
          this.buf[this.w] = pcm[i] / 0x8000;
          this.w = (this.w + 1) % this.buf.length;
          if (this.w === this.r) this.r = (this.r + 1) % this.buf.length; // overflow: drop oldest
        }
      } else if (msg.type === "clear") {
        this.r = this.w;
        if (this.playing) {
          this.playing = false;
          this.port.postMessage({ type: "cleared" });
        }
      }
    };
  }

  process(_inputs, outputs) {
    const out = outputs[0][0];
    let i = 0;
    for (; i < out.length && this.r !== this.w; i++) {
      out[i] = this.buf[this.r];
      this.r = (this.r + 1) % this.buf.length;
    }
    if (i > 0 && !this.playing) {
      this.playing = true;
      this.port.postMessage({ type: "playing", t: currentTime });
    }
    for (; i < out.length; i++) out[i] = 0;
    if (this.playing && this.r === this.w) {
      this.playing = false;
      this.port.postMessage({ type: "drained" });
    }
    for (let c = 1; c < outputs[0].length; c++) outputs[0][c].set(out);
    return true;
  }
}
registerProcessor("pcm-player", PcmPlayer);
