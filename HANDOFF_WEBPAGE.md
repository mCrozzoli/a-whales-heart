# Handoff: a GitHub Pages landing page for A Whale's Heart

From the "Calum's organ" session, 2026-10-19. This plan uses two existing projects of Miguel's as models.
Read the files listed below, don't copy from memory. Before you build anything, confirm the plan with Miguel.
Teach as you go: explain each step briefly (what Pages is, why the workflow, why relative paths, how tokens
and looks work). That way Miguel learns to repeat it for future projects.

## 1. Model A: Calum Organ (deploy pipeline)

Repo: `/Users/miguel/Documents/02_Music_Art/Calum Pipe Madness/calum-organ`
→ https://github.com/mCrozzoli/calum-organ, live at https://mcrozzoli.github.io/calum-organ/

- `.github/workflows/pages.yml`: on every push to `main` it runs the tests, then publishes ONE folder
  (`app/static`) with `actions/configure-pages@v5` → `upload-pages-artifact@v3` (path: that folder) →
  `deploy-pages@v4`. It needs the permissions `pages: write` and `id-token: write`.
  In the repo, set Settings → Pages → Source = "GitHub Actions".
- `tools/version_assets.py`: before upload it adds `?v=<commit>` to the CSS/JS references, so browsers
  never mix old and new files (Pages caches each file for 10 minutes). It's worth copying.
- `app/static/index.html` `<head>` has the patterns to reuse:
  - a short title and meta description;
  - an inline SVG data-URI favicon;
  - `<meta name="color-scheme" content="dark light">`;
  - a tiny inline script that sets `data-theme` on `<html>` before first paint. The choice comes from
    `?theme=` in the URL, else localStorage, else the system setting, so light mode never flashes dark.
- `app/static/app.css`: all colours are tokens on `:root` (dark is the default), with
  `:root[data-theme="light"]` overriding them. Use no literal colours elsewhere.
- Use relative paths only (no `/…`), because the site lives under `/<repo-name>/`.

## 2. Model B: Dark Sonification web displays (look and feel)

Repo: `/Users/miguel/Desktop/hello_darksonification/projects/web`
→ live at https://mcrozzoli.github.io/darksonification-web/

- `style/README.md` + `style/darkstyle.css` + `style/darkstyle.js` is the "darkstyle" kit, with three
  looks: dark / light / paper. Paper is Miguel's own visual language: warm paper grain, aubergine ink,
  ochre, and Karla + Rubik type, as on crozzoli.com. The kit has ~60 `--ds-*` tokens, a LOOK control
  (key T), and `?theme=paper` links. `style/specimen.html` shows every token.
- Rules to follow:
  - dark is the reference;
  - data colours keep their hue family across looks and are checked against each look's ground;
  - status colours are never data colours;
  - controls live in a side panel.
- `site/hub.html` + `site/designs.json` + `deploy/publish.py` show how the landing hub and its gates work.
  The gates: no symlinks, files under 95 MB, no root-absolute links, and no CLEARANCE-PENDING markers on
  public material.
- `projects/designs/dark_ocean/web_implementation/index.html` is the reference web shell. Its ground
  follows the look, and it runs SuperCollider in the browser via WASM (`engines/sc-wasm-5d47207`).

## 3. Suggested plan for this folder (not a git repo yet)

1. `git init`. Add a `.gitignore` for the large or raw data (IcelandData/, dataOne/, backup/, rendered/,
   budget/, and the budget pdf/xlsx). Keep the budget out of a public repo.
2. Create a `site/` folder for the page:
   - `index.html`, the landing page: what the piece is, the depth→heart-rate/amplitude mapping table from
     README.md, a short audio clip or video, credits, and a link to the live prototype;
   - `prototype.html`, adapted from `html/prototype.html`, with relative paths to `data/depth_data.json`
     and `gps_data.json`;
   - `style.css`, built on darkstyle tokens (copy darkstyle.css/js in). Give it the LOOK control and the
     pre-paint theme script.
3. Add `.github/workflows/pages.yml` modelled on calum-organ's, uploading only `site/`, plus the
   version-stamp step.
4. Sound on the web: either a rendered audio file, or SC-WASM as in dark_ocean. Recommend starting with the
   rendered audio and adding live SC later.
5. Check clearance before going public:
   - the heartbeat sample is from Zapsplat, so check its licence for redistribution;
   - check the licences/citations for the Iceland depth and DataONE GPS data.
   Leave anything uncleared out of the published folder.
6. Create the GitHub repo (e.g. `mCrozzoli/a-whales-heart`). Ask Miguel before creating or pushing it.
   Turn on Pages from Actions.
7. Preview locally (`python3 -m http.server` inside `site/`), check it at phone width and in each look,
   then push.
