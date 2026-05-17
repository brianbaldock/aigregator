# AIgregator Nostalgia (BBS) Theme — Implementation Plan

> **For Hermes:** Use subagent-driven-development to execute this task-by-task once approved.

**Goal:** Replace the current "Nostalgia" (formerly terminal) theme entry with a full interactive BBS experience at `/bbs/`. The bedroom + monitor video is the permanent backdrop. Articles render *inside* the CRT monitor as a BBS, with menus, message boards, an article reader, search, ANSI splashes, a fake login, MOTD, visitor counter, and door games (adventure, tic-tac-toe, WarGames, Matrix). Text is anchored to the monitor via precomputed motion tracking so it never slides off as the video drifts.

**Architecture:**
- Standalone SPA at `docs/bbs/index.html`, no framework. Vanilla JS + a tiny router. Pulls article data from a JSON manifest produced by `scripts/build.py`.
- Existing site layout, themes, and `/scene/` stay untouched. The current themes dropdown gets its "terminal/nostalgia" entry rewired so selecting "Nostalgia" shows a "▸ Start nostalgia mode" CTA that links to `/bbs/`. Other themes work exactly as before.
- The `/bbs/` experience is built on the perspective-warped CRT we already proved in `/scene/`, plus precomputed per-frame motion offsets, plus a state machine for the BBS UI.

**Tech Stack:**
- HTML/CSS/Vanilla JS (no build step for the BBS app itself)
- Python (existing `scripts/build.py`) extended to emit `docs/bbs/manifest.json`
- OpenCV + Python on the DGX Spark for the one-time motion track
- Web Audio API for ANSI key tones, modem, etc. (existing audio files)

---

## Phase 0 — Source-of-truth and conventions

### Task 0.1: Lock the BBS color palette

**Objective:** Set the green-on-black phosphor color tokens we agreed on, in one place so every screen uses them.

**Files:**
- Modify: `docs/bbs/styles/crt.css` (created in Task 1.x — defer until then; this task just documents the tokens)

**Tokens:**
```
--bbs-bg:        #000000;
--bbs-fg:        rgba(140, 220, 150, 0.62);   /* faded phosphor */
--bbs-fg-bright: rgba(170, 240, 175, 0.85);   /* highlighted/active */
--bbs-fg-dim:    rgba(140, 220, 150, 0.35);   /* unselected / disabled */
--bbs-accent:    rgba(255, 220, 120, 0.75);   /* amber for warnings/errors */
--bbs-glow:      rgba(140, 220, 150, 0.35);
```

No code yet — just lock the palette so reviews can flag drift.

---

## Phase 1 — Motion tracking (Spark side)

**Goal:** Produce `docs/bbs/monitor-track.json` containing per-frame `{tx, ty, rot, scale}` offsets for `bedroom-ambient.mp4` so the CRT overlay sticks to the monitor exactly.

### Task 1.1: Pick 4 monitor corners on the ambient video, frame 0

**Objective:** Use the existing `/scene/?pick` to record the monitor corners on the *first frame* of the ambient loop. We already have these from earlier, but re-confirm against `bedroom-ambient.mp4` (not the intro) since corner picker ran on the ambient.

**Files:**
- Output: `docs/bbs/data/monitor-corners.json` (created)

**Step 1:** Reuse the picker output already captured:
```json
{
  "tl": [3.39, 17.80],
  "tr": [95.72, 19.76],
  "br": [90.71, 73.35],
  "bl": [2.61, 72.37]
}
```

**Step 2:** Save to `docs/bbs/data/monitor-corners.json`. Commit.

### Task 1.2: Write the OpenCV tracker script

**Objective:** Python script that runs on the Spark, takes the video + frame-0 corners, tracks them every frame using KLT/Lucas-Kanade optical flow, and emits a per-frame transform JSON.

**Files:**
- Create: `scripts/track_monitor.py`
- Output: `docs/bbs/monitor-track.json`

