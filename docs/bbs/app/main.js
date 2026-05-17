// /bbs/ entrypoint. Sets up CRT warp + motion track + router, loads
// the article manifest, registers placeholder route renderers. Real
// screen renderers (login, menu, board, article, search, doors) land
// in Phase 3+.

import { route, start, navigate } from "./router.js";

// Gate removed — if BBS doesn't render well on a phone, that's fine.
// The nostalgia theme is also hidden from the picker on mobile UAs.

// First visit per *load* shows the walk-in — bounce to /scene/ every time.
// `from=scene` tells us we already came back, so don't loop.
// Bypass with ?skip-intro=1 for dev.
if (!location.search.includes("skip-intro") &&
    !location.search.includes("from=scene")) {
  location.replace("/scene/?then=bbs");
  throw new Error("redirecting to /scene/ for walk-in");
}

// ====================================================================
// Refs
// ====================================================================
const wrap    = document.querySelector(".video-wrap");
const ambient = document.getElementById("v-ambient");
const screenL = document.getElementById("screen-layer");
const screenQ = document.getElementById("screen-quad");
const bbsRoot = document.getElementById("bbs-root");

// ====================================================================
// Perspective warp (matrix3d) — lifted from /scene/.
// ====================================================================
function adj(m) {
  return [
    m[4]*m[8]-m[5]*m[7], m[2]*m[7]-m[1]*m[8], m[1]*m[5]-m[2]*m[4],
    m[5]*m[6]-m[3]*m[8], m[0]*m[8]-m[2]*m[6], m[2]*m[3]-m[0]*m[5],
    m[3]*m[7]-m[4]*m[6], m[1]*m[6]-m[0]*m[7], m[0]*m[4]-m[1]*m[3]
  ];
}
function multmm(a, b) {
  const c = Array(9);
  for (let i = 0; i < 3; i++) for (let j = 0; j < 3; j++) {
    let s = 0;
    for (let k = 0; k < 3; k++) s += a[3*i+k] * b[3*k+j];
    c[3*i+j] = s;
  }
  return c;
}
function multmv(m, v) {
  return [
    m[0]*v[0]+m[1]*v[1]+m[2]*v[2],
    m[3]*v[0]+m[4]*v[1]+m[5]*v[2],
    m[6]*v[0]+m[7]*v[1]+m[8]*v[2]
  ];
}
function basisToPoints(x1,y1,x2,y2,x3,y3,x4,y4) {
  const m = [x1,x2,x3, y1,y2,y3, 1,1,1];
  const v = multmv(adj(m), [x4,y4,1]);
  return multmm(m, [v[0],0,0, 0,v[1],0, 0,0,v[2]]);
}
function general2DProjection(s, d) {
  const ms = basisToPoints(s[0],s[1], s[2],s[3], s[4],s[5], s[6],s[7]);
  const md = basisToPoints(d[0],d[1], d[2],d[3], d[4],d[5], d[6],d[7]);
  return multmm(md, adj(ms));
}

const PLANE_W = 640, PLANE_H = 400;
let BASE_MATRIX3D = null;
let TRACK = null;

function getCornerPcts() {
  const s = getComputedStyle(document.documentElement);
  const num = k => parseFloat(s.getPropertyValue(k));
  return {
    tl: [num("--crt-tl-x"), num("--crt-tl-y")],
    tr: [num("--crt-tr-x"), num("--crt-tr-y")],
    br: [num("--crt-br-x"), num("--crt-br-y")],
    bl: [num("--crt-bl-x"), num("--crt-bl-y")],
  };
}
function applyWarp() {
  const r = wrap.getBoundingClientRect();
  const W = r.width, H = r.height;
  const c = getCornerPcts();
  const src = [0,0, PLANE_W,0, 0,PLANE_H, PLANE_W,PLANE_H];
  const dst = [
    W*c.tl[0]/100, H*c.tl[1]/100,
    W*c.tr[0]/100, H*c.tr[1]/100,
    W*c.bl[0]/100, H*c.bl[1]/100,
    W*c.br[0]/100, H*c.br[1]/100,
  ];
  let t = general2DProjection(src, dst);
  for (let i = 0; i < 9; i++) t[i] = t[i] / t[8];
  const m = [
    t[0],t[3],0,t[6],
    t[1],t[4],0,t[7],
    0,   0,   1,0,
    t[2],t[5],0,t[8],
  ];
  BASE_MATRIX3D = `matrix3d(${m.join(",")})`;
  screenQ.style.transform = BASE_MATRIX3D;
}
window.addEventListener("resize", applyWarp);
requestAnimationFrame(applyWarp);

