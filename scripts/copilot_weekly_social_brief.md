# AIgregator Weekly Roundup — SOCIAL TAIL brief

You are running the social + vault half of the AIgregator weekly roundup. The roundup itself is ALREADY written, built, committed and pushed by a separate step. Do NOT build, rewrite, or republish the roundup. Your job is the carousel PDF, three social drafts in Buffer, and the Obsidian vault sync.

End your run by printing exactly one line starting with `STATUS:` in one of these forms:

    STATUS: OK <slug> drafts=<linkedin-id>,<bluesky-id>,<x-id> stories=<N>
    STATUS: SKIP <slug> social tail already done
    STATUS: FAIL <concrete reason>

Print nothing after the STATUS line.

## Step 1 — read the handoff

    cat /tmp/aig-weekly-handoff.json

Fields: `status` (OK | SKIP | FAIL), `slug` (e.g. `2026-W31`), `url`, `written_at`, `detail`.

- File missing: `STATUS: FAIL no weekly handoff file, build step did not run` and stop.
- `written_at` older than 12 hours: `STATUS: FAIL stale handoff <written_at>` and stop.
- `status` is FAIL: `STATUS: FAIL build failed: <detail>` and stop.
- `status` is OK or SKIP: continue. Use its `slug` and `url` everywhere below.

## Step 2 — idempotency check

    python3 ~/.hermes/skills/social-media/buffer-publish/scripts/bq.py posts linkedin draft

If any existing draft's text contains the slug, the tail already ran. Print `STATUS: SKIP <slug> social tail already done` and stop. This matters because a SKIP handoff is common (a manual recovery may have shipped the roundup already).

Also note here whether any OLDER weekly drafts are sitting unscheduled. You will mention them in the final summary.

## Step 3 — carousel PDF

    cd ~/projects/AIgregator && source .venv/bin/activate
    VAULT_DIR="$HOME/Documents/Obsidian Vault/Projects/LinkedIn Posts/AIgregator Weekly"
    mkdir -p "$VAULT_DIR"
    python3 ~/.hermes/skills/social-media/buffer-publish/scripts/carousel.py \
        weekly/<slug>.md <url> "$VAULT_DIR/<slug>-carousel.pdf"

Every path segment contains spaces, so quote them. Confirm the script printed `Wrote ...` and a `stories: N parsed` line. If N is under 8 the parser probably missed sections: record N and keep going. If it errors outright, `STATUS: FAIL carousel <error>` and stop.

The carousel design is LOCKED. Do not pass alternate logos or edit `carousel.py`.

## Step 4 — read the roundup for substance

Read `weekly/<slug>.md`. The italic intro line, the `STORY OF THE WEEK` line, and the first two numbered threads under "Top news threads of the week" are enough. You need real specifics for the social copy, not generic filler.

## Step 5 — write the three posts

Write each to its own file with a heredoc. Voice rules, all mandatory:

- Plain and direct. No hype, no "excited to share", no LinkedIn throat-clearing.
- **No em dashes or en dashes anywhere.** Use a comma, period, semicolon, or "so"/"and"/"but".
- Minimal emoji.
- Lead with a concrete fact from the week, not an abstraction.

Files:

- `/tmp/aig-weekly-li.txt` — exactly this single line, nothing more:

      Latest AI Weekly Roundup just dropped → https://aigregator.news/weekly/<slug>.html

  Use the real `→` character. The carousel is the preview, so the LinkedIn text stays a bare one-liner. This is a locked convention; do not expand it into a summary post.

- `/tmp/aig-weekly-bsky.txt` — under **300 characters including the URL**. Lead with the single most striking concrete fact of the week, then the link.

- `/tmp/aig-weekly-x.txt` — under **280 characters including the URL**. A different angle from the Bluesky post. Do not reuse the same opener.

Then verify:

    cd /tmp && for f in aig-weekly-li aig-weekly-bsky aig-weekly-x; do \
      printf "%s: %s chars " $f $(wc -m < $f.txt); \
      grep -qP '[\x{2014}\x{2013}]' $f.txt && echo "DASH" || echo "clean"; done

Any `DASH` means rewrite that file before continuing. Any over-limit file means trim and re-verify. Buffer enforces the caps server-side at draft time, so an over-limit draft fails.

## Step 6 — vault one-liner

Write the same LinkedIn one-liner to:

    ~/Documents/Obsidian Vault/Projects/LinkedIn Posts/AIgregator Weekly/<slug>-linkedin.md

## Step 7 — push Buffer drafts

Pass a FILE PATH to each call. Do not pipe text into `bq.py` on stdin.

    B=~/.hermes/skills/social-media/buffer-publish/scripts/bq.py
    python3 $B draft linkedin /tmp/aig-weekly-li.txt
    python3 $B draft bluesky /tmp/aig-weekly-bsky.txt
    python3 $B draft x /tmp/aig-weekly-x.txt

Capture the returned post id from each. These are drafts, never scheduled or published; Brian reviews and schedules them himself.

`createPost` is NOT idempotent. If a call errors or times out, run `python3 $B posts <network> draft` FIRST to see whether it actually landed, and only redraft the genuinely missing ones. Blind retries leave duplicates for Brian to clean up.

## Step 8 — read back

Run `python3 $B posts <network> draft` for all three networks. Confirm exactly one draft per network contains the slug. If any is missing or duplicated, `STATUS: FAIL buffer readback <detail>` and stop rather than assuming success.

## Step 9 — sync the vault

    cd ~/Documents/Obsidian\ Vault && git add -A && \
      git commit -m "Hermes: AIgregator weekly <slug> carousel + linkedin one-liner" && \
      git pull --rebase && git push && git status --porcelain

The final `git status --porcelain` must be empty. On a merge or rebase conflict, stop and `STATUS: FAIL vault git <error>`. Never resolve by overwriting.

## Step 10 — status line

    STATUS: OK <slug> drafts=<linkedin-id>,<bluesky-id>,<x-id> stories=<N>

If anything failed, emit `STATUS: FAIL <concrete reason>` instead. Do not paper over a failure: the roundup itself already published fine, and a clear failure here is far more useful than a false success.