**Approach:**
1. Load `docs/scene/video/bedroom-ambient.mp4` with OpenCV
2. Take 4 corners from `monitor-corners.json` (convert from % to pixels using video w/h)
3. For each frame, use `cv2.calcOpticalFlowPyrLK` to track the 4 points
4. For each frame, fit the affine transform from `frame-0 corners` to `current corners` (cv2.estimateAffinePartial2D or homography for full perspective)
5. Emit JSON: `{ fps: 16, frames: [ {t: 0.0, m: [a,b,c,d,e,f]}, ... ] }` where `m` is the 6-value affine matrix (CSS-compatible) **relative to frame 0**

**Step 1:** Write `scripts/track_monitor.py` with the structure above. Include CLI args: `--video`, `--corners`, `--out`, `--mode {affine|homography}`. Default mode `affine` (8-DOF homography overshoots on subtle motion).

**Step 2:** Run on Spark — `python scripts/track_monitor.py --video docs/scene/video/bedroom-ambient.mp4 --corners docs/bbs/data/monitor-corners.json --out docs/bbs/monitor-track.json`

**Step 3:** Verify output: JSON should have `frames.length === 130` (8s × 16fps × 2 from ping-pong = 128 frames, plus padding), each `m` an array of 6 numbers near `[1, 0, 0, 1, 0, 0]` ± small deltas.

**Step 4:** Commit script + JSON.

### Task 1.3: Wire track into `/scene/` as a Phase-1 dogfood test

**Objective:** Before doing any BBS work, prove the motion track works in the existing `/scene/` page. If it doesn't track, no point building the BBS on it.

**Files:**
- Modify: `docs/scene/index.html` (the `applyWarp()` function and the `requestAnimationFrame` loop)

**Step 1:** On load, fetch `/bbs/monitor-track.json`.

**Step 2:** Add a `requestAnimationFrame` loop that runs whenever the ambient video is playing. Each frame: read `ambient.currentTime`, look up nearest frame in the track, compose the static "base warp matrix" (4-corner matrix3d) with the per-frame affine delta. Apply combined matrix to `#screen-quad`.

**Step 3:** Verify visually — the text should now stick to the monitor as the ambient video drifts. No shake, no slide.

**Step 4:** Commit. Tag commit `motion-track-shipped`.

### Task 1.4: Strengthen `( )` curvature

**Objective:** The text should bow outward on both left AND right edges to match the convex CRT, not just one side. Per user feedback.

**Files:**
- Modify: `docs/scene/index.html` (the `<filter id="crt-curve">` SVG block)
- Mirror change in: `docs/bbs/styles/crt.css` (later, once it exists)

**Step 1:** Change the displacement map gradient from horizontal-offset radial to a **horizontally stretched ellipse** centered at 50%:
```
<radialGradient id='g' cx='50%' cy='50%' fx='50%' fy='50%' r='80%' gradientTransform='matrix(0.7 0 0 1 0.15 0)'>
  <stop offset='0%'  stop-color='rgb(128,128,0)'/>
  <stop offset='40%' stop-color='rgb(128,128,0)'/>
  <stop offset='100%' stop-color='rgb(180,160,0)'/>
</radialGradient>
```
The `gradientTransform` squishes the gradient horizontally so the gradient-edge runs along the left and right walls of the screen.

**Step 2:** Bump `feDisplacementMap scale` from 18 → 22.

**Step 3:** Visual check — left AND right edges of text bow outward equally; top/bottom stay close to flat.

**Step 4:** Commit.

### Task 1.5: Increase interlacing + scanline density

**Objective:** Per user — more interlacing, more refresh lines.

**Files:**
- Modify: `docs/scene/index.html` (the `#crt-text` `text-shadow` block and add a `#scanlines` overlay back)

**Step 1:** Add a transparent scanline overlay back, scoped to the warped quad:
```css
#screen-quad::after {
  content: ""; position: absolute; inset: 0;
  background: repeating-linear-gradient(
    to bottom,
    rgba(0,0,0,0)    0px,
    rgba(0,0,0,0)    1px,
    rgba(0,0,0,0.20) 2px,
    rgba(0,0,0,0)    3px
  );
  mix-blend-mode: multiply;
  pointer-events: none;
}
```
Scanline period is 3px (was 4px previously). Darker (0.20 vs 0.15) so it reads on the transparent background.

**Step 2:** Strengthen interlace ghost in text-shadow — add a `0 0.5px 0 rgba(...)` micro-shadow and bump the existing `0 1px 0` to `rgba(...0.28)`.

