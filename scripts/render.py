#!/usr/bin/env python3
"""
A Whale's Heart — offline render script.

Produces a 5-minute video (5 x 60s cues) of the sonification
at 1x speed, rendered entirely offline with no SuperCollider,
no bridge, no screen capture, no BlackHole.

Output: rendered/final.mp4  (plus per-cue intermediates)

Cues:
  1. t = 0             (start)
  2. t = 2/5 of data
  3. t = 3/5 of data
  4. t = 4/5 of data
  5. t = end - 60s     (last minute)

Pipeline:
  1. Parse DEPTH_RAW + GPS inline from html/prototype.html
  2. Re-implement the HTML's mapping formulas in Python
     (mapBpm / mapAmp / mapRate / spatial pan)
  3. For each cue, simulate 60s of the phase-accumulator beat
     clock and collect beat events (t, amp, rate, pan)
  4. Mix heart-sample instances into a 60s stereo buffer
     (equal-power Pan2 matching SC's formula)
  5. Drive prototype.html via headless Chromium (Playwright)
     and record 60s of the viewport per cue
  6. ffmpeg: mux audio+video per cue -> concat -> final.mp4

Baked CONFIG = current HTML defaults (Default preset).
Ocean bed is deliberately skipped — heartbeats stand alone.

Deps:
    pip install playwright numpy scipy soundfile
    playwright install chromium
    brew install ffmpeg
"""

import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path


def _clean_env():
    """Strip DYLD_* vars that confuse Homebrew tools when MacPorts
    is also installed (classic /opt/local vs /opt/homebrew collision).
    Without this, Homebrew's ffmpeg loads MacPorts' libiconv and aborts."""
    return {k: v for k, v in os.environ.items() if not k.startswith("DYLD_")}

import numpy as np
import soundfile as sf
from scipy.signal import resample
from playwright.sync_api import sync_playwright


# ─── Paths ──────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
HTML = ROOT / "html" / "prototype.html"
WAV  = ROOT / "whale_heart_wav" / "whale_one_heart.wav"
OUT  = ROOT / "rendered"

# ─── Render parameters ──────────────────────────────────────────
CUE_DURATION_SEC = 60
SAMPLE_RATE      = 44_100
VIDEO_W, VIDEO_H = 1440, 900   # Playwright viewport; multiple of 16

# Baked CONFIG — must match html/prototype.html Default preset
CONFIG = {
    "bpm":  {"curve": "interval", "surface": 30.0, "depth": 2.0,
             "lungeMult": 2.5,    "lungeCap": 75.0},
    "amp":  {"direction": "surface", "exponent": 1.5,
             "min": 0.05, "max": 1.0, "lungeBoost": 0.0},
    "rate": {"enabled": True, "surface": 1.0, "depth": 0.25, "floor": 0.22},
}
MAXD = 132.8


# ─── Data parsing ───────────────────────────────────────────────
def parse_html_data():
    """Extract DEPTH_RAW and GPS arrays from the inline JS literals."""
    txt = HTML.read_text(encoding="utf-8")

    m = re.search(r"const\s+DEPTH_RAW\s*=\s*(\[[^\n]*?\]);", txt)
    if not m:
        raise RuntimeError("DEPTH_RAW literal not found in HTML")
    depth_raw = json.loads(m.group(1))

    m = re.search(r"const\s+GPS\s*=\s*(\[[^\n]*?\]);", txt)
    if not m:
        raise RuntimeError("GPS literal not found in HTML")
    gps = json.loads(m.group(1))

    return depth_raw, gps


# ─── Mapping formulas (mirror of html/prototype.html) ───────────
def map_bpm(depth, lunge):
    s = CONFIG["bpm"]["surface"]
    d = CONFIG["bpm"]["depth"]
    t = max(0.0, min(1.0, depth / MAXD))
    if CONFIG["bpm"]["curve"] == "interval":
        iS, iD = 60.0 / s, 60.0 / d
        interval = iS + (iD - iS) * t
        bpm = 60.0 / interval
    else:
        bpm = s + (d - s) * t
    if lunge:
        bpm = min(CONFIG["bpm"]["lungeCap"], bpm * CONFIG["bpm"]["lungeMult"])
    return bpm


def map_amp(depth, lunge):
    t = max(0.0, min(1.0, depth / MAXD))
    loud = (1 - t) if CONFIG["amp"]["direction"] == "surface" else t
    shaped = loud ** CONFIG["amp"]["exponent"]
    amp = CONFIG["amp"]["min"] + (CONFIG["amp"]["max"] - CONFIG["amp"]["min"]) * shaped
    if lunge:
        amp = min(1.0, amp + CONFIG["amp"]["lungeBoost"])
    return amp


