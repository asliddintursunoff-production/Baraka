// AudioWorklet: microphone -> 16 kHz mono PCM16 frames (default 20 ms), sent continuously.
// Downsampling uses box-filter decimation (cheap low-pass), good enough for speech.
// Each frame also carries `band`: the RMS of the speech band (~200-4000 Hz, one-pole filters),
// so fans/hum (low) and hiss (high) count less in the voice detector.
class MicProcessor extends AudioWorkletProcessor {
  constructor(options) {
    super();
    const frameMs = (options && options.processorOptions && options.processorOptions.frameMs) || 20;
    this.ratio = sampleRate / 16000;
    this.frame = new Int16Array(16 * frameMs);
    this.idx = 0;
    this.acc = 0;
    this.accN = 0;
    this.g = 0; // input samples consumed
    this.next = this.ratio; // input index at which the next output sample is due
    this.sq = 0; // sum of squares for RMS of the current frame
    this.bsq = 0; // same, speech band
    const dt = 1 / 16000;
    const rcHp = 1 / (2 * Math.PI * 200);
    const rcLp = 1 / (2 * Math.PI * 4000);
    this.aHp = rcHp / (rcHp + dt);
    this.aLp = dt / (rcLp + dt);
    this.hpY = 0;
    this.hpX = 0;
    this.lpY = 0;
  }

  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (!ch) return true;
    for (let i = 0; i < ch.length; i++) {
      this.acc += ch[i];
      this.accN++;
      this.g++;
      if (this.g >= this.next) {
        let s = this.acc / this.accN;
        this.acc = 0;
        this.accN = 0;
        this.next += this.ratio;
        if (s > 1) s = 1;
        else if (s < -1) s = -1;
        this.sq += s * s;
        this.hpY = this.aHp * (this.hpY + s - this.hpX);
        this.hpX = s;
        this.lpY += this.aLp * (this.hpY - this.lpY);
        this.bsq += this.lpY * this.lpY;
        this.frame[this.idx++] = s < 0 ? s * 0x8000 : s * 0x7fff;
        if (this.idx === this.frame.length) {
          const rms = Math.sqrt(this.sq / this.frame.length);
          const band = Math.sqrt(this.bsq / this.frame.length);
          const out = this.frame.slice(0);
          this.port.postMessage({ pcm: out.buffer, rms, band }, [out.buffer]);
          this.idx = 0;
          this.sq = 0;
          this.bsq = 0;
        }
      }
    }
    return true;
  }
}
registerProcessor("mic-processor", MicProcessor);