**Step 3:** Commit.

---

## Phase 2 — Manifest + routing scaffolding

### Task 2.1: Build JSON manifest from existing digests

**Objective:** Extend `scripts/build.py` to emit `docs/bbs/manifest.json` with one entry per digest article.

**Files:**
- Modify: `scripts/build.py`
- Output: `docs/bbs/manifest.json`

**Shape:**
```json
{
  "generated_at": "2026-05-17T...",
  "boards": [
    { "id": "news",    "name": "AI NEWS",        "description": "Daily digest, freshest first" },
    { "id": "archive", "name": "ARCHIVES",       "description": "All past issues" },
    { "id": "about",   "name": "ABOUT THIS BBS", "description": "Sysop and history" }
  ],
  "articles": [
    {
      "id": "2026-05-16-daily-ai-news",
      "board": "news",
      "title": "...",
      "date": "2026-05-16",
      "summary": "...",
      "body_text": "...",      // plaintext, BBS-safe (no HTML)
      "tags": ["..."],
      "url": "/digests/2026-05-16/"
    }
  ]
}
```

**Step 1:** In build.py, after digest HTML generation, also iterate the digest list and produce the manifest. Strip HTML → plaintext for `body_text` (use existing markdown source if available; fallback to BeautifulSoup `get_text()`).

**Step 2:** Run build, verify `docs/bbs/manifest.json` exists and is well-formed.

**Step 3:** Commit.

### Task 2.2: Scaffold `/bbs/` SPA

**Objective:** Create the BBS app shell: HTML with the video stage + warped CRT quad + a `<div id="bbs-root">` mount point. No content yet, just routing.

**Files:**
- Create: `docs/bbs/index.html`
- Create: `docs/bbs/styles/crt.css` (copies the warp + curvature + scanline stack from `/scene/`)
- Create: `docs/bbs/styles/bbs.css` (BBS layout — header, menu, prompt)
- Create: `docs/bbs/app/main.js` (entry point + router)
- Create: `docs/bbs/app/router.js`

**Step 1:** `index.html` mirrors `/scene/` for the video + start gate + screen-quad, but `#crt-text` is replaced with `<div id="bbs-root"></div>`.

**Step 2:** `router.js` — hash-based router (`#/`, `#/board/news`, `#/article/<id>`, `#/door/wargames`, etc.). On hash change, re-render `#bbs-root`.

**Step 3:** `main.js` — on load: fetch `monitor-track.json`, fetch `manifest.json`, start video pipeline, start router with default route `#/login` (if no `bbs.user` in localStorage) or `#/menu`.

**Step 4:** Add empty placeholder renderers for each route. Verify routing works (back/forward, deep links).

**Step 5:** Commit.

### Task 2.3: Rewire the existing Nostalgia theme entry

**Objective:** Replace the current terminal-themed view with: pick "Nostalgia" → main page becomes a minimal landing with a `▸ Start nostalgia mode` button that links to `/bbs/`. Don't break the other themes or layout.

**Files:**
- Modify: `templates/app.js` (THEMES array + the part that toggles theme classes)
- Modify: `templates/themes.css` (rename `terminal` styles → `nostalgia-landing`; add minimal landing UI)

**Step 1:** Theme key stays `nostalgia` (was already renamed earlier). When `data-theme="nostalgia"` is applied to the body:
- Hide the normal digest grid
- Show a centered hero with the `aigregator-logo-nostalgia.png` (existing) and a single button: `▸ START NOSTALGIA MODE`
- Button is an `<a href="/bbs/">` styled like a phosphor terminal command

**Step 2:** Other themes (phosphor default, dark, light, geocities, tron, matrix, canadian) keep current behavior.

**Step 3:** Verify: cycle through every theme via the dropdown; only nostalgia shows the landing, others unchanged.

**Step 4:** Commit.

---

## Phase 3 — BBS core UX

### Task 3.1: Login prompt

**Objective:** First visit shows `ENTER HANDLE:`. After typed and submitted, persist `{handle, firstVisit, lastVisit}` to `localStorage.bbs.user`. Subsequent visits skip to MOTD.

**Files:**
- Create: `docs/bbs/app/screens/login.js`