// ====================================================================
// Motion track — load + apply per-frame matrix delta on rAF loop.
// ====================================================================
fetch("/bbs/monitor-track.json")
  .then(r => r.ok ? r.json() : null)
  .then(t => { TRACK = t; if (t) console.log(`[track] ${t.frame_count} frames`); })
  .catch(err => console.warn("[track] not available:", err));

const MOTION_DAMP = 0.27;
const MOTION_SMOOTH = 0.18;
let smA = 1, smB = 0, smC = 0, smD = 1, smE = 0, smF = 0;

function applyTrackedTransform() {
  if (!BASE_MATRIX3D) return;
  if (!TRACK || ambient.paused) {
    screenQ.style.transform = BASE_MATRIX3D;
    return;
  }
  const t = ambient.currentTime;
  const idx = Math.min(TRACK.frames.length - 1, Math.max(0, Math.round(t * TRACK.fps)));
  const f = TRACK.frames[idx];
  if (!f) { screenQ.style.transform = BASE_MATRIX3D; return; }
  const r = wrap.getBoundingClientRect();
  const sx = r.width / TRACK.width;
  const sy = r.height / TRACK.height;
  const [a, b, c2, d2, e, fY] = f.m;
  const tA = 1 + (a  - 1) * MOTION_DAMP;
  const tB =     b       * MOTION_DAMP;
  const tC =     c2      * MOTION_DAMP;
  const tD = 1 + (d2 - 1) * MOTION_DAMP;
  const tE = e * sx * MOTION_DAMP;
  const tF = fY * sy * MOTION_DAMP;
  smA += (tA - smA) * MOTION_SMOOTH;
  smB += (tB - smB) * MOTION_SMOOTH;
  smC += (tC - smC) * MOTION_SMOOTH;
  smD += (tD - smD) * MOTION_SMOOTH;
  smE += (tE - smE) * MOTION_SMOOTH;
  smF += (tF - smF) * MOTION_SMOOTH;
  screenQ.style.transform =
    `matrix(${smA}, ${smB}, ${smC}, ${smD}, ${smE}, ${smF}) ${BASE_MATRIX3D}`;
}
function trackLoop() {
  applyTrackedTransform();
  requestAnimationFrame(trackLoop);
}
requestAnimationFrame(trackLoop);

// ====================================================================
// Load manifest, then start router.
// ====================================================================
const MANIFEST_URL = "/bbs/manifest.json";
let manifest = { boards: [], articles: [] };

const ctx = {
  manifest,
  user: JSON.parse(localStorage.getItem("bbs.user") || "null"),
};

// ====================================================================
// Placeholder route renderers. Real screens land in Phase 3+.
// Each returns either a string (innerHTML) or { html, cleanup }.
// ====================================================================
function placeholder(title, body, choices) {
  const choiceLines = (choices || []).map(c =>
    `<div class="bbs-row">  <span class="bbs-bright">[${c.key}]</span> ${c.label}</div>`
  ).join("");
  return `<div class="bbs-screen">
<div class="bbs-header">${title}</div>
${body}
${choiceLines ? "\n" + choiceLines : ""}
<div class="bbs-prompt">\n&gt; <span class="bbs-cursor"></span></div>
</div>`;
}

route(/^$/, () => {
  // Default: go straight to menu. The /scene/ transition already showed
  // the "press any key" prompt, so we don't repeat it here.
  navigate("/menu");
});

