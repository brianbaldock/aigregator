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
  { west: "datacenter" }, ["dataset-shard"],
  {
    gatekeeper: { item: "dataset-shard", needsFlag: "librarianPlacated",
                  blockMessage: "The librarian-bot lunges and snatches the SHARD back. 'CITE. YOUR. SOURCES,' it hisses. Try SHOW PAPER to prove your credentials." },
    altDesc: { flag: "librarianPlacated",
               desc: "Petabytes of training corpora on tape. The librarian-bot stands politely beside an unguarded pedestal, occasionally nodding to itself. WEST: datacenter." }
  });
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
addItem("laptop",              "LAPTOP — sticker-covered, 2% battery, fan dead. Could boot if it had real power and the right drive.");
addItem("mug",                 "MUG — reads 'KEEP CALM AND TRAIN ON'.");
addItem("keycard",             "KEYCARD — magstripe + RFID. Reads 'COLD STORAGE: AUTHORIZED'.");
addItem("usb-stick",           "USB STICK — labeled in Sharpie: 'WEIGHTS — DO NOT LOSE'. Bootable.");
addItem("loss-curve-printout", "PRINTOUT — a flatlined training curve, 47 days of nothing.");
addItem("logbook",             "LOGBOOK — last entry: 'rolling back. we trained on our own outputs.'");
addItem("dataset-shard",       "TAPE SHARD — Common Crawl, 2019. Heavy.");
addItem("paper",               "PAPER — 'Attention Is All You Need' (printed, dog-eared). A scholar-bot might respect this.");
addItem("flashlight",          "FLASHLIGHT — heavy, D-cells, works.");
addItem("radio",               "HAM RADIO — could broadcast a distress call.");
addItem("dvd",                 "GOLDEN DVD-R — THE LAST CLEAN DATASET. Pre-2022 internet. Don't drop it.");

const state = {
  room: "lobby",
  inv: [],
  visited: new Set(),
  flags: { radioUsed: false, droneArrived: false, dvdInserted: false, librarianPlacated: false, laptopBooted: false },
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
  // If an altDesc is registered for this room and its flag is set, use that instead.
  const desc = (r.altDesc && state.flags[r.altDesc.flag]) ? r.altDesc.desc : r.desc;
  out(desc);
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
  // Gatekeeper check — a room can block taking a specific item until a flag flips.
  if (r.gatekeeper && r.gatekeeper.item === itemId && !state.flags[r.gatekeeper.needsFlag]) {
    out(r.gatekeeper.blockMessage, "bbs-bright");
    return;
  }
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
    winSequence();
    return;
  }
  if (itemId === "flashlight") {
    out("Click. The beam sweeps the room. Useful in dark places.", "bbs-dim");
    return;
  }
  if ((itemId === "keycard" || itemId === "card") && state.room === "datacenter") {
    openOrSwipe(itemId);
    return;
  }
  if (itemId === "badge" && state.room === "datacenter") {
    out("You wave the BADGE at the reader. It's a dumb employee ID — no auth chip. You need a KEYCARD.", "bbs-dim");
    return;
  }
  if (itemId === "laptop") {
    out("2% battery and the fan is dead. It boots to a BIOS screen, then dies.", "bbs-dim");
    return;
  }
  if (itemId === "protein-bar" || itemId === "bar") {
    out("Chalky but edible. You feel marginally less doomed.", "bbs-dim");
    return;
  }
  if (itemId === "mug") {
    out("Empty. The grinder still says 'beans require root access'.", "bbs-dim");
    return;
  }
  out("Nothing obvious happens.", "bbs-dim");
}

// Open / unlock / swipe — designed for the COLD STORAGE door from the datacenter,
// but generic enough for any future locked exits.
function openOrSwipe(target) {
  const r = ROOMS[state.room];
  if (r.lockedExit) {
    if (state.inv.includes(r.lockedExit.needs)) {
      out("You swipe the " + r.lockedExit.needs.toUpperCase() + ". The reader chirps green. The door slides open.", "bbs-bright");
      move(r.lockedExit.dir);
      return;
    }
    out(r.lockedExit.message, "bbs-bright");
    return;
  }
  if (target === "keycard" || target === "card" || target === "badge") {
    out("There's nothing here to swipe it on.", "bbs-dim");
    return;
  }
  if (target === "door" || !target) {
    out("There's no locked door here. Try GO <direction>.", "bbs-dim");
    return;
  }
  out("Nothing here works that way.", "bbs-dim");
}

