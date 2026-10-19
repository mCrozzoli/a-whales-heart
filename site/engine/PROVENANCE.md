# SuperCollider WebAssembly build — provenance

- Source: GitHub Actions artifact `SuperCollider-5d47207bb313684e81ebe729a5f714f50761c6c7-wasm.zip`
  from `supercollider/supercollider`, workflow CI (job "Build wasm"), branch `develop`,
  run 36107729172, commit `5d47207bb313684e81ebe729a5f714f50761c6c7`, built 2026-09-25.
- Downloaded 2026-09-26 with `gh run download` (approved by Miguel) for the dark_ocean probe
  (`lab/web/PLAN.md` §11).
- Unreleased: no tagged SuperCollider release contains this build (latest 3.14.1, 2025-11-24).
- Licence (from the bundled README_WASM.md): scsynth and sclang GPL-3.0; the WASM bindings
  AGPL-3.0. `LICENSE` in each folder is the GPL-3.0 text.
- Contents: `sclang/` (sclang only), `scsynth/` (scsynth only), `editor/` (both, wired together
  by a browser IDE mock-up). Unmodified.
