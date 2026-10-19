# A Whale's Heart — Project Structure

```
a_whales_heart/
│
├── whaleheart.command          ← LAUNCHER (double-click to start)
│
├── html/
│   └── prototype.html          ← Visualization (browser, no server needed)
│
├── supercollider/
│   └── whaleheart.scd          ← Audio engine (run in SuperCollider)
│
├── data/
│   ├── depth_data.json         ← Iceland whale depth time series (10s resolution)
│   ├── gps_data.json           ← Pacific blue whale GPS track (spatialization)
│   └── whale_heart_wav/
│       └── zapsplat_animals_bluewhale_heartbeat_loop_26507.aif
│
├── dataOne/                    ← Raw DataONE dataset files
├── IcelandData/                ← Raw Iceland dataset files
└── sketches/                   ← Design sketches
```

## First Time Setup

Make the launcher executable (run once in Terminal):
```bash
chmod +x ~/Desktop/a_whales_heart/whaleheart.command
```

## Sonification Mappings

| Parameter       | Source           | Range       | Mapping               |
|----------------|------------------|-------------|----------------------|
| Heart rate      | depth            | 0–133m      | 30 → 2 bpm           |
| Amplitude       | depth            | 0–133m      | 0.10 → 1.0           |
| Spatialization  | GPS coordinates  | lat/lon     | → quad pan (future)  |
| Spectral split  | depth            | 0–133m      | → lo/hi routing (future) |

## Speaker Layout (UMC404)

```
        Front
    [0] FL    FR [1]
         ↑ whale ↑
    [2] RL    RR [3]
        Rear
```

## Status

- [x] Depth visualization (Iceland whale data)
- [x] GPS track visualization (Pacific blue whale)
- [x] Heartbeat BPM modelling from depth
- [x] SuperCollider 4-channel audio
- [ ] Iceland GPS data (pending)
- [ ] OSC sync: browser → SuperCollider
- [ ] Lunge event triggers
- [ ] Spectral frequency routing (floor/ceiling transducers)

## Web version

Live at https://mcrozzoli.github.io/a-whales-heart/ (landing page) and `prototype.html` (the display,
with SuperCollider running in the browser). Only `site/` is published, by `.github/workflows/pages.yml`
on every push to `main`.

- Edit the desktop files (`html/prototype.html`, `supercollider/whaleheart.scd`), then rebuild the web
  copies: `python3 tools/build_web.py`. The few web-only changes are listed, with reasons, in that script.
- Check before pushing: `python3 tools/check_site.py site` (refuses CLEARANCE-PENDING markers, symlinks,
  huge files, and links starting with `/`).
- Preview locally: `python3 -m http.server 8150 --directory site`, then http://localhost:8150/.
  The first visit to the prototype reloads once (the service worker in `coi-sw.js`).
- `site/engine/` is SuperCollider's WebAssembly build (develop @ 5d47207, unmodified; see
  `site/engine/PROVENANCE.md`). `site/engine.js` plays the part of `bridge.py`.