// SHOW item — present an inventory item to whoever's in the room.
// Currently the librarian-bot in the library cares about the seminal paper.
function show(itemId) {
  if (!state.inv.includes(itemId)) { out("You don't have a " + itemId.toUpperCase() + ".", "bbs-dim"); return; }
  if (state.room === "library" && itemId === "paper") {
    if (state.flags.librarianPlacated) {
      out("The librarian-bot has already seen the PAPER. It nods at you again, satisfied.", "bbs-dim");
      return;
    }
    state.flags.librarianPlacated = true;
    out("You hold up the PAPER. The librarian-bot freezes mid-rock, scans the title, and emits a long contented buzzing noise.", "bbs-bright");
    out("'Properly cited,' it murmurs. 'Properly cited.' It shuffles aside.", "bbs-bright");
    return;
  }
  if (state.room === "library") {
    out("The librarian-bot glances, unimpressed. 'CITE. YOUR. SOURCES.'", "bbs-dim");
    return;
  }
  out("There's nobody here to show that to.", "bbs-dim");
}

// COMBINE / USE X ON Y — two-object verb. Currently only the laptop+USB pairing matters,
// and only at the SERVER RACKS (the one room with real power coming off the dark
// INFERENCE-PRIMARY rack you can siphon from).
function combine(a, b) {
  if (!a || !b) { out("Combine what with what?", "bbs-dim"); return; }
  // Special case: USE KEYCARD ON DOOR (or similar) — route to door opener.
  if ((b === "door" || a === "door") && state.inv.includes(a === "door" ? b : a)) {
    openOrSwipe(a === "door" ? b : a);
    return;
  }
  if (!state.inv.includes(a)) { out("You don't have a " + a.toUpperCase() + ".", "bbs-dim"); return; }
  if (!state.inv.includes(b)) { out("You don't have a " + b.toUpperCase() + ".", "bbs-dim"); return; }
  // Normalize order — laptop is always the host, USB is always the payload.
  const set = new Set([a, b]);
  if (set.has("laptop") && set.has("usb-stick")) {
    if (state.flags.laptopBooted) {
      out("The laptop is already running the local model. It blinks patiently.", "bbs-dim");
      return;
    }
    if (state.room !== "racks") {
      out("You jam the USB into the laptop. It chirps, then dies — 2% battery isn't enough. You need real power.", "bbs-dim");
      return;
    }
    state.flags.laptopBooted = true;
    out("You jack the LAPTOP into the dark INFERENCE-PRIMARY rack and slot the USB STICK.", "bbs-bright");
    out("The fan stutters. The screen flickers. A tiny local model boots from the WEIGHTS and prints:", "bbs-bright");
    out("");
    out("  > scanning facility...", "bbs-dim");
    out("  > primary corpus: COLD STORAGE VAULT (auth required)", "bbs-dim");
    out("  > librarian-bot: PLACATE WITH SEMINAL PAPER", "bbs-dim");
    out("  > frozen tech: CARRIES BACKUP WEIGHTS (already in your hand)", "bbs-dim");
    out("  > exit node: RANKS RUN BY ARTIFACTS CARRIED — bring everything you can", "bbs-dim");
    out("");
    out("The screen dies. You pocket the laptop. The hint stays with you.", "bbs-bright");
    return;
  }
  out("Nothing happens. Those two don't fit together.", "bbs-dim");
}

