# A Whale's Heart — Offline Render

Produces a 5-minute video of the sonification (5 × 60s cues at 1× speed),
rendered entirely offline. No SuperCollider, no bridge, no screen capture,
no BlackHole. Fully deterministic — re-running produces identical output.

## One-time setup

```bash
pip install -r scripts/requirements.txt
playwright install chromium
brew install ffmpeg
```

## Run

From the project root:

```bash
python3 scripts/render.py
```

Output lands in `rendered/`:

```
rendered/
  cue_1.wav   cue_1.mp4     ← t = 0           (start)
  cue_2.wav   cue_2.mp4     ← t = 2/5
  cue_3.wav   cue_3.mp4     ← t = 3/5
  cue_4.wav   cue_4.mp4     ← t = 4/5
  cue_5.wav   cue_5.mp4     ← t = end − 60s
  final.mp4                 ← all five concatenated (5 min)
```

Takes ~6 minutes total wall-clock — five 60-second Playwright recordings
in real time, plus a few seconds each for audio synthesis and ffmpeg.

## What's baked in

- **Speed**: 1× (honest wall-clock)
- **CONFIG**: HTML `Default` preset (BPM mode, 30→2 bpm, amp exp 1.5, pitch 1.0→0.25)
- **Sample**: `whale_heart_wav/whale_one_heart.wav`
- **Ocean bed**: skipped — heartbeats only, clean for demos
- **Pan**: Pacific placeholder GPS driving equal-power stereo (SC `Pan2` formula)
- **Audio**: 44.1 kHz stereo WAV
- **Video**: 1440×900 viewport, H.264 + AAC MP4, 25 fps (Playwright default)

## Changing things

- **Different preset / config** → edit the `CONFIG` dict at the top of
  `scripts/render.py`. Must match the HTML's mapping semantics.
- **Different cue positions** → edit the `cues = [...]` list in `main()`.
- **Longer/shorter cues** → change `CUE_DURATION_SEC`.
- **Higher-res video** → change `VIDEO_W` / `VIDEO_H`.

## Notes

- `scripts/render.py` blocks all requests to `localhost:8080` inside the
  headless browser, so the render works regardless of whether `bridge.py`
  or SC are currently running.
- At 1× speed, each cue advances the depth canvas by only 6 data-frames
  (~0.07 % of the visible window). The visualization is *deliberately
  calm* — intended to feel like watching real whale-time. If you want
  more visible scrolling per cue, raise the speed in the HTML's animLoop
  before recording (but then the heart rhythm becomes speed-coupled
  artifacts, so consider re-exporting at 1× for the audio and a higher
  speed for a separate visual render).