**Step 1:** Renderer prints:
```
*** AIGREGATOR BBS - NODE 1 ***
SECURE 56K CONNECTION ESTABLISHED

NEW CALLER DETECTED.
PLEASE ENTER YOUR HANDLE:

> _
```

**Step 2:** Input is captured by keyboard handler (no `<input>` — render typed text into the BBS surface for authenticity). Enter submits.

**Step 3:** Save, route to `#/motd`.

**Step 4:** Commit.

### Task 3.2: MOTD + main menu

**Objective:** Welcome screen with sysop message of the day, visitor counter (read+increment localStorage), then a numbered menu of boards + doors + commands.

**Files:**
- Create: `docs/bbs/app/screens/motd.js`
- Create: `docs/bbs/app/screens/menu.js`
- Create: `docs/bbs/data/motd.txt` (sysop message, edit by hand)

**Step 1:** MOTD screen — print ANSI banner (Task 3.6) + welcome line "WELCOME BACK, {handle}. LAST CALL: {lastVisit}. VISITORS: {n}."

**Step 2:** Menu — numbered, BBS-classic, with key shortcuts:
```
[1] AI NEWS BOARD
[2] ARCHIVES
[3] ABOUT THIS BBS
[4] DOOR GAMES
[5] SEARCH
[Q] LOGOFF
```
Number keys + letters route to next screen.

**Step 3:** Commit.

### Task 3.3: Message board listing

**Objective:** Show article list for a board. Paginated 10/screen. Arrow keys navigate, Enter reads.

**Files:**
- Create: `docs/bbs/app/screens/board.js`

**Step 1:** Render header `BOARD: AI NEWS - PAGE 1/N`. Then numbered list `[01] 2026-05-16  Title goes here...`.

**Step 2:** Up/down move highlight; Enter routes to `#/article/<id>`; B = back; PgUp/PgDn paginate.

**Step 3:** Commit.

### Task 3.4: Article reader

**Objective:** Display one article inside the CRT with word wrap (~64 cols), scroll via arrow keys, N/P jump to next/prev article, B back to board.

**Files:**
- Create: `docs/bbs/app/screens/article.js`
- Create: `docs/bbs/app/util/wrap.js` (word-wrap utility)

**Step 1:** Article header `# title` line + date + tags. Body wrapped to 64 cols, rendered as `<pre>`.

**Step 2:** Scroll handling — arrow keys move viewport one line; PgUp/PgDn move a screen; Home/End jump to top/bottom.

**Step 3:** Footer status line `[B]ack [N]ext [P]rev [R]eply (disabled) [Q]uit to menu`.

**Step 4:** Commit.

### Task 3.5: Search

**Objective:** `/search <terms>` from anywhere, or menu option 5. Live-filter `manifest.json` by title + body_text.

**Files:**
- Create: `docs/bbs/app/screens/search.js`
- Create: `docs/bbs/app/util/search.js` (simple lowercase substring matcher; upgrade to fuzzy later if needed)

**Step 1:** Prompt screen `SEARCH: > _`. Enter runs, results list like a board listing.

**Step 2:** Highlight matched terms in results.

**Step 3:** Commit.

### Task 3.6: ANSI splash screens

**Objective:** Authentic BBS-style ANSI art banners between major sections (login → MOTD → menu). Use real-style block-character art rendered in monospace.

**Files:**
- Create: `docs/bbs/data/ansi/welcome.txt`
- Create: `docs/bbs/data/ansi/door.txt`
- Create: `docs/bbs/data/ansi/disconnect.txt`

**Step 1:** Hand-author 3-5 ASCII/ANSI banners using block characters (`█ ▓ ▒ ░`). Render with color tokens.

**Step 2:** Splash function: prints the banner, waits 1200ms or any key, then proceeds.

**Step 3:** Commit.

---

## Phase 4 — Door games

### Task 4.1: Door menu

**Files:** `docs/bbs/app/screens/doors.js`

```
DOOR GAMES:
[1] WARGAMES         "Shall we play a game?"
[2] THE ORACLE        Choose the red pill or the blue pill.
[3] TIC TAC TOE
[4] TEXT ADVENTURE: "AIGREGATOR QUEST"
[B] BACK
```