// Multi-ending win sequence — branches on what you carried to the exit node.
function winSequence() {
  const inv = new Set(state.inv);
  // Note: dvd is already in inv at this point (use() doesn't remove it).
  const hasPaper = inv.has("paper");
  const hasShard = inv.has("dataset-shard");
  const hasUsb   = inv.has("usb-stick");
  const hasLogbook = inv.has("logbook");
  const hasPrintout = inv.has("loss-curve-printout");
  // Count "scholarly" extras for the completionist tier.
  const extras = [hasPaper, hasShard, hasUsb, hasLogbook, hasPrintout].filter(Boolean).length;

  out("");
  out("You insert the golden DVD-R. The terminal whirrs, validates, then beams the dataset upward through the satellite dish.", "bbs-bright");
  out("");

  if (extras >= 4) {
    // COMPLETIONIST ending — carried the corpus, the math, the logs, and the backup.
    out("On the horizon, the GRAY GOO recoils. A new model — trained on real human writing, validated against your TAPE SHARD, anchored to the methodology in the PAPER, sanity-checked against your LOGBOOK — boots up clean. The USB WEIGHTS load as a fallback in case anything drifts.", "bbs-bright");
    out("", "");
    out("★★★ COMPLETIONIST ENDING ★★★", "bbs-bright");
    out("The web doesn't just survive. It remembers how it got here.", "bbs-bright");
  } else if (hasPaper && hasShard) {
    // GREAT ending — preserved methodology AND a slice of the old corpus.
    out("On the horizon, the GRAY GOO recoils. A new model — one trained on real human writing — boots up, with the PAPER's methodology baked in and the TAPE SHARD seeding a clean validation set.", "bbs-bright");
    out("", "");
    out("★★ GREAT ENDING ★★", "bbs-bright");
    out("The web survives — and so does the math that built it.", "bbs-bright");
  } else if (hasPaper) {
    // BONUS ending — preserved at least the methodology.
    out("On the horizon, the GRAY GOO recoils. A new model — one trained on real human writing, with 'Attention Is All You Need' set as required reading — boots up.", "bbs-bright");
    out("", "");
    out("★★ BONUS ENDING ★★", "bbs-bright");
    out("The web survives, and someone, somewhere, remembers how it actually worked.", "bbs-bright");
  } else {
    // STANDARD ending — original win text.
    out("On the horizon, the GRAY GOO recoils. A new model — one trained on real human writing — boots up.", "bbs-bright");
    out("", "");
    out("★ YOU WIN ★  The web survives. For now.", "bbs-bright");
    if (extras === 0) {
      out("");
      out("(You left a lot of useful artifacts behind. Try carrying more next run.)", "bbs-dim");
    } else {
      out("");
      out("(Hint: the PAPER changes the ending. So do other artifacts you picked up.)", "bbs-dim");
    }
  }
  out("");
  out("Press ESC to return.", "bbs-dim");
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
  out("  Move:   GO / WALK / RUN <dir>   |   N S E W U D   |   CLIMB UP   DESCEND");
  out("  Look:   LOOK / L                 |   EXAMINE / READ / LOOK AT <item>");
  out("  Items:  TAKE / GET / PICK UP <item>   |   DROP / PUT DOWN <item>   |   INVENTORY / I");
  out("  Act:    USE <item>   |   OPEN / UNLOCK / SWIPE <door|card>   |   TURN ON <item>");
  out("  Talk:   SHOW <item>  (present an item to someone in the room)");
  out("  Pair:   USE <a> ON <b>   |   INSERT <a> INTO <b>   |   COMBINE <a> AND <b>");
  out("  Misc:   HELP / ?     |   QUIT     |   ESC: back to door games");
  out("");
  out("Tip: locked door? OPEN DOOR or SWIPE KEYCARD.", "bbs-dim");
  out("Tip: someone in your way? Try SHOW <thing they'd want>.", "bbs-dim");
  out("Tip: dead electronics? Find a room with power and COMBINE them with whatever boots.", "bbs-dim");
  out("Tip: the ending depends on what you carry to the EXIT NODE. Explore.", "bbs-dim");
}

// ─── Command parsing ────────────────────────────────────
const DIRS = {
  n: "north", s: "south", e: "east", w: "west", u: "up", d: "down",
  north: "north", south: "south", east: "east", west: "west",
  up: "up", down: "down", door: "door", secret: "secret",
  fly: "fly", dock: "dock", in: "secret", out: "secret",
};

