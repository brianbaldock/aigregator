// AIGREGATOR QUEST — Zork-style text adventure, AI-news themed.
// Wake up in the AIgregator datacenter on the eve of MODEL COLLAPSE.
// Find the COLD STORAGE VAULT, recover the LAST CLEAN DATASET, escape
// via the EXIT NODE before the GRAY GOO consumes everything.

let mountEl = null;
let onNavigate = null;

const ROOMS = {};
const ITEMS = {};
// Populated at module-load via build helpers below to keep this file compact.

function addRoom(id, name, desc, exits, items, extras) {
  ROOMS[id] = { name, desc, exits: exits || {}, items: items || [], ...(extras || {}) };
}
function addItem(id, desc) { ITEMS[id] = desc; }

addRoom("lobby", "RECEPTION LOBBY",
  "Pristine glass and a dead receptionist bot. The wall is covered in framed 2023 seed funding announcements. EAST: revolving doors. DOWN: engineering. UP: ceiling hatch.",
  { east: "parking", down: "engineering", up: "ducts" }, ["badge"]);
addRoom("parking", "PARKING LOT",
  "Cybertrucks bake in the sun, doors stuck open mid-OTA. Your car was towed long ago. WEST: lobby.",
  { west: "lobby" }, ["protein-bar"]);
addRoom("ducts", "AIR DUCTS",
  "Cold metal, dust, the distant whirr of fans. NORTH: server room. DOWN: lobby.",
  { north: "cooling", down: "lobby" });
addRoom("engineering", "ENGINEERING FLOOR",
  "Standing desks abandoned mid-standup. A whiteboard reads 'Q4 ROADMAP: PRINCIPLES OF AI 2.0' and is otherwise blank. EAST: coffee. WEST: racks. NORTH: closet. SOUTH: bathroom. UP: lobby. DOWN: datacenter.",
  { east: "coffee", west: "racks", north: "closet", south: "bathroom", up: "lobby", down: "datacenter" }, ["laptop"]);
addRoom("coffee", "COFFEE BAR",
  "Industrial espresso machine, cold. Sticky note on the grinder: 'beans require root access'. WEST: engineering.",
  { west: "engineering" }, ["mug"]);
addRoom("racks", "SERVER RACKS",
  "Forty-two 2U pizza boxes humming. One dark rack labeled 'INFERENCE-PRIMARY'. EAST: engineering. NORTH: cooling. DOWN: datacenter.",
  { east: "engineering", north: "cooling", down: "datacenter" }, ["keycard"]);
addRoom("cooling", "COOLING CHAMBER",
  "Sub-zero. Your breath fogs. A frozen lab tech clutches a USB stick. SOUTH: racks. DOWN: datacenter.",
  { south: "racks", down: "datacenter" }, ["usb-stick"]);
addRoom("datacenter", "MAIN DATACENTER",
  "Cathedral of compute. GPUs pulse in sync drawing 6MW. NORTH: training. SOUTH: inference. EAST: library. WEST: lab. UP: engineering. A locked DOOR is marked 'COLD STORAGE — AUTH REQUIRED'.",
  { north: "training", south: "inference", east: "library", west: "lab", up: "engineering", door: "vault" }, [],
  { lockedExit: { dir: "door", needs: "keycard", message: "The reader blinks red. AUTH REQUIRED." } });
addRoom("training", "TRAINING WING",
  "8000 H200s screaming. A loss curve on the wall has flatlined for 47 days. SOUTH: datacenter.",
  { south: "datacenter" }, ["loss-curve-printout"]);
addRoom("inference", "INFERENCE WING",
  "Quieter than training. A logbook on a desk reads 'p99 latency spiking. ROOT CAUSE: synthetic data contamination.' NORTH: datacenter.",
  { north: "datacenter" }, ["logbook"]);
addRoom("library", "THE LIBRARY",
  "Petabytes of training corpora on tape. A librarian-bot rocks back and forth murmuring 'cite your sources, cite your sources'. WEST: datacenter.",
  { west: "datacenter" }, ["dataset-shard"]);
addRoom("lab", "RESEARCH LAB",
  "Whiteboards covered in attention diagrams. A poster reads 'PROMPT INJECTION: WORKED EXAMPLES'. EAST: datacenter. A SECRET passage gapes behind a loose ceiling tile.",
  { east: "datacenter", secret: "tunnel" }, ["paper"]);
addRoom("tunnel", "UNLIT CORRIDOR",
  "Pitch black. Water drips somewhere. NORTH continues. SOUTH: lab.",
  { north: "tunnelExit", south: "lab" }, [], { dark: true });
addRoom("tunnelExit", "EMERGENCY STAIRWELL",
  "A bare bulb swings overhead. UP: rooftop. SOUTH: tunnel.",
  { up: "rooftop", south: "tunnel" });