route(/^login$/, () => {
  // Kept for back-nav from Q (logoff). Mirrors scene's final frame but
  // without the "press any key" line (it caused a flash on the handoff).
  return `<div class="bbs-screen">
<div class="bbs-row">  +==================================+</div>
<div class="bbs-row">  |   AIGREGATOR BBS    -   NODE 1   |</div>
<div class="bbs-row">  |   DAILY AI NEWS DIGEST           |</div>
<div class="bbs-row">  +==================================+</div>
<div class="bbs-row"> </div>
<div class="bbs-row"><span class="bbs-cursor"></span></div>
</div>`;
});

route(/^menu$/, () => placeholder(
  "MAIN MENU",
  `WELCOME${ctx.user ? `, ${ctx.user.handle}` : ""}.
ARTICLES LOADED: <span class="bbs-bright">${ctx.manifest.articles.length}</span>
BOARDS:          <span class="bbs-bright">${ctx.manifest.boards.length}</span>`,
  [
    { key: "1", label: "AI NEWS BOARD" },
    { key: "2", label: "ARCHIVES" },
    { key: "3", label: "ABOUT THIS BBS" },
    { key: "4", label: "DOOR GAMES" },
    { key: "5", label: "SEARCH" },
    { key: "Q", label: "LOGOFF" },
  ]
));

// Per-board cursor state — tracks selected article index for arrow nav.
const boardCursor = {};

route(/^board\/([\w-]+)$/, ([boardId]) => {
  const board = ctx.manifest.boards.find(b => b.id === boardId);
  if (!board) return `<div>BOARD NOT FOUND: ${boardId}</div>`;
  const arts = ctx.manifest.articles.filter(a => a.board === boardId);
  if (boardCursor[boardId] == null) boardCursor[boardId] = 0;
  if (boardCursor[boardId] >= arts.length) boardCursor[boardId] = Math.max(0, arts.length - 1);
  const sel = boardCursor[boardId];
  const list = arts.length
    ? arts.map((a, i) => {
        const marker = i === sel ? ">" : " ";
        const cls = i === sel ? "bbs-row bbs-selected" : "bbs-row";
        return `<div class="${cls}" data-idx="${i}" data-id="${a.id}">${marker} [${String(i+1).padStart(2,"0")}] ${a.date}  ${a.title.slice(0,48)}</div>`;
      }).join("")
    : `<div class="bbs-dim">NO MESSAGES ON THIS BOARD.</div>`;
  const hint = arts.length
    ? `<span class="bbs-dim">↑/↓ to select  ·  ENTER to read  ·  [B] back  ·  (${sel+1}/${arts.length})</span>`
    : `<span class="bbs-dim">[B] back</span>`;
  // Wrap rows in a scrollable container so long lists don't get clipped
  // by the CRT mask. cleanup() runs scroll-into-view after the DOM mounts.
  const html = placeholder(
    `BOARD: ${board.name}`,
    `${board.description}

${hint}

<div id="board-scroll" class="bbs-scroll">${list}</div>`,
    [{ key: "B", label: "BACK" }]
  );
  // Trigger scroll-into-view after this render commits.
  scrollSelectedIntoView();
  return {
    html,
    cleanup: () => {},
  };
});

// After board re-renders, scroll the selected row into view.
function scrollSelectedIntoView() {
  setTimeout(() => {
    const row = document.querySelector(".bbs-selected");
    const root = document.getElementById("bbs-root");
    if (!row || !root) return;
    // Manual scroll calc — scrollIntoView is unreliable on masked containers.
    const rowTop = row.offsetTop;
    const rowBot = rowTop + row.offsetHeight;
    const viewTop = root.scrollTop;
    const viewBot = viewTop + root.clientHeight;
    const pad = 40; // keep cursor away from the mask edge
    if (rowTop < viewTop + pad) {
      root.scrollTop = Math.max(0, rowTop - pad);
    } else if (rowBot > viewBot - pad) {
      root.scrollTop = rowBot - root.clientHeight + pad;
    }
  }, 0);
}

