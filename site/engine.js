// =============================================================================
//  A Whale's Heart — web build · the sound engine
//
//  SuperCollider's own WebAssembly build runs sclang AND scsynth in this tab (engine/, develop
//  @ 5d47207, unmodified). sclang runs sc/whaleheart.scd, the desktop file with the web
//  substitutions of tools/build_web.py, so the SynthDefs and OSCdefs are the desktop code.
//
//  This file plays the part of bridge.py: the page still calls scPost('/api/gate', {...}) and the
//  same OSC (/whale/gate, /whale/play, …) goes into sclang with sclang.sendOsc() → the OSCdefs.
//  Differences, because this is a browser:
//    · SuperCollider starts on the first click or key press (browsers play nothing before one);
//    · Buffer.read needs a file system, so the page decodes the heartbeat, resamples it to
//      scsynth's rate and writes it into ~hbBuf with /b_setn (Dark Re-Wilding's route);
//    · stereo only (a browser gives two channels).
//
//  Adapted from dark_ocean's web_implementation/engine.js; the start-up guards are its own
//  (lab/PORTING_LOG.md §2 and §6 in hello_darksonification).
// =============================================================================
import { oscMessage, f, i, s } from "./osc.js";

const ENGINE_DIR = new URL("./engine/", import.meta.url);
const SC_FILE = new URL("./sc/whaleheart.scd", import.meta.url);
const SAMPLE = new URL("./sc/whale_one_heart.wav", import.meta.url);
const CHUNK = 4096;                              // floats per /b_setn (Re-Wilding's probe: fast and safe)

// This build's scsynth.getWorkletNode() throws (dark_ocean PORTING_LOG §2, gotcha 2), so remember
// whichever AudioWorkletNode connects to the speakers: that is scsynth.
const toDestination = [];
const nativeConnect = AudioNode.prototype.connect;
AudioNode.prototype.connect = function (dest, ...rest) {
  if (dest instanceof AudioDestinationNode) toDestination.push(this);
  return nativeConnect.call(this, dest, ...rest);
};

// OSC packets as bytes, and the two the start sequence needs to recognise (see instantiate()).
const asBytes = (p) => (p instanceof Uint8Array ? p : new Uint8Array(p.buffer || p));
const head = (p, n) => { const b = asBytes(p); let t = ""; for (let k = 0; k < Math.min(n, b.length); k++) t += String.fromCharCode(b[k]); return t; };
function notifyFlag(p) {                         // "/notify\0" ",i…" + int32 flag → the flag; anything else → null
  const b = asBytes(p);
  if (b.length < 16 || head(b, 8) !== "/notify\0" || !head(b, 10).endsWith(",i")) return null;
  return (b[12] << 24) | (b[13] << 16) | (b[14] << 8) | b[15];
}
const isDoneNotify = (p) => /^\/done\0+,s[^\0]*\0+\/notify\0/.test(head(p, 32));

class WhaleEngine {
  constructor() {
    this.state = "loading";
    this.error = null;
    this.log = [];                               // last post-window lines: whaleEngine.log
    this.watchers = [];
    this.mode = "stereo";                        // the last /api/setmode, replayed after a (re)start
    this.transport = null;                       // the last play / pause / stop
    this.attempt = 0;
    this.bootAllowed = 0;
    for (const ev of ["pointerdown", "keydown"]) document.addEventListener(ev, () => this.firstGesture(), true);
    window.addEventListener("error", (ev) => {   // scsynth dying in a worker surfaces here too
      const where = String(ev.filename || (ev.error && ev.error.filename) || "");
      if (this.crash && where.includes("/engine/scsynth.js")) this.crash(new Error(`scsynth stopped: ${ev.message}`));
    });
    this.setState("loading");
  }

  // ------------------------------------------------------------------ status
  setState(state, error) {
    this.state = state;
    if (error) this.error = error;
    try { window.whaleStatus && window.whaleStatus(state); } catch (_) {}
  }
  firstGesture() {
    if (this.ctx && this.ctx.state !== "running") this.ctx.resume().catch(() => {});
    if (this._boot || this.state === "error") return;
    this.boot();
  }

