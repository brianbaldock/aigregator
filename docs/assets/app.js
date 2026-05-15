/* ═══════════════════════════════════════════════════════════
   AIGREGATOR theme switcher + terminal mode
   ═══════════════════════════════════════════════════════════ */
(function () {
  "use strict";

  const THEMES = ["phosphor", "light", "geocities", "terminal"];
  const STORAGE_KEY = "aigregator_theme";

  function applyTheme(theme) {
    if (!THEMES.includes(theme)) theme = "phosphor";
    document.body.setAttribute("data-theme", theme);
    localStorage.setItem(STORAGE_KEY, theme);
    const sel = document.getElementById("theme-select");
    if (sel) sel.value = theme;
    if (theme === "terminal") initTerminal();
    else destroyTerminal();
  }

  function buildSwitcher() {
    const nav = document.querySelector("nav.menu");
    if (!nav) return;
    const span = document.createElement("span");
    span.className = "theme-switch";
    span.innerHTML = `<label for="theme-select" style="margin-right:6px;color:var(--green-dim);font-size:0.85em;">theme:</label><select id="theme-select">
      <option value="phosphor">phosphor</option>
      <option value="light">light</option>
      <option value="geocities">geocities</option>
      <option value="terminal">terminal</option>
    </select>`;
    nav.appendChild(span);
    span.querySelector("select").addEventListener("change", e => applyTheme(e.target.value));
  }

  // ─── DIGEST EXTRACTION ───────────────────────────────────
  // Read the rendered HTML article to build a section/item map for the terminal.
  let DIGEST = null;

  function parseDigest() {
    if (DIGEST) return DIGEST;
    const article = document.querySelector("article.digest");
    if (!article) return { sections: [], date: "unknown", subtitle: "", dashboard: "" };

    const h1 = article.querySelector("h1");
    const date = h1 ? h1.textContent.trim() : "";
    const subtitleP = h1 ? h1.nextElementSibling : null;
    const subtitle = subtitleP && subtitleP.tagName === "P" ? subtitleP.textContent.trim() : "";

    // Dashboard blockquote (first one)
    const dash = article.querySelector("blockquote");
    const dashboard = dash ? dash.innerText.trim() : "";

    // Walk sections (h2 followed by stats + ul/ol)
    const sections = [];
    let cur = null;
    for (const el of article.children) {
      if (el.tagName === "H2") {
        if (cur) sections.push(cur);
        const title = el.textContent.trim();
        const slug = title.toLowerCase()
          .replace(/[^a-z0-9]+/g, "-")
          .replace(/^-+|-+$/g, "")
          .replace(/^[0-9]+-/, ""); // strip leading digit from emoji-prefixed slugs
        cur = { title, slug, stats: "", items: [] };
      } else if (cur && el.tagName === "P" && el.querySelector("em")) {
        cur.stats = el.textContent.trim();
      } else if (cur && (el.tagName === "UL" || el.tagName === "OL")) {
        for (const li of el.children) {
          if (li.tagName !== "LI") continue;
          const text = li.textContent.trim().replace(/\s+/g, " ");
          const links = Array.from(li.querySelectorAll("a")).map(a => ({
            text: a.textContent.trim(),
            href: a.href,
          }));
          // Try to extract title (first <strong>) and the rest as body
          const strong = li.querySelector("strong");
          const title = strong ? strong.textContent.trim() : text.slice(0, 80);
          cur.items.push({ raw: text, title, links });
        }
      }
    }
    if (cur) sections.push(cur);

    DIGEST = { date, subtitle, dashboard, sections };
    return DIGEST;
  }

  // ─── TERMINAL ────────────────────────────────────────────
  let termEl = null;
  let outEl = null;
  let inputEl = null;
  let history = [];
  let histIdx = 0;
  let cwd = "/"; // "/" or "/<section-slug>"

  const BOOT = [
    "AIGREGATOR v1.0.0 [BIOS 0xAFC0]",
    "Phosphor BIOS (C) 1996 daily-signal corp.",
    "",
    "Memory test: 65535K OK",
    "Initialising news subsystem.....OK",
    "Loading lab feeds.............[OK]",
    "Loading social signal.........[OK]",
    "Polymarket uplink.............[OK]",
    "Kagi enrichment...............[OK]",
    "",
    "boot complete. type `help` for commands. type `man digest` for the manual.",
    "",
  ];

  const MAN_DIGEST = [
    "AIGREGATOR(1)                 USER COMMANDS                AIGREGATOR(1)",
    "",
    "NAME",
    "  aigregator -- daily AI news digest, scored and cited.",
    "",
    "FILESYSTEM",
    "  Each section of today's digest is exposed as a directory under /.",
    "  Each story is a numbered 'file' inside its section.",
    "  Navigate with `cd <section>` and inspect a story with `cat <N>`.",
    "  Open the primary source in a new tab with `open <N>`.",
    "",
    "COMMANDS",
    "  help, ?            this list",
    "  man <topic>        manual (try: man digest, man scoring, man easter)",
    "  ls [-l]            list current directory contents",
    "  cd <dir>           change directory (cd .. or cd / to go up)",
    "  pwd                print working directory",
    "  cat <N>            print story N (in current section)",
    "  open <N>           open story N's primary link in a new tab",
    "  dash               show today's dashboard",
    "  themes             show theme switcher (also: theme <name>)",
    "  archive            list past digests",
    "  date, whoami       flavor",
    "  clear              clear screen",
    "  exit               return to the regular site",
    "",
    "SEE ALSO",
    "  man scoring, man easter",
    "",
  ];

  const MAN_SCORING = [
    "SCORING(7)",
    "",
    "  Each story carries a credibility score 1..8.",
    "    base       1..5 from highest-credibility source",
    "    bonus      +1 per independent corroborating source, max +3",
    "",
    "  Per-item flags:",
    "    🔥  cross-source (corroboration >= +2)",
    "    🌱  open source / non-frontier-lab",
    "    🛡️  responsible AI / safety / policy",
    "    🎨  cool indie project / novel application",
    "",
    "  Per-item sentiment dot:  🟢 positive   🟡 neutral   🔴 negative",
    "  Source count:            ▤×N",
    "",
    "  Dashboard mean is credibility-weighted across all news items.",
    "",
  ];

  const MAN_EASTER = [
    "EASTER(7)",
    "",
    "  somewhere in this terminal is a `sudo` joke, a `coffee` machine,",
    "  a `hack` minigame, a `tree`, a wargames reference, and at least",
    "  one route to /dev/null. happy hunting.",
    "",
    "  hint: the `aigregator` binary itself is curious.",
    "",
  ];

  function createTerm() {
    if (termEl) return;
    termEl = document.createElement("div");
    termEl.id = "term";
    termEl.innerHTML = `
      <div id="term-desk"></div>
      <svg class="floppies" viewBox="0 0 130 110" xmlns="http://www.w3.org/2000/svg">
        <!-- pile of 3.5" floppies -->
        <g>
          <rect x="6"  y="78" width="118" height="22" rx="2" fill="#1a3a8a" stroke="#0a1a3a" stroke-width="1"/>
          <rect x="62" y="80" width="48"  height="4"  fill="#cccccc"/>
          <rect x="84" y="83" width="14"  height="14" rx="1" fill="#888"/>
        </g>
        <g transform="translate(-4,-16)">
          <rect x="6"  y="78" width="118" height="22" rx="2" fill="#aa0a0a" stroke="#3a0606" stroke-width="1"/>
          <rect x="62" y="80" width="48"  height="4"  fill="#cccccc"/>
          <rect x="84" y="83" width="14"  height="14" rx="1" fill="#888"/>
        </g>
        <g transform="translate(8,-32)">
          <rect x="6"  y="78" width="118" height="22" rx="2" fill="#e8b830" stroke="#7a5a10" stroke-width="1"/>
          <rect x="62" y="80" width="48"  height="4"  fill="#cccccc"/>
          <rect x="84" y="83" width="14"  height="14" rx="1" fill="#888"/>
        </g>
        <g transform="translate(-2,-48)">
          <rect x="6"  y="78" width="118" height="22" rx="2" fill="#1a8a3a" stroke="#0a3a18" stroke-width="1"/>
          <rect x="62" y="80" width="48"  height="4"  fill="#cccccc"/>
          <rect x="84" y="83" width="14"  height="14" rx="1" fill="#888"/>
        </g>
        <g transform="translate(6,-64)">
          <rect x="6"  y="78" width="118" height="22" rx="2" fill="#1a1a1a" stroke="#000" stroke-width="1"/>
          <rect x="62" y="80" width="48"  height="4"  fill="#dddddd"/>
          <rect x="84" y="83" width="14"  height="14" rx="1" fill="#aaa"/>
        </g>
      </svg>
      <svg class="coffee" viewBox="0 0 90 120" xmlns="http://www.w3.org/2000/svg">
        <!-- ceramic mug -->
        <path d="M 14 36 L 14 100 Q 14 110 24 110 L 58 110 Q 68 110 68 100 L 68 36 Z"
              fill="#e8e2d4" stroke="#6a5a4a" stroke-width="1.5"/>
        <!-- coffee surface -->
        <ellipse cx="41" cy="38" rx="27" ry="5" fill="#3a1f0c"/>
        <ellipse cx="41" cy="37" rx="24" ry="3" fill="#5a2f12"/>
        <!-- handle -->
        <path d="M 68 50 Q 86 50 86 68 Q 86 86 68 86"
              fill="none" stroke="#6a5a4a" stroke-width="6" stroke-linecap="round"/>
        <path d="M 68 50 Q 86 50 86 68 Q 86 86 68 86"
              fill="none" stroke="#e8e2d4" stroke-width="3" stroke-linecap="round"/>
      </svg>
      <div class="steam"><span></span><span></span><span></span></div>
      <div id="term-scene">
        <div class="monitor">
          <div class="bezel">
            <div class="screen">
              <div id="term-output-wrap">
                <div id="term-output"></div>
                <div id="term-prompt-line">
                  <span id="term-prompt"></span>
                  <input id="term-input" autocomplete="off" autocapitalize="off" spellcheck="false" />
                </div>
              </div>
            </div>
          </div>
          <div class="powerbtn"></div>
          <div class="led"></div>
          <div class="nameplate">AIGREGATOR-1000</div>
        </div>
      </div>
    `;
    document.body.appendChild(termEl);
    outEl = document.getElementById("term-output");
    inputEl = document.getElementById("term-input");
    updatePrompt();

    inputEl.addEventListener("keydown", onKey);
    termEl.addEventListener("click", () => {
      if (inputEl && document.getElementById("term-scene").classList.contains("zoomed")) {
        inputEl.focus();
      }
    });
  }

  function destroyTerminal() {
    if (termEl) { termEl.remove(); termEl = null; outEl = null; inputEl = null; }
  }

  function initTerminal() {
    parseDigest();
    createTerm();
    outEl.innerHTML = "";
    // Brief beat to let the desk scene render, then trigger zoom
    const scene = document.getElementById("term-scene");
    setTimeout(() => {
      scene.classList.add("zoomed");
    }, 600);
    // Once zoom is roughly done, type the boot sequence
    setTimeout(() => {
      typeLines(BOOT, () => {
        inputEl.focus();
      });
    }, 2400);
  }

  function updatePrompt() {
    const p = document.getElementById("term-prompt");
    if (p) p.textContent = `user@aigregator:${cwd}$ `;
  }

  function print(line, cls) {
    const div = document.createElement("div");
    div.className = "term-line " + (cls || "");
    if (typeof line === "string") div.innerHTML = line;
    else div.appendChild(line);
    outEl.appendChild(div);
    outEl.scrollTop = outEl.scrollHeight;
  }

  function typeLines(lines, done, delay = 28) {
    let i = 0;
    function next() {
      if (i >= lines.length) { if (done) done(); return; }
      print(escapeHTML(lines[i]));
      i++;
      setTimeout(next, delay);
    }
    next();
  }

  function escapeHTML(s) {
    return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
  }

  // ─── COMMANDS ────────────────────────────────────────────
  function onKey(e) {
    if (e.key === "Enter") {
      e.preventDefault();
      const cmd = inputEl.value;
      print(`<span style="color:#ffb000">user@aigregator:${cwd}$</span> ${escapeHTML(cmd)}`);
      inputEl.value = "";
      if (cmd.trim()) {
        history.push(cmd);
        histIdx = history.length;
        runCommand(cmd.trim());
      }
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      if (histIdx > 0) { histIdx--; inputEl.value = history[histIdx]; }
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      if (histIdx < history.length - 1) { histIdx++; inputEl.value = history[histIdx]; }
      else { histIdx = history.length; inputEl.value = ""; }
    } else if (e.key === "Tab") {
      e.preventDefault();
      autocomplete();
    } else if (e.ctrlKey && e.key.toLowerCase() === "l") {
      e.preventDefault();
      outEl.innerHTML = "";
    }
  }

  function autocomplete() {
    const v = inputEl.value;
    const cmds = ["help", "man", "ls", "cd", "pwd", "cat", "open", "dash", "themes", "theme", "archive", "date", "whoami", "clear", "exit", "hack", "coffee", "tree", "sudo"];
    const matches = cmds.filter(c => c.startsWith(v));
    if (matches.length === 1) inputEl.value = matches[0] + " ";
    else if (matches.length > 1) print(matches.join("  "), "term-muted");
  }

  function runCommand(line) {
    const [cmd, ...args] = line.split(/\s+/);
    const arg = args.join(" ");
    switch (cmd) {
      case "help": case "?": print(MAN_DIGEST.slice(7, 22).join("\n"), "term-info"); break;
      case "man": doMan(arg); break;
      case "ls": doLs(args); break;
      case "cd": doCd(arg); break;
      case "pwd": print(cwd); break;
      case "cat": doCat(arg); break;
      case "open": doOpen(arg); break;
      case "dash": doDash(); break;
      case "theme": doTheme(arg); break;
      case "themes": print("available themes: phosphor, light, geocities, terminal. usage: theme <name>", "term-info"); break;
      case "archive": doArchive(); break;
      case "date": print(new Date().toString()); break;
      case "whoami": print("user@aigregator", "term-muted"); break;
      case "clear": outEl.innerHTML = ""; break;
      case "exit": applyTheme("phosphor"); break;
      // ── easter eggs ─────────────────────────────────────
      case "sudo": print("hermes is not in the sudoers file. this incident will be reported.", "term-err"); break;
      case "coffee": print("HTCPCP 418: i'm a teapot. ☕ but here, have some anyway.", "term-warn"); break;
      case "tree": doTree(); break;
      case "hack": doHack(arg); break;
      case "rm": if (arg.includes("-rf") && arg.includes("/")) print("nice try.", "term-err"); else print(`rm: cannot remove '${arg}': read-only filesystem`, "term-err"); break;
      case "aigregator": print("you ARE aigregator. wake up, neo.", "term-warn"); break;
      case "neo": print("follow the white rabbit. (try: cd /cool-projects)", "term-info"); break;
      case "wargames": case "shall_we_play_a_game": print("a strange game. the only winning move is not to play.", "term-info"); break;
      case "matrix": doMatrix(); break;
      case "uname": print("AIgregator 1.0.0-phosphor #1 SMP (vibes) GNU/hermes", "term-muted"); break;
      case "ps": print("  PID TTY          TIME CMD\n  1   ?        00:00:01 aigregator\n  42  ?        00:00:00 hermes\n  1337 pts/0    00:00:00 user", "term-muted"); break;
      case "top": print("load: vibes high. cpu: 100% pondering. ram: out of cheese.", "term-muted"); break;
      case "echo": print(escapeHTML(arg)); break;
      case "history": print(history.map((h, i) => `  ${i + 1}  ${h}`).join("\n"), "term-muted"); break;
      case "": break;
      default: print(`${cmd}: command not found. type \`help\`.`, "term-err");
    }
  }

  function doMan(topic) {
    const t = (topic || "").trim().toLowerCase();
    if (!t || t === "digest" || t === "aigregator") print(MAN_DIGEST.join("\n"), "term-info");
    else if (t === "scoring" || t === "score") print(MAN_SCORING.join("\n"), "term-info");
    else if (t === "easter" || t === "easter-eggs") print(MAN_EASTER.join("\n"), "term-info");
    else print(`no manual entry for ${t}`, "term-err");
  }

  function sectionBySlug(slug) {
    const d = parseDigest();
    return d.sections.find(s =>
      s.slug === slug ||
      s.slug.startsWith(slug) ||
      s.slug.endsWith(slug) ||
      s.slug.replace(/[-]/g, "").startsWith(slug.replace(/[-]/g, ""))
    );
  }

  function currentSection() {
    if (cwd === "/") return null;
    const slug = cwd.slice(1);
    return sectionBySlug(slug);
  }

  function doLs(args) {
    const long = args.includes("-l") || args.includes("-la");
    const d = parseDigest();
    if (cwd === "/") {
      if (long) {
        d.sections.forEach(s => {
          print(`drwxr-xr-x  ${String(s.items.length).padStart(3)} user  user  ${escapeHTML(s.title)}/`);
        });
        print(`-rw-r--r--   1  user  user  README.txt`, "term-muted");
        print(`-rw-r--r--   1  user  user  dashboard.json`, "term-muted");
      } else {
        const out = d.sections.map(s => s.slug + "/").join("  ");
        print(out + "  README.txt  dashboard.json");
      }
    } else {
      const s = currentSection();
      if (!s) { print(`ls: ${cwd}: no such directory`, "term-err"); return; }
      if (!s.items.length) { print("(quiet today)", "term-muted"); return; }
      s.items.forEach((it, i) => {
        const n = String(i + 1).padStart(2, "0");
        const title = it.title.length > 80 ? it.title.slice(0, 77) + "..." : it.title;
        print(`${n}.  ${escapeHTML(title)}`);
      });
      print("", null);
      print(`(${s.items.length} item${s.items.length === 1 ? "" : "s"} -- try \`cat <N>\` or \`open <N>\`)`, "term-muted");
    }
  }

  function doCd(target) {
    target = (target || "").trim();
    if (!target || target === "~" || target === "/") { cwd = "/"; updatePrompt(); return; }
    if (target === "..") { cwd = "/"; updatePrompt(); return; }
    if (target.startsWith("/")) target = target.slice(1);
    const s = sectionBySlug(target.toLowerCase());
    if (!s) { print(`cd: ${target}: no such directory. try \`ls\`.`, "term-err"); return; }
    cwd = "/" + s.slug;
    updatePrompt();
  }

  function doCat(arg) {
    if (arg === "README.txt") {
      print("AIGREGATOR daily AI signal -- terminal mode.\n", "term-info");
      print("Today's digest is mounted as a fake filesystem.\nUse `ls` to list, `cd <section>` to enter, `cat <N>` to read.\n", "term-muted");
      print("Type `man digest` for the manual.\nType `themes` to switch back.", "term-muted");
      return;
    }
    if (arg === "dashboard.json") { doDash(); return; }
    const s = currentSection();
    if (!s) { print("cat: must `cd` into a section first. try `ls`.", "term-err"); return; }
    const n = parseInt(arg, 10);
    if (!n || n < 1 || n > s.items.length) {
      print(`cat: ${arg}: no such story. range: 1..${s.items.length}`, "term-err");
      return;
    }
    const it = s.items[n - 1];
    print("─".repeat(60), "term-muted");
    print(`<strong style="color:#ffb000">${escapeHTML(it.title)}</strong>`);
    print(escapeHTML(it.raw));
    if (it.links.length) {
      print("");
      print("sources:", "term-muted");
      it.links.forEach((l, i) => {
        print(`  [${i + 1}] <a class="term-link" href="${l.href}" target="_blank">${escapeHTML(l.text)}</a> -- ${escapeHTML(l.href)}`);
      });
    }
    print("─".repeat(60), "term-muted");
  }

  function doOpen(arg) {
    const s = currentSection();
    if (!s) { print("open: must `cd` into a section first.", "term-err"); return; }
    const n = parseInt(arg, 10);
    if (!n || n < 1 || n > s.items.length) {
      print(`open: ${arg}: no such story.`, "term-err"); return;
    }
    const it = s.items[n - 1];
    if (!it.links.length) { print("open: no link available", "term-err"); return; }
    print(`opening ${it.links[0].href}...`, "term-info");
    window.open(it.links[0].href, "_blank");
  }

  function doDash() {
    const d = parseDigest();
    print("─".repeat(60), "term-muted");
    print(escapeHTML(d.date), "term-warn");
    if (d.subtitle) print(escapeHTML(d.subtitle), "term-muted");
    print("");
    print(escapeHTML(d.dashboard));
    print("─".repeat(60), "term-muted");
  }

  function doTheme(name) {
    if (!name) { print("usage: theme <phosphor|light|geocities|terminal>", "term-info"); return; }
    if (!THEMES.includes(name)) { print(`theme: unknown theme '${name}'`, "term-err"); return; }
    print(`switching to ${name}...`, "term-info");
    setTimeout(() => applyTheme(name), 400);
  }

  function doArchive() {
    print("fetching archive...", "term-muted");
    fetch("../archive.html").then(r => r.text()).then(html => {
      const m = [...html.matchAll(/<a href="digests\/([^"]+)\.html">([^<]+)<\/a>/g)];
      if (!m.length) {
        // we might be on the index page
        const m2 = [...html.matchAll(/<a href="digests\/([^"]+)\.html">([^<]+)<\/a>/g)];
        if (!m2.length) { print("archive empty or unreachable", "term-err"); return; }
      }
      print("archived transmissions:", "term-info");
      m.forEach(x => {
        print(`  <a class="term-link" href="../digests/${x[1]}.html">${escapeHTML(x[1])}</a>  ${escapeHTML(x[2])}`);
      });
    }).catch(() => print("archive: network error", "term-err"));
  }

  function doTree() {
    const d = parseDigest();
    print(".");
    d.sections.forEach((s, i) => {
      const last = i === d.sections.length - 1;
      print(`${last ? "└── " : "├── "}${s.slug}/`);
      s.items.forEach((it, j) => {
        const lastItem = j === s.items.length - 1;
        const prefix = last ? "    " : "│   ";
        print(`${prefix}${lastItem ? "└── " : "├── "}${String(j + 1).padStart(2, "0")}_${escapeHTML(it.title.slice(0, 40))}`);
      });
    });
  }

  function doHack(arg) {
    if (!arg) { print("usage: hack <planet|mainframe|gibson|nsa>", "term-info"); return; }
    const targets = { planet: "the planet", mainframe: "the mainframe", gibson: "the gibson", nsa: "lol no" };
    const target = targets[arg.toLowerCase()];
    if (!target) { print(`hack: unknown target '${arg}'`, "term-err"); return; }
    print(`accessing ${target}...`, "term-info");
    const steps = [
      "bypassing firewall.....",
      "spoofing mac address...",
      "injecting payload......",
      "escalating privileges..",
      "covering tracks........",
      "🟢 ACCESS GRANTED. (just kidding. close your terminal and touch grass.)",
    ];
    let i = 0;
    const tick = () => {
      if (i >= steps.length) return;
      print(steps[i], i === steps.length - 1 ? "term-warn" : "term-muted");
      i++;
      setTimeout(tick, 350);
    };
    tick();
  }

  function doMatrix() {
    let count = 0;
    const id = setInterval(() => {
      const row = Array.from({length: 60}, () =>
        String.fromCharCode(0x30A0 + Math.random() * 96 | 0)).join("");
      print(`<span style="color:#00ff41">${escapeHTML(row)}</span>`);
      count++;
      if (count > 20) { clearInterval(id); print("wake up, neo.", "term-warn"); }
    }, 80);
  }

  // ─── COPY LINK + KONAMI CODE ─────────────────────────────
  function wireCopyLinks() {
    document.querySelectorAll("a.copy-link").forEach(a => {
      a.addEventListener("click", e => {
        e.preventDefault();
        const url = a.getAttribute("data-url") || location.href;
        if (navigator.clipboard) {
          navigator.clipboard.writeText(url).then(() => {
            const original = a.textContent;
            a.textContent = "OK!";
            a.classList.add("copied");
            setTimeout(() => {
              a.textContent = original;
              a.classList.remove("copied");
            }, 1500);
          });
        }
      });
    });
  }

  function wireKonami() {
    const SEQ = ["ArrowUp","ArrowUp","ArrowDown","ArrowDown",
                 "ArrowLeft","ArrowRight","ArrowLeft","ArrowRight","b","a"];
    let idx = 0;
    document.addEventListener("keydown", e => {
      const expected = SEQ[idx];
      if (e.key === expected || e.key.toLowerCase() === expected) {
        idx++;
        if (idx === SEQ.length) {
          idx = 0;
          applyTheme("geocities");
          // Brief on-screen toast
          const toast = document.createElement("div");
          toast.textContent = "★ KONAMI ACCEPTED · GEOCITIES MODE ★";
          toast.style.cssText = "position:fixed;top:20px;left:50%;transform:translateX(-50%);" +
            "background:#ff00ff;color:#fff;padding:8px 16px;font-family:'Comic Sans MS',cursive;" +
            "font-size:14px;font-weight:bold;border:3px ridge #ffff00;z-index:10000;letter-spacing:1px;";
          document.body.appendChild(toast);
          setTimeout(() => toast.remove(), 2500);
        }
      } else {
        idx = 0;
      }
    });
  }

  function wireArchiveFilter() {
    const search = document.getElementById("archive-search");
    const body = document.getElementById("archive-body");
    if (!search || !body) return;
    const rows = Array.from(body.querySelectorAll("tr[data-themes]"));
    const countEl = document.getElementById("archive-count");
    let activeTheme = "";
    let activeQuery = "";

    function apply() {
      let visible = 0;
      rows.forEach(row => {
        const themes = (row.getAttribute("data-themes") || "").toLowerCase();
        const text = row.textContent.toLowerCase();
        const themeOk = !activeTheme || themes.split(",").includes(activeTheme);
        const qOk = !activeQuery || text.includes(activeQuery);
        const show = themeOk && qOk;
        row.classList.toggle("hidden", !show);
        if (show) visible++;
      });
      if (countEl) countEl.textContent = visible;
    }

    search.addEventListener("input", e => {
      activeQuery = e.target.value.trim().toLowerCase();
      apply();
    });

    document.querySelectorAll(".filter-chip").forEach(chip => {
      chip.addEventListener("click", () => {
        document.querySelectorAll(".filter-chip").forEach(c => c.classList.remove("active"));
        chip.classList.add("active");
        activeTheme = (chip.getAttribute("data-theme") || "").toLowerCase();
        apply();
      });
    });
  }

  // ─── INIT ────────────────────────────────────────────────
  function init() {
    buildSwitcher();
    const saved = localStorage.getItem(STORAGE_KEY) || "phosphor";
    applyTheme(saved);
    wireCopyLinks();
    wireKonami();
    wireArchiveFilter();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else { init(); }
})();