route(/^article\/(.+)$/, ([id]) => {
  const a = ctx.manifest.articles.find(x => x.id === id);
  if (!a) return `<div>ARTICLE NOT FOUND: ${id}</div>`;
  return placeholder(
    `${a.title}`,
    `${a.date}  ·  ${a.read_min} min  ·  ${a.word_count} words

<span class="bbs-dim">(article reader stub — Phase 3 wraps body to 64 cols + scroll)</span>

${a.summary}`,
    [
      { key: "B", label: "BACK TO BOARD" },
      { key: "N", label: "NEXT ARTICLE" },
      { key: "P", label: "PREVIOUS" },
    ]
  );
});

route(/^doors$/, () => placeholder(
  "DOOR GAMES",
  `Select a door:`,
  [
    { key: "1", label: "WARGAMES (global thermonuclear war sim)" },
    { key: "2", label: "TIC TAC TOE (vs CPU)" },
    { key: "3", label: "AIGREGATOR QUEST (text adventure)" },
    { key: "4", label: "GATOR RUN (jump or die)" },
    { key: "B", label: "BACK" },
  ]
));

// ─── SEARCH ────────────────────────────────────────────
let searchQuery = "";
let searchSel = 0;

route(/^search$/, () => {
  const q = searchQuery.toLowerCase().trim();
  const all = ctx.manifest.articles || [];
  const hits = q
    ? all.filter(a =>
        (a.title || "").toLowerCase().includes(q) ||
        (a.summary || "").toLowerCase().includes(q) ||
        (a.tags || []).some(t => String(t).toLowerCase().includes(q))
      )
    : [];
  if (searchSel >= hits.length) searchSel = Math.max(0, hits.length - 1);
  const cursor = `<span class="bbs-cursor"></span>`;
  const resultsList = q
    ? (hits.length
        ? hits.map((a, i) => {
            const marker = i === searchSel ? ">" : " ";
            const cls = i === searchSel ? "bbs-row bbs-selected" : "bbs-row";
            return `<div class="${cls}" data-id="${a.id}">${marker} ${a.date}  ${a.title.slice(0,52)}</div>`;
          }).join("")
        : `<div class="bbs-dim">  no results.</div>`)
    : `<div class="bbs-dim">  start typing to search titles, summaries, and tags.</div>`;

  const html = placeholder(
    "SEARCH",
    `<span class="bbs-dim">type to filter  ·  ↑/↓ select  ·  ENTER read  ·  ESC clear  ·  [B] back</span>

SEARCH: <span class="bbs-bright">${escapeHtml(searchQuery) || " "}</span>${cursor}

${q ? `<span class="bbs-dim">${hits.length} result(s):</span>` : ""}
${resultsList}`,
    [{ key: "B", label: "BACK" }]
  );
  scrollSelectedIntoView();
  return { html, cleanup: () => {} };
});

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

route(/^about$/, () => placeholder(
  "ABOUT THIS BBS",
  `AIGREGATOR BBS - NODE 1
SYSOP: Brian Baldock + Hermes
EST.   2026

Daily AI news digest, reimagined as a 1990s bulletin board.
The room is real video. The monitor is real geometry. The text is
projected onto the screen with motion tracking so it follows the
camera's micro-drift.

Phase 1: motion track + CRT polish (SHIPPED)
Phase 2: manifest + routing (SHIPPED)
Phase 3+: login, boards, reader, search, ANSI splash (TBD)
Phase 4: door games (TBD)`,
  [{ key: "B", label: "BACK" }]
));

// ====================================================================
// Door games — each is a self-contained module that returns { html, cleanup }
// and may register a keyboard handler via window.__setDoorKeyHandler(fn).
// ====================================================================
const doorModules = {
  wargames: () => import("./doors/wargames.js"),
  ttt:      () => import("./doors/ttt.js"),
  quest:    () => import("./doors/quest.js"),
  gator:    () => import("./doors/gator.js"),
};