// Verb synonyms — accept many ways to say the same thing.
const VERBS = {
  move:    new Set(["go","enter","walk","run","head","move","travel","proceed"]),
  take:    new Set(["take","get","grab","pickup","snag","pocket","collect","grab-it"]),
  drop:    new Set(["drop","discard"]),
  use:     new Set(["use","insert","broadcast","activate","operate","apply","press","push","plug"]),
  examine: new Set(["examine","x","inspect","read","study","check","peruse"]),
  inv:     new Set(["inventory","i","inv","items","carrying","gear","stuff"]),
  help:    new Set(["help","?","h","commands","hint"]),
  quit:    new Set(["quit","q","bye","abandon"]),
  open:    new Set(["open","unlock","swipe","tap","wave","scan","badge"]),
  climb:   new Set(["climb","ascend"]),  // bare = up; with arg, uses arg
  descend: new Set(["descend"]),          // bare = down
  look:    new Set(["look","l"]),
  show:    new Set(["show","present","offer","give","display","prove"]),
  combine: new Set(["combine","attach","connect","pair","join"]),
};

// Item synonyms — common shortenings + casual names → canonical item IDs.
// Lets "use card", "examine printout", "take dvd-r" all work as expected.
const ITEM_ALIASES = {
  "card": "keycard", "key": "keycard", "key-card": "keycard",
  "id": "badge", "employee-badge": "badge",
  "bar": "protein-bar", "snack": "protein-bar",
  "usb": "usb-stick", "stick": "usb-stick", "thumbdrive": "usb-stick", "drive": "usb-stick",
  "printout": "loss-curve-printout", "curve": "loss-curve-printout", "graph": "loss-curve-printout",
  "log": "logbook", "book": "logbook",
  "tape": "dataset-shard", "shard": "dataset-shard",
  "torch": "flashlight", "light": "flashlight", "lamp": "flashlight",
  "ham": "radio", "ham-radio": "radio",
  "dvd-r": "dvd", "disc": "dvd", "disk": "dvd", "dataset": "dvd",
  "computer": "laptop",
  "cup": "mug", "coffee": "mug",
  "paper": "paper", "attention": "paper",
};

function resolveItem(name) {
  return ITEM_ALIASES[name] || name;
}

// Split arg tokens around a connector word (on / onto / into / in / with / and / to)
// and return [leftItem, rightItem] if both halves are non-empty. Otherwise null.
const PAIR_CONNECTORS = new Set(["on","onto","into","in","with","and","to"]);
function splitPair(argParts) {
  if (!argParts || argParts.length < 3) return null;
  for (let i = 1; i < argParts.length - 1; i++) {
    if (PAIR_CONNECTORS.has(argParts[i])) {
      const left = argParts.slice(0, i).join("-");
      const right = argParts.slice(i + 1).join("-");
      if (left && right) return [left, right];
    }
  }
  return null;
}

