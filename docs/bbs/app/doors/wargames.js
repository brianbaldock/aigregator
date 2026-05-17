// WARGAMES — DEFCON missile launch simulator, themed after the 1983 movie.
// Plays the iconic "Shall we play a game?" sequence, lets the user pick a
// target, then runs through tic-tac-toe-style learning to the famous line:
// "THE ONLY WINNING MOVE IS NOT TO PLAY."

const TARGETS = [
  { name: "LAS VEGAS",      city: "NV" },
  { name: "SEATTLE",        city: "WA" },
  { name: "WASHINGTON DC",  city: "DC" },
  { name: "NEW YORK",       city: "NY" },
  { name: "MOSCOW",         city: "USSR" },
  { name: "LENINGRAD",      city: "USSR" },
];

const SCENES = [
  { type: "type", text: "LOGON: " },
  { type: "type", text: "JOSHUA", color: "bright" },
  { type: "wait", ms: 800 },
  { type: "line", text: "" },
  { type: "line", text: "GREETINGS PROFESSOR FALKEN." },
  { type: "wait", ms: 1200 },
  { type: "line", text: "" },
  { type: "line", text: "HOW ARE YOU FEELING TODAY?" },
  { type: "wait", ms: 900 },
  { type: "line", text: "" },
  { type: "line", text: "> I'M FINE. HOW ARE YOU?" },
  { type: "wait", ms: 1100 },
  { type: "line", text: "" },
  { type: "line", text: "EXCELLENT. IT'S BEEN A LONG TIME. CAN YOU EXPLAIN" },
  { type: "line", text: "THE REMOVAL OF YOUR USER ACCOUNT ON 6/23/73?" },
  { type: "wait", ms: 1400 },
  { type: "line", text: "" },
  { type: "line", text: "> PEOPLE SOMETIMES MAKE MISTAKES." },
  { type: "wait", ms: 1200 },
  { type: "line", text: "" },
  { type: "line", text: "YES THEY DO. SHALL WE PLAY A GAME?" },
  { type: "wait", ms: 800 },
  { type: "prompt" },
];

const STATE = {
  phase: "intro",      // intro -> menu -> launch -> defcon -> end
  defcon: 5,
  selectedTarget: 0,
  scriptIdx: 0,
  scrollEl: null,
};

let mountEl = null;
let onNavigate = null;
let tickHandle = null;

function el(html) {
  mountEl.innerHTML = html;
  STATE.scrollEl = mountEl.querySelector("#wopr-out");
}

function append(line, cls) {
  if (!STATE.scrollEl) return;
  const d = document.createElement("div");
  d.className = "bbs-row" + (cls ? " " + cls : "");
  d.textContent = line;
  STATE.scrollEl.appendChild(d);
  // Auto-scroll to bottom on new output.
  STATE.scrollEl.scrollTop = STATE.scrollEl.scrollHeight;
}

function renderShell(title, footer) {
  const defconColor = STATE.defcon <= 2 ? "bbs-bright" : "bbs-dim";
  return `<div class="bbs-screen">
<div class="bbs-header">${title}</div>
<div class="bbs-row"><span class="${defconColor}">[ DEFCON ${STATE.defcon} ]</span>  NORAD ::  W.O.P.R.  ::  CHEYENNE MTN COMPLEX</div>
<div class="bbs-row">────────────────────────────────────────────────────</div>
<div id="wopr-out" class="bbs-scroll-pane"></div>
<div class="bbs-row">────────────────────────────────────────────────────</div>
<div class="bbs-row bbs-dim">${footer}</div>
</div>`;
}

// Cap lines so nothing falls off the bottom of the CRT.
const MAX_LINES = 14;
function trimLines() {
  if (!STATE.scrollEl) return;
  while (STATE.scrollEl.children.length > MAX_LINES) {
    STATE.scrollEl.removeChild(STATE.scrollEl.firstChild);
  }
}

async function runIntro() {
  el(renderShell("WOPR — STRATEGIC AIR COMMAND", "PRESS ENTER TO CONTINUE  ·  ESC: ABORT"));
  for (const step of SCENES) {
    if (STATE.phase !== "intro") return; // user navigated away
    if (step.type === "wait") {
      await sleep(step.ms);
    } else if (step.type === "line") {
      append(step.text);
    } else if (step.type === "type") {
      await typeOut(step.text, step.color === "bright");
    } else if (step.type === "prompt") {
      STATE.phase = "menu";
      renderMenu();
    }
  }
}