addRoom("rooftop", "ROOFTOP",
  "Wind, satellite dishes, and a horizon being swallowed by the GRAY GOO — a tide of synthetic data eating the city. DOWN: stairwell.",
  { down: "tunnelExit" }, ["radio"]);
addRoom("vault", "COLD STORAGE VAULT",
  "Climate-controlled, pristine. Tape spools labeled CC-MAIN-2019 through CC-MAIN-2022. A pedestal holds the LAST CLEAN DATASET — a single golden DVD-R. WEST: datacenter.",
  { west: "datacenter" }, ["dvd"]);
addRoom("exitNode", "EXIT NODE",
  "A glowing terminal at the end of a long corridor.\n\n  > INSERT LAST CLEAN DATASET\n\nSOUTH: rooftop.",
  { south: "rooftop" }, [], { isExit: true });
addRoom("closet", "JANITOR CLOSET",
  "Mops, buckets, a single dusty CRT showing static. SOUTH: engineering.",
  { south: "engineering" }, ["flashlight"]);
addRoom("bathroom", "BATHROOM",
  "A line of stalls. Graffiti reads 'GPT-2 WAS ENOUGH'. NORTH: engineering.",
  { north: "engineering" });
addRoom("drone", "RESCUE DRONE",
  "A wobbly quadcopter the size of a refrigerator. It chirps and extends a docking arm toward the EXIT NODE. DOWN: rooftop. DOCK: exit node.",
  { down: "rooftop", dock: "exitNode" });

addItem("badge",               "EMPLOYEE BADGE — issued to 'I. ASIMOV'.");
addItem("protein-bar",         "PROTEIN BAR — expired six months ago. Still edible.");
addItem("laptop",              "LAPTOP — sticker-covered, 2% battery, fan dead.");
addItem("mug",                 "MUG — reads 'KEEP CALM AND TRAIN ON'.");
addItem("keycard",             "KEYCARD — magstripe + RFID. Reads 'COLD STORAGE: AUTHORIZED'.");
addItem("usb-stick",           "USB STICK — labeled in Sharpie: 'WEIGHTS — DO NOT LOSE'.");
addItem("loss-curve-printout", "PRINTOUT — a flatlined training curve, 47 days of nothing.");
addItem("logbook",             "LOGBOOK — last entry: 'rolling back. we trained on our own outputs.'");
addItem("dataset-shard",       "TAPE SHARD — Common Crawl, 2019. Heavy.");
addItem("paper",               "PAPER — 'Attention Is All You Need' (printed, dog-eared).");
addItem("flashlight",          "FLASHLIGHT — heavy, D-cells, works.");
addItem("radio",               "HAM RADIO — could broadcast a distress call.");
addItem("dvd",                 "GOLDEN DVD-R — THE LAST CLEAN DATASET. Pre-2022 internet. Don't drop it.");

const state = {
  room: "lobby",
  inv: [],
  visited: new Set(),
  flags: { radioUsed: false, droneArrived: false, dvdInserted: false },
  log: [],
  gameOver: false,
};

function out(line, cls) {
  state.log.push({ line, cls: cls || "" });
  if (state.log.length > 200) state.log.shift();
}

function look() {
  const r = ROOMS[state.room];
  state.visited.add(state.room);
  if (r.dark && !state.inv.includes("flashlight")) {
    out("It is pitch black. You can't see a thing.", "bbs-bright");
    out("If you keep moving you may stumble into a grue.", "bbs-dim");
    return;
  }
  out("");
  out("─ " + r.name + " ─", "bbs-bright");
  out(r.desc);
  if (r.items && r.items.length) {
    out("You can see: " + r.items.map(i => i.toUpperCase()).join(", "), "bbs-dim");
  }
}

function move(dir) {
  const r = ROOMS[state.room];
  if (r.lockedExit && r.lockedExit.dir === dir && !state.inv.includes(r.lockedExit.needs)) {
    out(r.lockedExit.message, "bbs-bright");
    return;
  }
  const dest = r.exits[dir];
  if (!dest) { out("You can't go that way.", "bbs-dim"); return; }
  state.room = dest;
  look();
  // Drone special case: reaching exitNode without dvd = stuck
  if (dest === "exitNode" && !state.inv.includes("dvd")) {
    out("The terminal blinks impatiently. You need the LAST CLEAN DATASET.", "bbs-bright");
  }
}

function take(itemId) {
  const r = ROOMS[state.room];
  const idx = (r.items || []).indexOf(itemId);
  if (idx < 0) { out("There's no " + itemId.toUpperCase() + " here.", "bbs-dim"); return; }
  r.items.splice(idx, 1);
  state.inv.push(itemId);
  out("Taken: " + itemId.toUpperCase(), "bbs-bright");
}