  // ------------------------------------------------------------------ post window
  post_(src, text) {
    for (const line of String(text).split("\n")) {
      if (!line) continue;
      this.log.push(`[${src}] ${line}`);
      if (this.log.length > 800) this.log.splice(0, this.log.length - 800);
      if (/ERROR|FAILURE|not installed/.test(line)) console.warn(`[SuperCollider] ${line}`);
      for (const w of [...this.watchers]) {
        if (w.re.test(line)) { this.watchers.splice(this.watchers.indexOf(w), 1); w.resolve(line); }
      }
    }
  }
  until(re, ms) {
    return new Promise((resolve, reject) => {
      const w = { re, resolve };
      this.watchers.push(w);
      setTimeout(() => {
        const k = this.watchers.indexOf(w);
        if (k >= 0) { this.watchers.splice(k, 1); reject(new Error(`timed out waiting for ${re}`)); }
      }, ms);
    });
  }
  // Ask sclang for a value: it posts "<tag> <value>", read back from the post window.
  async ask(expr, ms = 3000) {
    const tag = "WH" + Math.random().toString(36).slice(2, 8);
    const answer = this.until(new RegExp(`^${tag} `), ms);
    this.sclang.runCode(`("${tag} " ++ (${expr})).postln;`);
    return (await answer).slice(tag.length + 1);
  }
  // Ask sclang a question until it answers "true".
  async poll(expr, ms, every = 300, alive = () => true) {
    const end = performance.now() + ms;
    for (;;) {
      if (!alive()) throw new Error("superseded by a fresh SuperCollider");
      const tag = "WH" + Math.random().toString(36).slice(2, 8);
      const answer = this.until(new RegExp(`^${tag} (true|false)$`), every + 500).then((l) => l.endsWith("true"), () => false);
      try { this.sclang.runCode(`("${tag} " ++ (${expr}).asBoolean).postln;`); } catch (_) {}
      if (await answer) return;
      if (performance.now() > end) throw new Error(`SuperCollider never reported: ${expr}`);
      await new Promise((r) => setTimeout(r, every));
    }
  }

  // ------------------------------------------------------------------ load (no audio yet)
  async instantiate() {
    const locateFile = (p) => new URL(p, ENGINE_DIR).href;   // sclang.data would otherwise resolve against the page
    const [{ default: ScSynth }, { default: ScLang }] = await Promise.all([
      import(new URL("scsynth.js", ENGINE_DIR).href), import(new URL("sclang.js", ENGINE_DIR).href),
    ]);
    let synth = null;
    const live = () => synth !== null && this.scsynth === synth;
    const printErr = (t) => {
      console.error(t);
      if (!/worker sent an error/.test(t) || !live()) return;
      if (this.crash) this.crash(new Error(`scsynth stopped: ${t}`));
      else if (this.state === "ready") this.setState("error", `scsynth stopped: ${t}`);
    };
    synth = await ScSynth({ locateFile, printErr });
    this.scsynth = synth;
    const lang = await ScLang({ locateFile });
    this.sclang = lang;
    lang.printCallback = (t) => { if (live()) this.post_("lang", t); };
    synth.onStdout = (t) => { if (live()) this.post_("synth", t); };
    synth.onPrint = (t) => { if (live()) this.post_("synth", t); };
    // THE SECOND /notify (dark_ocean PORTING_LOG §6): this scsynth build dies when sclang registers
    // for notifications twice. Only the first `/notify 1` reaches scsynth; a repeat is answered here
    // with scsynth's own first reply.
    let registered = false, notifyReply = null;
    lang.onOsc = (osc) => {                                         // sclang → scsynth
      if (!live()) return;
      const n = notifyFlag(osc);
      if (n === 1) {
        if (registered) { if (notifyReply) lang.sendOsc(notifyReply.slice()); return; }
        registered = true;
      } else if (n === 0) registered = false;
      synth.sendOsc(osc);
    };
    synth.onOscReply = (r) => {                                     // scsynth → sclang
      if (!live()) return;
      if (!notifyReply && isDoneNotify(r)) notifyReply = asBytes(r).slice();
      lang.sendOsc(r);
    };
    window.bootServer = (opts) => {              // Server:bootServerApp calls this; only the running attempt may boot
      if (this.bootAllowed !== this.attempt) return;
      this.bootAllowed = 0;
      setTimeout(() => { if (live()) synth.boot(opts); }, 100);
    };
    lang.bootInterpreter();
    await this.poll("true", 45000, 400);         // the interpreter answers = class library compiled
  }
  preload() {
    if (this._preload) return this._preload;
    this._preload = (async () => {
      if (!self.crossOriginIsolated) throw new Error("this browser did not allow SharedArrayBuffer");
      const [code, wav] = await Promise.all([
        fetch(SC_FILE).then((r) => { if (!r.ok) throw new Error(`whaleheart.scd: HTTP ${r.status}`); return r.text(); }),
        fetch(SAMPLE).then((r) => { if (!r.ok) throw new Error(`whale_one_heart.wav: HTTP ${r.status}`); return r.arrayBuffer(); }),
      ]);
      this.code = code;
      // Decode once here; it is resampled to scsynth's own rate once that is known (fill()).
      this.sample = await new OfflineAudioContext(2, 1, 44100).decodeAudioData(wav);
      await this.instantiate();
      this.setState("idle");
    })().catch((e) => { console.error(e); this.setState("error", e.message); throw e; });
    return this._preload;
  }