async function typeOut(text, bright) {
  const d = document.createElement("div");
  d.className = "bbs-row" + (bright ? " bbs-bright" : "");
  STATE.scrollEl.appendChild(d);
  for (const ch of text) {
    if (STATE.phase !== "intro") return;
    d.textContent += ch;
    await sleep(45 + Math.random() * 40);
  }
}

function sleep(ms) { return new Promise(r => setTimeout(r, ms)); }

function renderMenu() {
  el(renderShell("WOPR — GAME LIBRARY", "↑/↓ select target  ·  ENTER launch  ·  ESC abort"));
  append("LIST GAMES", "bbs-dim");
  append("> GLOBAL THERMONUCLEAR WAR", "bbs-bright");
  append("");
  append("WHICH SIDE DO YOU WANT?", "bbs-dim");
  append("");
  renderTargets();
}

function renderTargets() {
  TARGETS.forEach((t, i) => {
    const marker = i === STATE.selectedTarget ? ">" : " ";
    const cls = i === STATE.selectedTarget ? "bbs-selected" : "";
    append(`${marker} [${i+1}] ${t.name.padEnd(20)} ${t.city}`, cls);
  });
}

function refreshTargets() {
  // Re-render menu cleanly to update selection
  renderMenu();
}

function launchSequence() {
  STATE.phase = "launch";
  el(renderShell("STRATEGIC MISSILE LAUNCH", "STAND BY  ·  ESC: ABORT"));
  const target = TARGETS[STATE.selectedTarget];
  append(`TARGET ACQUIRED: ${target.name}, ${target.city}`, "bbs-bright");
  append("");

  let countdown = 5;
  const countdownTimer = setInterval(() => {
    if (STATE.phase !== "launch") { clearInterval(countdownTimer); return; }
    if (countdown > 0) {
      append(`  T-MINUS ${countdown}...`);
      countdown--;
    } else {
      clearInterval(countdownTimer);
      append("");
      append("  *** LAUNCH ***", "bbs-bright");
      append("");
      setTimeout(beginSimulation, 1000);
    }
  }, 700);
}

function beginSimulation() {
  STATE.phase = "defcon";
  STATE.defcon = 5;
  el(renderShell("GLOBAL THERMONUCLEAR WAR", "WOPR IS THINKING...  ·  ESC: ABORT"));
  append("USSR RESPONDS WITH FULL ICBM SALVO.", "bbs-bright");
  append("");

  const map = [
    "       . . .   _____.____.____         ",
    "    ._/ U.S.A. \\___.    ._.    \\       ",
    "   /                 \\__/       \\___   ",
    "   \\.        *  *     .       *   .|   ",
    "    \\_.    *    .      \\__.       /    ",
    "       \\____.________.____.______/     ",
    "                                       ",
    "          *  USSR  *  *                ",
    "       /‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾\\         ",
    "      /  .   .    *    .  *   \\        ",
    "      \\__________________________\\     ",
  ];
  map.forEach(l => append(l));
  append("");

  // Drop DEFCON over time
  const defconSteps = [
    { delay: 1200, msg: "RADAR DETECTS 412 INBOUND TRACKS." },
    { delay: 1400, msg: "DEFCON 4." },
    { delay: 1400, msg: "DEFCON 3." },
    { delay: 1400, msg: "DEFCON 2." },
    { delay: 1400, msg: "DEFCON 1." },
    { delay: 1400, msg: "" },
    { delay: 600, msg: "WOPR IS RUNNING SIMULATIONS..." },
    { delay: 1000, msg: "" },
  ];

  let i = 0;
  const stepFn = () => {
    if (STATE.phase !== "defcon") return;
    if (i >= defconSteps.length) { runSimulations(); return; }
    const s = defconSteps[i++];
    setTimeout(() => {
      const m = s.msg.match(/^DEFCON (\d)\.$/);
      if (m) {
        STATE.defcon = parseInt(m[1]);
        el(renderShell("GLOBAL THERMONUCLEAR WAR", "WOPR IS THINKING...  ·  ESC: ABORT"));
        map.forEach(l => append(l));
        append("");
        for (let j = 0; j < i; j++) append(defconSteps[j].msg, defconSteps[j].msg.startsWith("DEFCON") ? "bbs-bright" : "");
      } else {
        append(s.msg, s.msg.includes("INBOUND") || s.msg.includes("SIMULATIONS") ? "bbs-bright" : "");
      }
      stepFn();
    }, s.delay);
  };
  stepFn();
}