def map_rate(depth):
    if not CONFIG["rate"]["enabled"]:
        return 1.0
    t = max(0.0, min(1.0, depth / MAXD))
    r = CONFIG["rate"]["surface"] + (CONFIG["rate"]["depth"] - CONFIG["rate"]["surface"]) * np.sqrt(t)
    return max(CONFIG["rate"]["floor"], r)


def gps_bounds(gps):
    lats = [p["latitude"]  for p in gps]
    lons = [p["longitude"] for p in gps]
    return min(lats), max(lats), min(lons), max(lons)


# ─── Beat simulator ─────────────────────────────────────────────
def simulate_beats(cue_start_frame, depth_raw, gps, duration_sec):
    """Replay the HTML phase accumulator in Python at 1x speed.
    Returns list of (t_sec, amp, rate, pan_x)."""
    events = []
    total = len(depth_raw)
    float_frame = float(cue_start_frame)
    phase = 0.0

    la0, la1, lo0, lo1 = gps_bounds(gps)
    dlon = (lo1 - lo0) or 1.0

    dt_ms = 1.0
    n_steps = int(duration_sec * 1000 / dt_ms)

    for step in range(n_steps):
        float_frame += dt_ms / 10_000.0  # speed=1
        if float_frame >= total - 1:
            break
        fi = min(int(float_frame), total - 1)
        fr = depth_raw[fi]
        depth = fr["depth"]
        lunge = fr["lunge"]

        bpm = map_bpm(depth, lunge)
        interval_ms = 60_000.0 / bpm
        phase += dt_ms / interval_ms

        if phase >= 1:
            phase -= 1
            if phase >= 1:
                phase = 0
            amp  = map_amp(depth, lunge)
            rate = map_rate(depth)

            gi = max(0, min(len(gps) - 1,
                            int((float_frame / total) * len(gps))))
            p = gps[gi]
            pan_x = ((p["longitude"] - lo0) / dlon) * 2 - 1

            t_sec = (step * dt_ms) / 1000.0
            events.append((t_sec, amp, rate, pan_x))

    return events


# ─── Audio synthesis ────────────────────────────────────────────
def load_sample(path, target_sr):
    data, sr = sf.read(str(path), dtype="float32")
    if data.ndim == 2:
        mono = data.mean(axis=1)
    else:
        mono = data
    if sr != target_sr:
        mono = resample(mono, int(len(mono) * target_sr / sr))
    return mono.astype(np.float32)


def synth_audio(events, sample_mono, duration_sec, sr):
    """Mix one sample instance per event with resample+amp+equal-power pan."""
    n = int(duration_sec * sr)
    out = np.zeros((n, 2), dtype=np.float32)

    # Simple resample cache — keyed by rate rounded to 3 decimals
    cache = {}

    def resampled(rate):
        key = round(rate, 3)
        if key not in cache:
            new_len = max(1, int(len(sample_mono) / rate))
            cache[key] = resample(sample_mono, new_len).astype(np.float32)
        return cache[key]

    for t_sec, amp, rate, pan in events:
        beat = resampled(rate) * amp
        pan_c = max(-1.0, min(1.0, pan))
        l_gain = float(np.sqrt((1 - pan_c) / 2))  # SC Pan2 equal-power
        r_gain = float(np.sqrt((1 + pan_c) / 2))

        start = int(t_sec * sr)
        end   = start + len(beat)
        if start >= n:
            continue
        if end > n:
            beat = beat[: n - start]
            end = n
        out[start:end, 0] += beat * l_gain
        out[start:end, 1] += beat * r_gain

    # Gentle peak normalization
    peak = float(np.abs(out).max())
    if peak > 0.99:
        out *= 0.99 / peak
    return out