  // ------------------------------------------------------------------ boot (a click asked for sound)
  // A start whose scsynth dies or stalls retires that SuperCollider and starts a fresh one. Two tries.
  boot() {
    if (this._boot) return this._boot;
    this._boot = (async () => {
      await this.preload();
      for (let attempt = 1; ; attempt++) {
        try { await this.start(); return; }
        catch (e) {
          if (attempt >= 2) throw e;
          console.warn(`[whale] SuperCollider did not start (${e.message}); starting a fresh one`);
          this.retire();
          await this.instantiate();
        }
      }
    })().catch((e) => { console.error(e); this.setState("error", e.message); });
    return this._boot;
  }
  start() {
    const my = ++this.attempt, alive = () => this.attempt === my;
    return new Promise((resolve, reject) => {
      this.crash = reject;
      (async () => {
        this.setState("booting");
        this.bootAllowed = my;
        this.sclang.runCode(`~webSeconds = ${this.sample.duration};`);
        this.sclang.runCode(this.code);          // s.waitForBoot → bootServer() → scsynth in an AudioWorklet
        await this.poll("~whaleReady == true", 25000, 300, alive);   // SynthDefs, buffer, OSCdefs: all there
        if (!alive()) return;
        const nodes = toDestination.filter((n) => n instanceof AudioWorkletNode);
        this.node = nodes[nodes.length - 1] || null;
        this.ctx = this.node ? this.node.context : null;
        if (this.ctx && this.ctx.state !== "running") { try { await this.ctx.resume(); } catch (_) {} }
        await this.fill();
        if (!alive()) return;
        this.setState("ready");
        this.replay();
      })().then(resolve, reject);
    }).finally(() => { if (alive()) this.crash = null; });
  }
  // Write the heartbeat into ~hbBuf: resampled to scsynth's rate, interleaved L R L R, in chunks.
  async fill() {
    const [bufnum, frames, rate] = (await this.ask(`[~hbBuf.bufnum, ~hbBuf.numFrames, s.sampleRate].join(" ")`))
      .split(" ").map(Number);
    const off = new OfflineAudioContext(2, frames, rate);
    const src = off.createBufferSource();
    src.buffer = this.sample; src.connect(off.destination); src.start();
    const out = await off.startRendering();
    const L = out.getChannelData(0), R = out.getChannelData(this.sample.numberOfChannels > 1 ? 1 : 0);
    const data = new Float32Array(frames * 2);
    for (let k = 0; k < frames; k++) { data[2 * k] = L[k]; data[2 * k + 1] = R[k]; }
    for (let o = 0; o < data.length; o += CHUNK) {
      const n = Math.min(CHUNK, data.length - o), args = [i(bufnum), i(o), i(n)];
      for (let k = 0; k < n; k++) args.push(f(data[o + k]));
      this.scsynth.sendOsc(oscMessage("/b_setn", args));
    }
    this.post_("web", `heartbeat: ${frames} frames at ${rate} Hz into buffer ${bufnum}`);
  }
  retire() {
    this.attempt++;
    this.crash = null;
    try { this.sclang.runCode("AppClock.clear; SystemClock.clear; TempoClock.default.clear;"); } catch (_) {}
    this.scsynth = this.sclang = null;
    for (const n of toDestination) { try { n.disconnect(); } catch (_) {} try { n.context.close(); } catch (_) {} }
    toDestination.length = 0;
    this.node = this.ctx = null;
  }
  replay() {                                     // SuperCollider (re)started: give it the page's state
    this.send("/whale/setmode", [s(this.mode)]);
    if (this.transport === "stop") this.send("/whale/stop", []);
  }

  // ------------------------------------------------------------------ bridge.py's routes
  post(path, d = {}) {
    if (path === "/api/play" || path === "/api/pause" || path === "/api/stop") this.transport = path.slice(5);
    if (path === "/api/setmode") this.mode = d.mode === "quad" ? "quad" : "stereo";
    if (this.state !== "ready") return;          // visual only until SuperCollider sounds
    switch (path) {
      case "/api/play": return this.send("/whale/play", []);
      case "/api/pause": return this.send("/whale/pause", []);
      case "/api/stop": return this.send("/whale/stop", []);
      case "/api/setmode": return this.send("/whale/setmode", [s(this.mode)]);
      case "/api/gate":
        return this.send("/whale/gate", [
          f(d.amplitude ?? 0.5), f(d.rate ?? 1.0), s(d.type ?? "surface"),
          f(d.depth ?? 0), f(d.bpm ?? 20), f(d.spatX ?? 0), f(d.spatY ?? 0),
        ]);
      default: return;
    }
  }
  send(address, args) { this.sclang.sendOsc(oscMessage(address, args)); }

  // ------------------------------------------------------------------ debugging
  levels() {                                     // instantaneous peak / rms (dBFS) of what scsynth outputs
    if (!this.ctx || !this.node) return null;
    if (!this._an) { this._an = this.ctx.createAnalyser(); this._an.fftSize = 4096; nativeConnect.call(this.node, this._an); }
    const buf = new Float32Array(this._an.fftSize);
    this._an.getFloatTimeDomainData(buf);
    let peak = 0, sum = 0;
    for (const v of buf) { const a = Math.abs(v); if (a > peak) peak = a; sum += v * v; }
    return { peak: +peak.toFixed(4), rms_dBFS: +(10 * Math.log10(sum / buf.length || 1e-12)).toFixed(1) };
  }
}

export const whaleEngine = new WhaleEngine();