### Task 4.2: WarGames

**Objective:** WOPR style. Lists "GAMES AVAILABLE" (Falken's Maze, Black Jack, Gin Rummy, Hearts, Bridge, Checkers, Chess, Poker, Fighter Combat, Guerrilla Engagement, Desert Warfare, Air-To-Ground Actions, Theaterwide Tactical Warfare, Theaterwide Biotoxic and Chemical Warfare, **GLOBAL THERMONUCLEAR WAR**). User picks. If anything but GTW, says "WOULDN'T YOU PREFER A NICE GAME OF CHESS?". If GTW, runs the Tic-Tac-Toe simulation (W.O.P.R. plays itself, scrolling moves) and ends with "A STRANGE GAME. THE ONLY WINNING MOVE IS NOT TO PLAY."

**Files:** `docs/bbs/app/screens/door-wargames.js`

### Task 4.3: The Oracle (Matrix references)

**Objective:** Oracle's kitchen vibe. Text adventure asking philosophical questions. Red pill / blue pill branch. References woven in (rabbit hole, "there is no spoon," "Mr. Anderson..."). Pure flavor, ~2-3 minutes of play.

**Files:** `docs/bbs/app/screens/door-oracle.js`

### Task 4.4: Tic-Tac-Toe

**Objective:** Playable. User vs CPU. CPU uses minimax (it's a tiny state space, perfect play is ~50 lines). Same render style as everything else.

**Files:** `docs/bbs/app/screens/door-ttt.js`

### Task 4.5: AIgregator Quest — text adventure

**Objective:** Tiny Zork-style adventure where you explore "the AIgregator data center." Rooms, items, simple verb parser (`look`, `go north`, `take`, `read`, `use`). End goal: retrieve the daily digest from the mainframe. ~10 rooms, ~6 items, ~30 min of content.

**Files:**
- Create: `docs/bbs/app/screens/door-adventure.js`
- Create: `docs/bbs/data/adventure/world.json` (rooms, exits, items, descriptions)

---

## Phase 5 — Polish, ship

### Task 5.1: Sound design pass

**Objective:** Add keyboard click on every typed BBS character. Modem reconnect tone when navigating between major screens (subtle). Disconnect tone on Q logoff.

**Files:** modify each screen renderer; reuse `docs/scene/audio/` files.

### Task 5.2: Visitor counter, last caller, sysop message

**Files:**
- Server-side (optional): a single hand-bumped counter in `docs/bbs/data/stats.json` or just persist per-browser in localStorage with a randomized starting offset so it feels plausible.

### Task 5.3: First-run intro flow

**Objective:** First time a user hits `/bbs/`, play the full walk-in intro (current `/scene/`). Subsequent visits skip straight to ambient + boot/login. Persist `bbs.intro_played`.

### Task 5.4: Cross-browser + mobile QC

**Objective:** Verify on Safari iOS, Chrome Android, Firefox desktop. Touch input for the BBS (tap-anywhere keyboard? on-screen mini-keyboard? D-pad?). This is its own design conversation.

### Task 5.5: Update skill `projects:aigregator`

**Objective:** Document the BBS architecture, manifest format, motion-track regeneration, and door-game framework so future sessions don't re-derive them.

---

## Phase ordering

```
Phase 0  →  Phase 1 (must land + verify)  →  Phase 2  →  Phase 3  →  Phase 4  →  Phase 5
```

Phase 1 is the gating risk. If the motion track doesn't produce convincing tracking, the whole "text glued to monitor" premise breaks and we need to fall back to faking it. So we ship and dogfood Phase 1 inside `/scene/` first, then build everything else on top of it once it's proven.

## Estimated effort (rough)

| Phase | Tasks | Effort |
|---|---|---|
| 0 | Lock palette | 5 min |
| 1 | Motion track + CRT polish | 2-3 hr |
| 2 | Manifest + routing + theme rewire | 2 hr |
| 3 | BBS core UX | 4-5 hr |
| 4 | Door games | 3-4 hr |
| 5 | Polish, mobile, ship | 2-3 hr |
| **Total** | | **~14-17 hr** |

This is realistically 2-4 sessions. Phase 1+2 could ship tonight if you want momentum; door games are their own evening.