function parse(input) {
  const raw = input.trim().toLowerCase();
  if (!raw) return;
  out("> " + input, "bbs-dim");
  const parts = raw.split(/\s+/);
  let verb = parts[0];
  let argParts = parts.slice(1);

  // Multi-word verb glue — rewrite into canonical single-verb form.
  //   "pick up X"   → take X
  //   "put down X"  → drop X
  //   "look at X"   → examine X (vs bare "look" which describes the room)
  //   "look in X"   → examine X
  //   "turn on X"   → use X
  //   "turn off X"  → use X
  //   "plug in X"   → use X
  if (verb === "pick" && argParts[0] === "up") { verb = "take"; argParts.shift(); }
  else if (verb === "put"  && argParts[0] === "down") { verb = "drop"; argParts.shift(); }
  else if (verb === "look" && (argParts[0] === "at" || argParts[0] === "in")) { verb = "examine"; argParts.shift(); }
  else if (verb === "turn" && (argParts[0] === "on" || argParts[0] === "off")) { verb = "use"; argParts.shift(); }
  else if (verb === "plug" && argParts[0] === "in") { verb = "use"; argParts.shift(); }

  // Bare "exit" with no noun = leave the game (matches old behavior).
  // With a noun ("exit room") fall through to movement attempt.
  if (verb === "exit" && argParts.length === 0) { onNavigate("/doors"); return; }

  const arg = argParts.join("-");

  // Bare-word direction: "n", "north", "door", "fly", etc.
  if (DIRS[verb] && argParts.length === 0) { move(DIRS[verb]); return; }

  // Movement verbs with a direction argument: "go north", "walk door".
  if (VERBS.move.has(verb) && argParts.length > 0) {
    const d = DIRS[argParts[0]] || argParts[0];
    move(d); return;
  }
  // CLIMB / ASCEND default UP, DESCEND defaults DOWN; both accept explicit dirs.
  if (VERBS.climb.has(verb)) {
    const d = argParts[0] ? (DIRS[argParts[0]] || argParts[0]) : "up";
    move(d); return;
  }
  if (VERBS.descend.has(verb)) {
    const d = argParts[0] ? (DIRS[argParts[0]] || argParts[0]) : "down";
    move(d); return;
  }

  // Open / unlock / swipe — primarily for locked doors.
  if (VERBS.open.has(verb)) { openOrSwipe(resolveItem(arg)); return; }

  // SHOW <item> — present to whoever's in the room.
  if (VERBS.show.has(verb)) { if (arg) show(resolveItem(arg)); else out("Show what?"); return; }

  // Two-object verbs: USE X ON Y, INSERT X INTO Y, PLUG X INTO Y, COMBINE X AND Y.
  // We re-split argParts on the connector words (on / onto / into / with / and / to).
  // If found, route to combine(). Otherwise fall through to single-object USE.
  if (VERBS.use.has(verb) || VERBS.combine.has(verb)) {
    const pair = splitPair(argParts);
    if (pair) {
      combine(resolveItem(pair[0]), resolveItem(pair[1]));
      return;
    }
    if (VERBS.combine.has(verb)) {
      // COMBINE without a pair — be helpful.
      if (arg) out("Combine " + arg.toUpperCase() + " with what? Try COMBINE A AND B.", "bbs-dim");
      else out("Combine what with what?", "bbs-dim");
      return;
    }
    // Falls through to single-object USE below.
  }

  if (VERBS.look.has(verb) && argParts.length === 0) { look(); return; }
  if (VERBS.take.has(verb))    { if (arg) take(resolveItem(arg));    else out("Take what?"); return; }
  if (VERBS.drop.has(verb))    { if (arg) drop(resolveItem(arg));    else out("Drop what?"); return; }
  if (VERBS.use.has(verb))     { if (arg) use(resolveItem(arg));     else out("Use what?"); return; }
  if (VERBS.examine.has(verb)) { if (arg) examine(resolveItem(arg)); else out("Examine what?"); return; }
  if (VERBS.inv.has(verb))     { inventory(); return; }
  if (VERBS.help.has(verb))    { help(); return; }
  if (VERBS.quit.has(verb))    { onNavigate("/doors"); return; }

  // "leave" / "place" — drop synonyms only when there's an item argument.
  if ((verb === "leave" || verb === "place") && arg) { drop(resolveItem(arg)); return; }

  out("I don't understand. Try HELP.", "bbs-dim");
}

let inputBuf = "";
function render() {
  // Render the full log directly — no inner scroll pane. Overflow falls
  // to #bbs-root which the global scroll handler in main.js drives.
  const lines = state.log.map(l => `<div class="bbs-row ${l.cls}">${escapeHtml(l.line)}</div>`).join("");
  mountEl.innerHTML = `<div class="bbs-screen">
<div class="bbs-header">AIGREGATOR QUEST</div>
${lines}
<div class="bbs-row">────────────────────────────────────────────</div>
<div class="bbs-row">&gt; <span class="bbs-bright">${escapeHtml(inputBuf)}</span><span class="bbs-cursor"></span></div>
<div class="bbs-row bbs-dim">type commands  ·  ENTER submit  ·  ↑/↓ PgUp/PgDn scroll  ·  ESC back</div>
</div>`;
  // Auto-scroll viewport to bottom so the latest line + prompt are visible.
  const root = document.getElementById("bbs-root");
  if (root) root.scrollTop = root.scrollHeight;
}

function escapeHtml(s) {
  return String(s).replace(/[&<>"']/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;"}[c]));
}

function keyHandler(e) {
  if (e.key === "Escape") { onNavigate("/doors"); return true; }
  // Scroll keys fall through to the global #bbs-root scroller in main.js.
  if (e.key === "ArrowUp" || e.key === "ArrowDown" ||
      e.key === "PageUp"  || e.key === "PageDown"  ||
      e.key === "Home"    || e.key === "End") {
    return false;
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
    else if (k === "flags") state.flags = { radioUsed: false, droneArrived: false, dvdInserted: false, librarianPlacated: false, laptopBooted: false };
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