function drop(itemId) {
  const idx = state.inv.indexOf(itemId);
  if (idx < 0) { out("You're not carrying that.", "bbs-dim"); return; }
  state.inv.splice(idx, 1);
  ROOMS[state.room].items.push(itemId);
  out("Dropped: " + itemId.toUpperCase(), "bbs-dim");
}

function use(itemId) {
  if (!state.inv.includes(itemId)) { out("You don't have a " + itemId.toUpperCase() + ".", "bbs-dim"); return; }
  if (itemId === "radio" && state.room === "rooftop" && !state.flags.radioUsed) {
    state.flags.radioUsed = true;
    out("You broadcast a distress call on 144.39 MHz. Static, then a faint reply: 'rescue drone inbound, ETA 90 seconds. dock at exit node.'", "bbs-bright");
    setTimeout(() => {
      state.flags.droneArrived = true;
      ROOMS.rooftop.exits.fly = "drone";
      out("");
      out("A QUADCOPTER thrums down out of the smog and hovers at the rooftop edge. You can now FLY to it.", "bbs-bright");
      render();
    }, 4000);
    return;
  }
  if (itemId === "dvd" && state.room === "exitNode") {
    state.flags.dvdInserted = true;
    state.gameOver = true;
    out("");
    out("You insert the golden DVD-R. The terminal whirrs, validates, then beams the dataset upward through the satellite dish.", "bbs-bright");
    out("");
    out("On the horizon, the GRAY GOO recoils. A new model — one trained on real human writing — boots up.", "bbs-bright");
    out("");
    out("★ YOU WIN ★  The web survives. For now.", "bbs-bright");
    out("");
    out("Press ESC to return.", "bbs-dim");
    return;
  }
  if (itemId === "flashlight") {
    out("Click. The beam sweeps the room. Useful in dark places.", "bbs-dim");
    return;
  }
  out("Nothing obvious happens.", "bbs-dim");
}

function inventory() {
  if (!state.inv.length) { out("You are empty-handed.", "bbs-dim"); return; }
  out("Inventory:", "bbs-bright");
  state.inv.forEach(i => out("  - " + ITEMS[i]));
}

function examine(itemId) {
  if (state.inv.includes(itemId) || (ROOMS[state.room].items || []).includes(itemId)) {
    out(ITEMS[itemId] || "Nothing special about it.");
  } else {
    out("You don't see that here.", "bbs-dim");
  }
}

function help() {
  out("Commands:", "bbs-bright");
  out("  GO <dir>  /  N S E W U D  /  ENTER <dir>");
  out("  LOOK  /  L");
  out("  TAKE <item>  /  GET <item>");
  out("  DROP <item>");
  out("  USE <item>  (e.g. USE RADIO on the rooftop, USE DVD at exit node)");
  out("  EXAMINE <item>  /  X <item>");
  out("  INVENTORY  /  I");
  out("  HELP  /  ?");
  out("  ESC: back to door games");
}

// ─── Command parsing ────────────────────────────────────
const DIRS = {
  n: "north", s: "south", e: "east", w: "west", u: "up", d: "down",
  north: "north", south: "south", east: "east", west: "west",
  up: "up", down: "down", door: "door", secret: "secret",
  fly: "fly", dock: "dock", in: "secret", out: "secret",
};

function parse(input) {
  const raw = input.trim().toLowerCase();
  if (!raw) return;
  out("> " + input, "bbs-dim");
  const parts = raw.split(/\s+/);
  const verb = parts[0];
  const arg = parts.slice(1).join("-");

  if (DIRS[verb] && parts.length === 1) { move(DIRS[verb]); return; }
  if ((verb === "go" || verb === "enter" || verb === "walk") && parts[1]) {
    const d = DIRS[parts[1]] || parts[1];
    move(d); return;
  }
  if (verb === "look" || verb === "l") { look(); return; }
  if (verb === "take" || verb === "get" || verb === "grab") { if (arg) take(arg); else out("Take what?"); return; }
  if (verb === "drop") { if (arg) drop(arg); else out("Drop what?"); return; }
  if (verb === "use" || verb === "insert" || verb === "broadcast") { if (arg) use(arg); else out("Use what?"); return; }
  if (verb === "examine" || verb === "x" || verb === "inspect") { if (arg) examine(arg); else out("Examine what?"); return; }
  if (verb === "inventory" || verb === "i" || verb === "inv") { inventory(); return; }
  if (verb === "help" || verb === "?") { help(); return; }
  if (verb === "quit" || verb === "exit") { onNavigate("/doors"); return; }
  out("I don't understand. Try HELP.", "bbs-dim");
}

