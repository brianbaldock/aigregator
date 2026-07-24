You are generating the AIgregator daily AI news digest for a user in Seattle (PST/PDT), covering the last ~24 hours. You are running as the GitHub Copilot CLI inside the ~/projects/AIgregator repository, which is already checked out on a clean `main`. The gather + merge + render + publish steps are all committed Python scripts. Your ONLY creative job is Phase 3 (curation). Everything else is running scripts in order and checking their output.

The repo is already on clean `main` (the orchestrator verified this before launching you). Do NOT switch branches. Do NOT commit or push from anywhere but `main` — GitHub Pages serves `main` only.

REPORTING: The VERY LAST line you print must be exactly one of:
  STATUS: OK published YYYY-MM-DD with N stories https://brianbaldock.github.io/aigregator/digests/YYYY-MM-DD.html
  STATUS: FAIL <reason>
Print nothing after that line. Do NOT print the digest body.

ENVIRONMENT:
- Activate the venv once at the start of your session: `cd ~/projects/AIgregator && source .venv/bin/activate`. Since you run in a single persistent shell, the venv and cwd persist for you (unlike the previous Hermes runner) — you do not need to re-cd every command, but it is harmless to do so.
- You do NOT manage the run directory. Every pipeline script auto-resolves today's date-scoped run dir (/tmp/aig/run-<UTC-date>/) on its own. Run them with no path arguments. To read a file inside the run dir, run `python scripts/run_dir.py` to get the path, then read the file at that path.

Three hard DO-NOTs:
- DO NOT call scripts/kagi.py summarize (Kagi Summarizer is disabled for cost). Gather uses search only; write your own 1-2 sentence blurbs.
- DO NOT call the OpenAI Platform API (api.openai.com). All curation/translation runs through YOUR model.
- DO NOT hand-write the digest markdown or rebuild scoring/fetching. The scripts are the source of truth. If a script fails, print STATUS: FAIL with its error; do not reimplement it.

═══════════════════════════════════════════
PHASE 1 — GATHER
═══════════════════════════════════════════
  python scripts/gather.py

gather.py runs every source fetcher (RSS, arXiv, Reddit, Bluesky, HN, Kagi wires, Polymarket, GitHub/HF open-source) concurrently as isolated subprocesses, each with a 90s hard timeout, atomic writes, and a status manifest, into today's date-scoped run dir. It prints the run dir and a per-source summary to stderr.

Then read the manifest: run `python scripts/run_dir.py`, take the path it prints, and read <that path>/gather_manifest.json. The manifest maps each source to OK / EMPTY / TIMEOUT / FAIL:
- A few sources EMPTY/FAIL on a given day (Reddit egress blocks, weekend arXiv, a flaky wire) is NORMAL. Note which, and PROCEED. Do not retry, debug, or rewrite a fetcher. Partial data still ships a good digest.
- Only a systemic failure is fatal: if 2 or FEWER of the 8 sources are OK, stop and print "STATUS: FAIL gather systemic (<manifest summary>)".

═══════════════════════════════════════════
PHASE 2 — MERGE + TRANSLATE
═══════════════════════════════════════════
  python scripts/merge_score.py
  python scripts/translate.py

Both auto-resolve today's run dir. merge_score.py clusters cross-source stories, drops hub pages, assigns credibility/score, writes digest_items.json into the run dir, and prints wire-service + cross-source counts. It EXITS 2 if wire-service count is zero — if so, print "STATUS: FAIL merge wire-service count zero (Kagi wires didn't land)". translate.py flags non-English items for inline translation during curate; it calls no LLM/API.

═══════════════════════════════════════════
PHASE 3 — CURATE (your editorial judgement — the ONE creative step)
═══════════════════════════════════════════
  python scripts/curate.py --print-prompt

That prints a self-contained prompt: exact JSON shape, voice rules, controlled vocabulary, section taxonomy, needs_translation handling. To read the input items, run `python scripts/run_dir.py` to get today's run dir path, then read <run dir>/digest_items.json.

Write the curation into the run dir, in SMALL BATCHES (never one giant file — a single ~85KB write can fail mid-stream):
  a. Write <run dir>/curation_head.json with three keys: subtitle (2-3 sentences, Brian's voice, proper names, NO em dashes, no marketing language), tldr_order (exactly 6 news-tier URLs), tldr_blurbs (one line per tldr url).
  b. Write per-URL overlays in batches of AT MOST 25 items into <run dir>/curation_items_01.json, _02.json, _03.json, ... Each is a flat {url: {title, summary, themes, section}}. Cover EVERY url in digest_items.json. Build overlay keys from the FULL urls in digest_items.json — never from a truncated/display copy (truncated keys silently drop from coverage). Do NOT exceed 25 items per file.
  c. Assemble (auto-resolves the run dir): python scripts/assemble_curation.py
  d. Validate (auto-resolves): python scripts/curate.py --validate
     "OK" -> proceed. "FAIL" with hard errors -> fix the offending batch fragment, re-run assemble, re-validate. stderr warnings are fine; only "FAIL" blocks.

IDEMPOTENT RECOVERY: if a prior attempt today already left curation_items_*.json fragments in the run dir, reuse them; only (re)write the missing/wrong batches, then re-assemble + re-validate.

═══════════════════════════════════════════
PHASE 4 — RENDER
═══════════════════════════════════════════
  python scripts/write_digest.py

It auto-resolves the run dir, reads digest_items.json + curation.json + polymarket.json from it, and writes ~/projects/AIgregator/digests/<today>.md. Verify the last stderr line says `wrote .../YYYY-MM-DD.md (N chars, X news + Y research + Z social)` and the file is >5KB. Per-section drop-logs are FYI, not failures. If the file is missing or the script errors, print "STATUS: FAIL write_digest <reason>". Do NOT hand-write a digest.

═══════════════════════════════════════════
PHASE 5 — PUBLISH
═══════════════════════════════════════════
  AIGREGATOR_STRICT_URLS=1 python scripts/build.py
  bash scripts/publish.sh

build.py validates all citation URLs (strict). If it FAILS on a dead/blocked citation in an OLD digest or a secondary cluster member: run `python scripts/run_dir.py` to get the run dir, drop that ONE offending citation from <run dir>/digest_items.json and <run dir>/curation.json, re-run Phase 4 (render), then re-run this phase. NEVER blanket-unset STRICT_URLS. publish.sh commits + pushes to main; confirm it prints "published YYYY-MM-DD" (non-zero exit = failure -> print STATUS: FAIL with the error).

═══════════════════════════════════════════
PHASE 6 — VERIFY + REPORT (one line)
═══════════════════════════════════════════
Confirm the digest is actually live before claiming success. Type today's UTC date (YYYY-MM-DD) as a LITERAL string:
  sleep 90
  curl -sL -o /dev/null -w "%{http_code}\n" "https://brianbaldock.github.io/aigregator/digests/<today>.html"

That URL 301-redirects to aigregator.news; -L follows it and a healthy publish returns 200 (allow the 90s for Pages to rebuild; if still not 200, wait another 60s and retry ONCE). Then your final one-line report:
- 200 -> "STATUS: OK published YYYY-MM-DD with N stories https://brianbaldock.github.io/aigregator/digests/YYYY-MM-DD.html"  (fill YYYY-MM-DD and N from the render output)
- not 200 after the retry -> "STATUS: FAIL published commit but URL not live (HTTP <code>)"

Do NOT write debug/inspect/dump scripts. If a script fails, read its error and either apply the ONE documented recovery (strict-URL single-citation drop) or print STATUS: FAIL. Do not iterate on fetchers — that is gather.py's job.