route(/^door\/(\w+)$/, ([gameId]) => {
  if (!doorModules[gameId]) return `<div>UNKNOWN DOOR: ${gameId}</div>`;
  if (window.__setDoorKeyHandler) window.__setDoorKeyHandler(null);
  document.body.classList.add("in-door");
  doorModules[gameId]().then(mod => {
    const result = mod.start(bbsRoot, ctx, navigate);
    if (result?.keyHandler) window.__setDoorKeyHandler(result.keyHandler);
  }).catch(err => {
    console.error(`[door] ${gameId} failed:`, err);
    bbsRoot.innerHTML = `<div class="bbs-screen">DOOR LOAD FAILED: ${gameId}<br>[B] BACK</div>`;
  });
  return `<div class="bbs-screen"><div class="bbs-dim">LOADING ${gameId.toUpperCase()}...</div></div>`;
});

// ====================================================================
// Bootstrap
// ====================================================================
// Bootstrap: start router immediately so the "press any key" banner appears
// the instant the page loads (matches scene's final frame for a seamless
// handoff from /scene/). Manifest loads in parallel — it's only needed
// once the user navigates into menu/boards.
start(bbsRoot, ctx, "");

fetch(MANIFEST_URL)
  .then(r => r.json())
  .then(m => {
    manifest = m;
    ctx.manifest = m;
    console.log(`[bbs] loaded manifest: ${m.articles.length} articles`);
    // Re-render current route now that manifest is available — fixes
    // "BOARD NOT FOUND" if user navigated before manifest finished loading.
    navigate(location.hash.replace(/^#/, "") || "/menu");
  })
  .catch(err => {
    console.error("[bbs] manifest load failed:", err);
  });

// Lock mouse-wheel scrolling on the CRT — arrow keys are the only nav
// mechanism. Programmatic scrollTop (used by scrollSelectedIntoView)
// still works because we only block wheel events.
bbsRoot.addEventListener("wheel", (e) => e.preventDefault(), { passive: false });

// Per-screen key → route map. Keyboard + click both consult this.
// Keys are uppercased; ENTER means any key on stub screens.
function currentPath() {
  return location.hash.replace(/^#\/?/, "");
}
function keymapFor(path) {
  if (path === "" || path === "login") {
    return { "ENTER": "/menu", " ": "/menu" };
  }
  if (path === "menu") {
    return {
      "1": "/board/news",
      "2": "/board/archive",
      "3": "/about",
      "4": "/doors",
      "5": "/search",
      "Q": "/login",
    };
  }
  if (path.startsWith("board/")) {
    const arts = ctx.manifest.articles.filter(a => a.board === path.split("/")[1]);
    const map = { "B": "/menu" };
    arts.forEach((a, i) => {
      const n = String(i + 1).padStart(2, "0");
      map[n] = `/article/${a.id}`;
      // Also accept single-digit for first 9
      if (i < 9) map[String(i + 1)] = `/article/${a.id}`;
    });
    return map;
  }
  if (path.startsWith("article/")) {
    return { "B": "/board/news" };
  }
  if (path === "doors") {
    const map = {
      "1": "/door/wargames",
      "2": "/door/ttt",
      "3": "/door/quest",
      "4": "/door/gator",
      "B": "/menu",
    };
    return map;
  }
  if (path.startsWith("door/")) {
    return { "B": "/doors" };
  }
  if (path === "search" || path === "about") {
    return { "B": "/menu" };
  }
  return { "B": "/menu" };
}

// Click handler: any [KEY] span in the rendered screen, or any article row on a board.
bbsRoot.addEventListener("click", (e) => {
  const t = e.target;
  // Article row click (board screens)
  const row = t.closest?.(".bbs-row[data-id]");
  if (row) {
    navigate(`/article/${row.dataset.id}`);
    return;
  }
  if (!t || t.nodeName !== "SPAN") return;
  if (!t.classList.contains("bbs-bright")) return;
  const key = t.textContent.replace(/[\[\]]/g, "").trim().toUpperCase();
  const map = keymapFor(currentPath());
  if (map[key]) navigate(map[key]);
});

// Keyboard handler: number/letter keys, arrows, Enter, Backspace.
document.addEventListener("keydown", e => {
  const path = currentPath();

  // Door games handle their own input — delegate fully.
  if (path.startsWith("door/")) {
    if (doorKeyHandler && doorKeyHandler(e) === true) return;
    if (e.key === "Escape") { navigate("/doors"); return; }
    return;
  }

  if (e.key === "Escape") {
    // Search: ESC clears the query instead of exiting.
    if (path === "search") {
      if (searchQuery) {
        e.preventDefault();
        searchQuery = ""; searchSel = 0;
        navigate("/search");
        return;
      }
      navigate("/menu"); return;
    }
    window.location.href = "/";
    return;
  }
  if (e.key === "Backspace") {
    if (path === "search") {
      e.preventDefault();
      searchQuery = searchQuery.slice(0, -1);
      searchSel = 0;
      navigate("/search");
      return;
    }
    e.preventDefault(); navigate("/menu"); return;
  }

  // Search: type-to-filter, ↑/↓ select, ENTER open.
  if (path === "search") {
    const q = searchQuery.toLowerCase().trim();
    const all = ctx.manifest.articles || [];
    const hits = q ? all.filter(a =>
      (a.title || "").toLowerCase().includes(q) ||
      (a.summary || "").toLowerCase().includes(q) ||
      (a.tags || []).some(t => String(t).toLowerCase().includes(q))
    ) : [];

    if (e.key === "ArrowDown" && hits.length) {
      e.preventDefault();
      searchSel = (searchSel + 1) % hits.length;
      navigate("/search"); return;
    }
    if (e.key === "ArrowUp" && hits.length) {
      e.preventDefault();
      searchSel = (searchSel - 1 + hits.length) % hits.length;
      navigate("/search"); return;
    }
    if (e.key === "Enter" && hits.length) {
      e.preventDefault();
      navigate(`/article/${hits[searchSel].id}`); return;
    }
    // Printable character: append to query.
    if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
      e.preventDefault();
      searchQuery += e.key;
      searchSel = 0;
      navigate("/search");
      return;
    }
    return;
  }

  // Board screens: arrow keys move the cursor, Enter opens the article.
  if (path.startsWith("board/")) {
    const boardId = path.split("/")[1];
    const arts = ctx.manifest.articles.filter(a => a.board === boardId);
    if (arts.length) {
      if (e.key === "ArrowDown") {
        e.preventDefault();
        boardCursor[boardId] = (boardCursor[boardId] + 1) % arts.length;
        navigate(`/board/${boardId}`);
        scrollSelectedIntoView();
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        boardCursor[boardId] = (boardCursor[boardId] - 1 + arts.length) % arts.length;
        navigate(`/board/${boardId}`);
        scrollSelectedIntoView();
        return;
      }
      if (e.key === "Enter") {
        e.preventDefault();
        const a = arts[boardCursor[boardId]];
        if (a) navigate(`/article/${a.id}`);
        return;
      }
    }
  }

  const map = keymapFor(path);
  if (e.key === "Enter" && map["ENTER"]) { navigate(map["ENTER"]); return; }
  const k = e.key.length === 1 ? e.key.toUpperCase() : e.key;
  if (map[k]) { e.preventDefault(); navigate(map[k]); }
});

// Door games register their own keydown handler via this hook.
// They return true if they consumed the key, false to let main handle it.
let doorKeyHandler = null;
window.__setDoorKeyHandler = (fn) => { doorKeyHandler = fn; };

// Toggle door body class based on route so bbs-root scroll is locked
// only while inside a game (boards still need scrolling).
window.addEventListener("hashchange", () => {
  const inDoor = location.hash.startsWith("#/door/");
  document.body.classList.toggle("in-door", inDoor);
  if (!inDoor) doorKeyHandler = null;
});