function runSimulations() {
  STATE.phase = "sim";
  const sims = [
    "US FIRST STRIKE :: WINNER NONE",
    "USSR FIRST STRIKE :: WINNER NONE",
    "NATO/WARSAW PACT :: WINNER NONE",
    "FAR EAST STRATEGY :: WINNER NONE",
    "US/USSR ESCALATION :: WINNER NONE",
    "MIDDLE EAST WAR :: WINNER NONE",
    "ARCTIC EXCHANGE :: WINNER NONE",
    "SUBMARINE ENGAGEMENT :: WINNER NONE",
  ];
  let i = 0;
  const interval = setInterval(() => {
    if (STATE.phase !== "sim") { clearInterval(interval); return; }
    if (i >= sims.length) {
      clearInterval(interval);
      setTimeout(endgame, 1200);
      return;
    }
    append(sims[i++], "bbs-dim");
  }, 250);
}

function endgame() {
  STATE.phase = "end";
  el(renderShell("WOPR — CONCLUSION", "ENTER or B to return  ·  ESC: abort"));
  append("");
  append("A STRANGE GAME.", "bbs-bright");
  append("");
  append("THE ONLY WINNING MOVE IS", "bbs-bright");
  append("NOT TO PLAY.", "bbs-bright");
  append("");
  append("");
  append("HOW ABOUT A NICE GAME OF CHESS?", "bbs-dim");
}

function keyHandler(e) {
  if (e.key === "Escape") {
    cleanup();
    onNavigate("/doors");
    return true;
  }
  // Scroll keys work in any phase except menu (which uses ↑/↓ for target).
  if (STATE.scrollEl && STATE.phase !== "menu") {
    const pane = STATE.scrollEl;
    const lineH = 28; // approx VT323 line at 22px
    if (e.key === "ArrowUp")   { e.preventDefault(); pane.scrollTop -= lineH * 2; return true; }
    if (e.key === "ArrowDown") { e.preventDefault(); pane.scrollTop += lineH * 2; return true; }
    if (e.key === "PageUp")    { e.preventDefault(); pane.scrollTop -= pane.clientHeight; return true; }
    if (e.key === "PageDown")  { e.preventDefault(); pane.scrollTop += pane.clientHeight; return true; }
    if (e.key === "Home")      { e.preventDefault(); pane.scrollTop = 0; return true; }
    if (e.key === "End")       { e.preventDefault(); pane.scrollTop = pane.scrollHeight; return true; }
  }
  if (STATE.phase === "menu") {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      STATE.selectedTarget = (STATE.selectedTarget + 1) % TARGETS.length;
      refreshTargets();
      return true;
    }
    if (e.key === "ArrowUp") {
      e.preventDefault();
      STATE.selectedTarget = (STATE.selectedTarget - 1 + TARGETS.length) % TARGETS.length;
      refreshTargets();
      return true;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      launchSequence();
      return true;
    }
    const n = parseInt(e.key, 10);
    if (n >= 1 && n <= TARGETS.length) {
      STATE.selectedTarget = n - 1;
      launchSequence();
      return true;
    }
  }
  if (STATE.phase === "end") {
    if (e.key === "Enter" || e.key === "b" || e.key === "B") {
      cleanup();
      onNavigate("/doors");
      return true;
    }
  }
  return true; // swallow everything while inside the door
}

function cleanup() {
  STATE.phase = "intro";
  STATE.defcon = 5;
  STATE.selectedTarget = 0;
  if (tickHandle) { clearTimeout(tickHandle); tickHandle = null; }
}

export function start(mount, ctx, navigate) {
  mountEl = mount;
  onNavigate = navigate;
  cleanup();
  runIntro();
  return { keyHandler };
}