# ─── Video render (headless Chromium) ───────────────────────────
def render_video(cue_start_frame, duration_sec, out_dir):
    """Open prototype.html in headless Chromium, seek to cue, play, record."""
    out_dir = Path(out_dir)
    out_dir.mkdir(exist_ok=True)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        ctx = browser.new_context(
            viewport={"width": VIDEO_W, "height": VIDEO_H},
            record_video_dir=str(out_dir),
            record_video_size={"width": VIDEO_W, "height": VIDEO_H},
        )
        page = ctx.new_page()
        # Block every bridge call so the HTML stays in visual-only mode
        page.route("**/api/**", lambda route: route.abort())

        page.goto(f"file://{HTML.resolve()}")
        # Wait for JS to finish loading (floatFrame defined)
        page.wait_for_function("typeof floatFrame !== 'undefined'", timeout=10_000)
        # Bridge polling will fail; Play button should enable ~300ms later
        page.wait_for_selector("#btn-play:not([disabled])", timeout=10_000)
        # Seek to cue
        page.evaluate(f"floatFrame = {cue_start_frame}; drawDepth(); drawMap();")
        # Go
        page.click("#btn-play")
        page.wait_for_timeout(int(duration_sec * 1000))
        page.click("#btn-play")

        video = page.video
        ctx.close()      # this flushes + finalizes the .webm
        browser.close()
        # Belt-and-suspenders: make sure the .webm is fully written before
        # ffmpeg opens it. close() should block until done, but wait anyway.
        import time
        path = Path(video.path())
        for _ in range(20):
            if path.exists() and path.stat().st_size > 0:
                break
            time.sleep(0.1)
        return path


# ─── ffmpeg wrappers ────────────────────────────────────────────
def mux(video_path, audio_path, out_path):
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-i", str(video_path),
            "-i", str(audio_path),
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            str(out_path),
        ],
        check=True,
        env=_clean_env(),
    )


def concat(mp4_list, out_path):
    list_file = OUT / "_concat.txt"
    list_file.write_text("\n".join(f"file '{p.name}'" for p in mp4_list))
    subprocess.run(
        [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "concat", "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(out_path),
        ],
        check=True,
        env=_clean_env(),
    )
    list_file.unlink(missing_ok=True)


# ─── Orchestrator ───────────────────────────────────────────────
def main():
    if not HTML.exists():
        sys.exit(f"Missing: {HTML}")
    if not WAV.exists():
        sys.exit(f"Missing: {WAV}")
    if not shutil.which("ffmpeg"):
        sys.exit("ffmpeg not on PATH. Install: brew install ffmpeg")

    OUT.mkdir(exist_ok=True)

    print("┌ A Whale's Heart — offline render")
    print("│")
    print("│ Parsing data from HTML...")
    depth_raw, gps = parse_html_data()
    total = len(depth_raw)
    print(f"│   {total} depth frames  ·  {len(gps)} GPS points")
    print(f"│   {total*10}s data-time  ·  {total*10/3600:.2f}h")

    print("│ Loading heartbeat sample...")
    sample_mono = load_sample(WAV, SAMPLE_RATE)
    print(f"│   {len(sample_mono)/SAMPLE_RATE:.3f}s mono @ {SAMPLE_RATE} Hz")

    # Cue starts — 5 positions per spec
    frames_per_cue = int(CUE_DURATION_SEC / 10)  # 6 frames at 1x
    cues = [
        0,
        int(total * 2 / 5),
        int(total * 3 / 5),
        int(total * 4 / 5),
        max(0, total - frames_per_cue - 2),
    ]

    segment_mp4s = []
    for i, start in enumerate(cues, start=1):
        label = f"cue_{i}"
        mp4_path = OUT / f"{label}.mp4"
        print(f"│")
        print(f"├─ {label}  (frame {start}  ·  t={start*10}s data-time)")

        # Resumable: skip cues whose .mp4 is already complete.
        if mp4_path.exists() and mp4_path.stat().st_size > 1024:
            print(f"│   ✓ already rendered — skipping")
            segment_mp4s.append(mp4_path)
            continue

        audio_path = OUT / f"{label}.wav"
        if audio_path.exists() and audio_path.stat().st_size > 1024:
            print(f"│   audio  ✓ reusing {audio_path.name}")
        else:
            events = simulate_beats(start, depth_raw, gps, CUE_DURATION_SEC)
            print(f"│   simulated {len(events)} beats")
            audio = synth_audio(events, sample_mono, CUE_DURATION_SEC, SAMPLE_RATE)
            sf.write(str(audio_path), audio, SAMPLE_RATE)
            print(f"│   audio  → {audio_path.name}")

        video_path = render_video(start, CUE_DURATION_SEC, OUT)
        print(f"│   video  → {video_path.name}")

        mux(video_path, audio_path, mp4_path)
        print(f"│   muxed  → {mp4_path.name}")
        segment_mp4s.append(mp4_path)

        # Clean the Playwright .webm — keep .wav and .mp4 for inspection
        video_path.unlink(missing_ok=True)

    print("│")
    print("│ Concatenating final video...")
    final = OUT / "final.mp4"
    concat(segment_mp4s, final)
    print(f"│   → {final}")
    print("└ Done.")


if __name__ == "__main__":
    main()
