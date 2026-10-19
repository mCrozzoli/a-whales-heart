"""Build the web version of the prototype from the desktop files.

    python3 tools/build_web.py

  supercollider/whaleheart.scd  ->  site/sc/whaleheart.scd
  html/prototype.html           ->  site/prototype.html

The desktop files stay the source of truth: edit them, then rebuild. The web
copies differ only by the substitutions below, each with its reason. Every
`old` must occur EXACTLY once, or the build stops and names it (the desktop
file changed shape: update the substitution here, never the generated file).
Modelled on dark_ocean's web_implementation/build/build_web.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = ROOT / "site"

# ── SuperCollider: (why, old, new) ─────────────────────────────────────────
SC = [
    ("no file system in the browser: the page loads the sample (engine.js)",
     '''root    = thisProcess.nowExecutingPath.dirname +/+ "..";
// Prefer the hand-trimmed single systole+diastole, fall back gracefully.
bufPath = root +/+ "whale_heart_wav/whale_one_heart.wav";
if (File.exists(bufPath).not) {
    bufPath = root +/+ "whale_heart_wav/heartbeat_single.aif";
};
if (File.exists(bufPath).not) {
    bufPath = root +/+ "whale_heart_wav/zapsplat_animals_bluewhale_heartbeat_loop_26507.aif";
    "Using original 32s loop. Provide whale_one_heart.wav for clean playback.".postln;
};
"Heartbeat sample: %".format(bufPath.basename).postln;''',
     '''// web: no file system; engine.js decodes whale_one_heart.wav and fills ~hbBuf.'''),

    ("a browser gives two output channels: stereo only",
     "s.options.numOutputBusChannels = 4;",
     "s.options.numOutputBusChannels = 2;  // web: the browser gives two channels"),

    ("no audio device to pick; scsynth's heap is fixed at 16 MiB (dark_ocean PORTING_LOG §2.3)",
     's.options.device = "UMC404HD 192k";',
     "s.options.memSize = 2048;  // web: leaves room in scsynth's 16 MiB heap"),

    ("Buffer.read needs a file system: allocate, and the page fills it with /b_setn",
     '''    ~hbBuf = Buffer.read(s, bufPath, action: { |buf|
        "  Buffer: % sec  % ch".format(buf.duration.round(0.001), buf.numChannels).postln;
    });''',
     '''    // web: engine.js sets ~webSeconds, then fills this buffer from the page.
    ~hbBuf = Buffer.alloc(s, (~webSeconds * s.sampleRate).round.asInteger, 2);'''),

    ("no network: there is no bridge.py to tell",
     '    ~bridge = NetAddr("127.0.0.1", 57121);\n',
     ""),

    ("engine.js polls this instead of waiting for bridge.py's /whale/ready",
     "    ~bridge.sendMsg('/whale/ready');",
     "    ~whaleReady = true;  // web: engine.js polls this"),
]

# ── The page: (why, old, new) ──────────────────────────────────────────────
HTML = [
    ("cross-origin isolated pages load fonts only with CORS",
     '<link href="https://fonts.googleapis.com/css2?',
     '<link crossorigin href="https://fonts.googleapis.com/css2?'),

    ("start SuperCollider in this tab (service worker on hosts without headers, then engine.js)",
     "</head>",
     '''<script type="module">
  // web: SuperCollider's WebAssembly build needs SharedArrayBuffer, so the page must be
  // cross-origin isolated. GitHub Pages cannot send the headers: coi-sw.js adds them,
  // after one automatic reload on the first visit.
  let reloading = false;
  if (!self.crossOriginIsolated && "serviceWorker" in navigator) {
    await navigator.serviceWorker.register("./coi-sw.js");
    if (!sessionStorage.getItem("whaleCoi")) {
      sessionStorage.setItem("whaleCoi", "1");
      await navigator.serviceWorker.ready;
      reloading = true;
      location.reload();
    }
  } else {
    sessionStorage.removeItem("whaleCoi");
  }
  if (!reloading) {
    const { whaleEngine } = await import("./engine.js");
    window.whaleEngine = whaleEngine;
    whaleEngine.preload().catch(() => {});   // download + compile now; sound starts at the first click
  }
</script>
</head>'''),

    ("no bridge: the page can play at once (visual only until SuperCollider is ready)",
     '<button id="btn-play" disabled>',
     '<button id="btn-play">'),

    ("no bridge.py on the web",
     "const BRIDGE = 'http://localhost:8080';",
     "// web: no bridge.py; engine.js plays its part"),
]

# The bridge block is replaced whole: from scPost() through the polling timer.
BRIDGE_START = "async function scPost(path, data={}) {"
BRIDGE_END = "setInterval(pollBridge, 300); pollBridge();"
BRIDGE_WEB = '''// web: SuperCollider runs in this tab. engine.js takes bridge.py's paths
// (/api/play, /api/pause, /api/stop, /api/setmode, /api/gate) and sends the
// same OSC to the same OSCdefs, so the rest of this page is unchanged.
function scPost(path, data={}) {
  if (window.whaleEngine) window.whaleEngine.post(path, data);
}
const SC_STATUS = {
  loading: ['connecting', 'Loading SC'],
  idle:    ['connecting', 'Sound starts on Play'],
  booting: ['connecting', 'Starting SC'],
  ready:   ['ready',      'SC in this tab'],
  error:   ['error',      'Visual only'],
};
window.whaleStatus = (state) => {
  const [cls, txt] = SC_STATUS[state] || ['error', state];
  scDot.className = 'sc-dot ' + cls; scLbl.textContent = txt;
  if (state === 'ready' && !scReady) { scReady = true; bridgeOnline = true; }
};'''


def apply(text: str, subs, name: str) -> str:
    for why, old, new in subs:
        n = text.count(old)
        if n != 1:
            sys.exit(f"BUILD STOPPED: {name}: expected 1 match, found {n}, for: {why}")
        text = text.replace(old, new)
    return text


def build() -> None:
    sc = (ROOT / "supercollider" / "whaleheart.scd").read_text(encoding="utf-8")
    sc = apply(sc, SC, "whaleheart.scd")
    header = "// GENERATED by tools/build_web.py from supercollider/whaleheart.scd. Edit that file, then rebuild.\n"
    (SITE / "sc").mkdir(exist_ok=True)
    (SITE / "sc" / "whaleheart.scd").write_text(header + sc, encoding="utf-8")

    html = (ROOT / "html" / "prototype.html").read_text(encoding="utf-8")
    html = apply(html, HTML, "prototype.html")
    a, b = html.count(BRIDGE_START), html.count(BRIDGE_END)
    if (a, b) != (1, 1):
        sys.exit(f"BUILD STOPPED: prototype.html: bridge block markers found {a} and {b} times")
    i, j = html.index(BRIDGE_START), html.index(BRIDGE_END) + len(BRIDGE_END)
    html = html[:i] + BRIDGE_WEB + html[j:]
    html = html.replace("<!DOCTYPE html>", "<!DOCTYPE html>\n<!-- GENERATED by tools/build_web.py from html/prototype.html. Edit that file, then rebuild. -->", 1)
    (SITE / "prototype.html").write_text(html, encoding="utf-8")

    print(f"site/sc/whaleheart.scd  ({len(SC)} substitutions)")
    print(f"site/prototype.html     ({len(HTML) + 1} substitutions)")


if __name__ == "__main__":
    build()
