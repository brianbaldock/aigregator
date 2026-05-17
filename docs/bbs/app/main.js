// /bbs/ entrypoint. Sets up CRT warp + motion track + router, loads
// the article manifest, registers placeholder route renderers. Real
// screen renderers (login, menu, board, article, search, doors) land
// in Phase 3+.

import { route, start, navigate } from "./router.js";

// ====================================================================
// Mobile gate — desktop only per design call. Strict width gate;
// `pointer: coarse` false-positives on touchscreen laptops.
const MIN_VW = 768;
if (window.innerWidth < MIN_VW) {
  document.getElementById("mobile-gate").hidden = false;
  document.getElementById("stage").style.display = "none";
  throw new Error("mobile-gate: bailing");
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
  // Default: jump to login if no user, else menu
  navigate(ctx.user ? "/menu" : "/login");
});

route(/^login$/, () => placeholder(
  "*** AIGREGATOR BBS - NODE 1 ***",
  `SECURE 56K CONNECTION ESTABLISHED.

NEW CALLER DETECTED.
PLEASE ENTER YOUR HANDLE:

<span class="bbs-dim">(login screen — Phase 3 will wire keyboard input here)</span>`,
  [{ key: "ENTER", label: "STUB: press any key to continue → menu" }]
));

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

route(/^board\/([\w-]+)$/, ([boardId]) => {
  const board = ctx.manifest.boards.find(b => b.id === boardId);
  if (!board) return `<div>BOARD NOT FOUND: ${boardId}</div>`;
  const arts = ctx.manifest.articles.filter(a => a.board === boardId);
  const list = arts.length
    ? arts.map((a, i) =>
        `<div class="bbs-row">[${String(i+1).padStart(2,"0")}] ${a.date}  ${a.title.slice(0,48)}</div>`
      ).join("")
    : `<div class="bbs-dim">NO MESSAGES ON THIS BOARD.</div>`;
  return placeholder(
    `BOARD: ${board.name}`,
    `${board.description}\n\n${list}`,
    [{ key: "B", label: "BACK" }]
  );
});

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
  `Phase 4 lands the playable doors.`,
  [
    { key: "1", label: "WARGAMES" },
    { key: "2", label: "THE ORACLE" },
    { key: "3", label: "TIC TAC TOE" },
    { key: "4", label: "AIGREGATOR QUEST (text adventure)" },
    { key: "B", label: "BACK" },
  ]
));

route(/^search$/, () => placeholder(
  "SEARCH",
  `SEARCH: > <span class="bbs-cursor"></span>

<span class="bbs-dim">(search stub — Phase 3 wires substring match against manifest)</span>`,
  [{ key: "B", label: "BACK" }]
));

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
// Bootstrap
// ====================================================================
fetch(MANIFEST_URL)
  .then(r => r.json())
  .then(m => {
    manifest = m;
    ctx.manifest = m;
    console.log(`[bbs] loaded manifest: ${m.articles.length} articles`);
    start(bbsRoot, ctx, "");
  })
  .catch(err => {
    console.error("[bbs] manifest load failed:", err);
    bbsRoot.textContent = "\nERROR: manifest.json failed to load.";
  });

// Hover-route helpers for stub navigation during dev. Click any
// [LETTER] / [NUMBER] in the prompt list to jump.
bbsRoot.addEventListener("click", (e) => {
  const t = e.target;
  if (!t || t.nodeName !== "SPAN") return;
  if (!t.classList.contains("bbs-bright")) return;
  const key = t.textContent.replace(/[\[\]]/g, "").trim().toUpperCase();
  const routesMap = {
    "1": "/board/news",
    "2": "/board/archive",
    "3": "/about",
    "4": "/doors",
    "5": "/search",
    "B": "/menu",
    "Q": "/login",
  };
  if (routesMap[key]) navigate(routesMap[key]);
});

// ESC = exit to main site
document.addEventListener("keydown", e => {
  if (e.key === "Escape") window.location.href = "/";
});