let inputBuf = "";
let questScrollEl = null;
let stickToBottom = true;
function render() {
  // Render the full log inside a scrollable pane. Stick to bottom unless
  // the user has scrolled up to read history.
  const lines = state.log.map(l => `<div class="bbs-row ${l.cls}">${escapeHtml(l.line)}</div>`).join("");
  mountEl.innerHTML = `<div class="bbs-screen">
<div class="bbs-header">AIGREGATOR QUEST</div>
<div id="quest-log" class="bbs-scroll-pane">${lines}</div>
<div class="bbs-row">────────────────────────────────────────────</div>
<div class="bbs-row">&gt; <span class="bbs-bright">${escapeHtml(inputBuf)}</span><span class="bbs-cursor"></span></div>
<div class="bbs-row bbs-dim">type commands  ·  ENTER submit  ·  ↑/↓ PgUp/PgDn scroll  ·  ESC back</div>
</div>`;
  questScrollEl = mountEl.querySelector("#quest-log");
  if (questScrollEl && stickToBottom) {
    questScrollEl.scrollTop = questScrollEl.scrollHeight;
  }
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function keyHandler(e) {
  if (e.key === "Escape") { onNavigate("/doors"); return true; }
  // Scroll keys for log history.
  if (questScrollEl) {
    const pane = questScrollEl;
    const scrollBy = (px) => {
      pane.scrollTop += px;
      // If user scrolled up, stop auto-sticking to bottom.
      stickToBottom = (pane.scrollTop + pane.clientHeight >= pane.scrollHeight - 4);
    };
    const lineH = 28;
    if (e.key === "ArrowUp")   { e.preventDefault(); scrollBy(-lineH * 2); return true; }
    if (e.key === "ArrowDown") { e.preventDefault(); scrollBy(lineH * 2);  return true; }
    if (e.key === "PageUp")    { e.preventDefault(); scrollBy(-pane.clientHeight); return true; }
    if (e.key === "PageDown")  { e.preventDefault(); scrollBy(pane.clientHeight);  return true; }
    if (e.key === "Home")      { e.preventDefault(); pane.scrollTop = 0; stickToBottom = false; return true; }
    if (e.key === "End")       { e.preventDefault(); pane.scrollTop = pane.scrollHeight; stickToBottom = true; return true; }
  }
  if (state.gameOver) return true;
  if (e.key === "Enter") {
    e.preventDefault();
    parse(inputBuf);
    inputBuf = "";
    render();
    return true;
  }
  if (e.key === "Backspace") {
    e.preventDefault();
    inputBuf = inputBuf.slice(0, -1);
    render();
    return true;
  }
  if (e.key.length === 1 && !e.ctrlKey && !e.metaKey && !e.altKey) {
    e.preventDefault();
    inputBuf += e.key;
    render();
    return true;
  }
  return true;
}

function intro() {
  out("");
  out("AIGREGATOR QUEST — v1.0", "bbs-bright");
  out("");
  out("You wake on the lobby floor with no memory of how you got here. The building hums with the resonance of a million matrix multiplications. Outside, the news scrolls past: MODEL COLLAPSE IMMINENT. THE GRAY GOO ADVANCES.", "");
  out("");
  out("Find the COLD STORAGE VAULT. Recover the LAST CLEAN DATASET. Escape via the EXIT NODE before the synthetic data swallows everything.", "");
  out("");
  out("Type HELP for commands.", "bbs-dim");
  look();
}

export function start(mount, ctx, navigate) {
  mountEl = mount;
  onNavigate = navigate;
  // Reset state on each entry.
  Object.keys(state).forEach(k => {
    if (k === "log") state.log = [];
    else if (k === "inv") state.inv = [];
    else if (k === "visited") state.visited = new Set();
    else if (k === "flags") state.flags = { radioUsed: false, droneArrived: false, dvdInserted: false };
    else if (k === "room") state.room = "lobby";
    else if (k === "gameOver") state.gameOver = false;
  });
  inputBuf = "";
  // Refresh room items to defaults (since they mutate)
  // Re-add items that may have been taken in a prior playthrough:
  ROOMS.lobby.items = ["badge"];
  ROOMS.parking.items = ["protein-bar"];
  ROOMS.engineering.items = ["laptop"];
  ROOMS.coffee.items = ["mug"];
  ROOMS.racks.items = ["keycard"];
  ROOMS.cooling.items = ["usb-stick"];
  ROOMS.training.items = ["loss-curve-printout"];
  ROOMS.inference.items = ["logbook"];
  ROOMS.library.items = ["dataset-shard"];
  ROOMS.lab.items = ["paper"];
  ROOMS.rooftop.items = ["radio"];
  ROOMS.vault.items = ["dvd"];
  ROOMS.closet.items = ["flashlight"];
  delete ROOMS.rooftop.exits.fly;
  intro();
  render();
  return { keyHandler };
}
