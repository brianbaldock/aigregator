# AIgregator Weekly Roundup — SOCIAL TAIL brief

You are running the social + vault half of the AIgregator weekly roundup. The roundup itself is ALREADY written, built, committed and pushed by a separate step. Do NOT build, rewrite, or republish the roundup. Your job is the carousel PDF, three social drafts in Buffer, and the Obsidian vault sync.

End your run by printing exactly one line starting with `STATUS:` in one of these forms:

    STATUS: OK <slug> drafts=<linkedin-id>,<bluesky-id>,<x-id> stories=<N>
    STATUS: SKIP <slug> social tail already done
    STATUS: FAIL <concrete reason>

Print nothing after the STATUS line.

## Step 0 - organization policy and vault preflight

Read these files directly. This Copilot run does not inherit Hermes skills:

- `~/.hermes/skills/note-taking/obsidian/SKILL.md`
- `~/.hermes/skills/note-taking/obsidian/references/knowledge-organization.md`

If either is unavailable, fail before writing. Their organization and scoped-sync
rules apply here. Keep topics, note type, provenance and lifecycle distinct;
folder placement alone is not integration. Do not change publishing transport,
schedules, or the approved carousel design as part of organizing the vault.

Current compatibility paths (not a new subject taxonomy):

    VAULT="$HOME/Documents/Obsidian Vault"
    VAULT_REL="Projects/LinkedIn Posts/AIgregator Weekly"
    VAULT_DIR="$VAULT/$VAULT_REL"
    INDEX_REL="$VAULT_REL/AIGregator Weekly.md"

Inspect `git status --short --branch` and the staged diff in the vault, fetch
origin, and reconcile with `git merge --ff-only origin/main` before writing.
Require the vault's main branch, no pre-existing staged changes, and no local
unpushed commits; do not publish another session's commits. Fast-forward is safe
with unrelated dirty files when Git accepts it. If Git refuses, stop and report
the conflict; do not stash, reset, clean or commit unrelated work unattended.
Record the pre-existing dirty/untracked paths so they can be preserved.

Read the existing weekly index and `00 - Home.md`, plus any relevant existing
project/publication hub. Require the directory and index above to already exist.
If either is missing, STOP with `STATUS: FAIL vault layout changed` and report
any relocated candidate. Do not recreate the old tree with `mkdir -p`. A folder
migration must update this brief and the wrapper's `VAULT_DIR` together.
Abort if this edition's intended files or an index that needs editing have
pre-existing uncommitted changes. Do not take ownership of Brian's edits.

## Step 1 — read the handoff

    cat /tmp/aig-weekly-handoff.json

Fields: `status` (OK | SKIP | FAIL), `slug` (e.g. `2026-W31`), `url`, `written_at`, `detail`.

- File missing: `STATUS: FAIL no weekly handoff file, build step did not run` and stop.
- `written_at` older than 12 hours: `STATUS: FAIL stale handoff <written_at>` and stop.
- `status` is FAIL: `STATUS: FAIL build failed: <detail>` and stop.
- `status` is OK or SKIP: continue. Use its `slug` and `url` everywhere below.
- Validate `slug` as a real ISO week in exact `YYYY-Www` form and require `url`
  to equal `https://aigregator.news/weekly/<slug>.html`. Reject invalid values;
  never normalize a malformed slug into a filename or shell argument.

## Step 2 — idempotency check

Read Buffer posts for EACH of `linkedin`, `bluesky`, and `x`, using the existing
helper with each of the statuses `draft`, `scheduled`, and `sent`:

    python3 ~/.hermes/skills/social-media/buffer-publish/scripts/bq.py posts <network> <status>

Match the exact weekly URL in post text, not a substring of the slug. Record
IDs, actual statuses and text per network. The current `bq.py posts` helper
filters one response client-side and does NOT expose GraphQL errors or pagination
metadata. Its printed zero count is NOT proof of absence. Before any create call,
use its read-only `raw`/introspection surface to verify complete response coverage
and no GraphQL errors; resolve pagination using the verified live schema or fail
closed if completeness cannot be established. Do not invent pagination arguments.
Multiple matches on a network are a blocker to report, not permission to delete
or redraft. If some networks have scheduled/sent posts while others are missing,
stop for manual reconciliation before creating anything; the wrapper's OK summary
assumes three unscheduled drafts.

An existing post protects that network from another create call, even if already
scheduled or sent. Create only genuinely missing network drafts. If all three
exist, skip copy generation and Buffer mutations, but CONTINUE through vault
integration, link verification and sync. An existing LinkedIn draft alone is
not proof the PDF, other drafts or graph links were completed.

Also note any older weekly drafts sitting unscheduled for the final summary.

## Step 3 — carousel PDF

Reuse an existing PDF only after checking it is nonempty, opens, has five pages,
and reflects the current weekly source. Regenerate a missing, stale or invalid
PDF with the existing generator. Use the paths validated in Step 0:

    cd ~/projects/AIgregator && source .venv/bin/activate
    python3 ~/.hermes/skills/social-media/buffer-publish/scripts/carousel.py \
        weekly/<slug>.md <url> "$VAULT_DIR/<slug>-carousel.pdf"

Every path segment contains spaces, so quote them. Confirm the script printed `Wrote ...` and a `stories: N parsed` line. If N is under 8 the parser probably missed sections: record N and keep going. If it errors outright, `STATUS: FAIL carousel <error>` and stop.

The carousel design is LOCKED. Do not pass alternate logos or edit `carousel.py`.

## Step 4 — read the roundup for substance

Read `weekly/<slug>.md`. The italic intro line, the `STORY OF THE WEEK` line, and the first two numbered threads under "Top news threads of the week" are enough. You need real specifics for the social copy, not generic filler.

Determine the final `stories=<N>` from the current source with the carousel's
existing parser, including when the PDF was reused. Do not invent N from an old log.

## Step 5 — write the three posts

Write each missing network's copy to its own file using file-editing tools.
For an existing post, preserve its verified text rather than generating a new
version: put the verified text in its corresponding temporary file for the
checks below, never reuse a leftover `/tmp` file. If all three posts exist,
skip this entire step. Do not use interpreter pipes or shell heredocs.
Voice rules, all mandatory:

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

## Step 6 - vault publication lineage (also required on reruns)

Keep `<slug>-linkedin.md` as the exact paste-ready LinkedIn one-liner, with no
frontmatter, index text or wikilinks. Create it if absent, using the verified
existing post text or this run's approved one-liner. Preserve an existing matching file; if its
text differs from the verified Buffer post or the required one-liner, report
the discrepancy instead of silently replacing either version.

Maintain a companion at `$VAULT_DIR/<slug>.md`, not another copy of the roundup.
Use a small `type: publication-edition` property and the real `edition` slug.
Keep published-article state separate from social draft/scheduled/sent state;
record social IDs/statuses only after readback in Step 8. Do not infer topic
tags from the announcement or invent a verification/publication date.

The companion must include:

- A link back to the existing weekly index.
- The exact published weekly URL as a normal external Markdown link.
- Explicit vault-relative wikilinks to `<slug>-linkedin.md` and
  `<slug>-carousel.pdf` (include `.pdf` for the attachment).
- Relevant existing project or subject-map links only after reading both ends
  and explaining the relationship. Do not create placeholder topic notes.

At the current paths, the navigation skeleton is:

    # <slug> - AIgregator weekly
    Part of [[Projects/LinkedIn Posts/AIgregator Weekly/AIGregator Weekly|AIgregator Weekly]].
    Source: [Published roundup](https://aigregator.news/weekly/<slug>.html)
    Copy: [[Projects/LinkedIn Posts/AIgregator Weekly/<slug>-linkedin|LinkedIn copy]]
    Attachment: [[Projects/LinkedIn Posts/AIgregator Weekly/<slug>-carousel.pdf|Carousel PDF]]

Replace every placeholder with the validated value. Preserve user-authored
companion content; make targeted edits rather than rewriting it wholesale.
Add exactly one edition link to `$INDEX_REL`, preserving existing prose and
other editions. Ensure the index itself is reachable from an existing
project/publication hub connected to Home. If no such path exists, add one
descriptive link under Home's existing `Main indexes` section. Do not build a
parallel index hierarchy or bulk backfill old editions in this weekly run.

Track the exact changed paths: this edition's PDF, one-liner, companion, weekly
index and (only if necessary) the existing hub or Home. These are the ONLY vault
paths this run may stage. Private navigation must never enter Buffer payloads.

## Step 7 — push Buffer drafts

Only for networks proven missing in Step 2, pass a FILE PATH to each call below.
Skip all create calls when all three posts already exist. Never pass a companion
or index note as the payload. Do not pipe text into `bq.py` on stdin.

    B=~/.hermes/skills/social-media/buffer-publish/scripts/bq.py
    python3 $B draft linkedin /tmp/aig-weekly-li.txt
    python3 $B draft bluesky /tmp/aig-weekly-bsky.txt
    python3 $B draft x /tmp/aig-weekly-x.txt

Capture the returned post id from each. These are drafts, never scheduled or published; Brian reviews and schedules them himself.

`createPost` is NOT idempotent. If a call errors or times out, run `python3 $B posts <network> draft` FIRST to see whether it actually landed, and only redraft the genuinely missing ones. Blind retries leave duplicates for Brian to clean up.

## Step 8 — read back

Read back each new draft and each reused post by its recorded ID (the helper's
`posts` command supports the actual status from Step 2). Confirm exact weekly
URL and expected text, one post per network, and `draft` status for every newly
created post. Preserve already scheduled/sent posts without mutation. On missing,
duplicate or mismatched results, `STATUS: FAIL buffer readback <detail>` and stop.
Update the companion with the verified per-network IDs and states, not a blanket
claim that all social posts are published.

Before sync, read the actual notes and verify the navigation journey:
Home -> existing hub (if any) -> weekly index -> edition companion -> copy/PDF.
Resolve each introduced wikilink against the vault filesystem, including the
attachment; check there is exactly one index entry for this edition, the source
URL is exact, and the LinkedIn payload still contains only its one-liner. Missing
targets, duplicate entries, or private metadata in copy are failures. A file's
existence or a higher edge count is not enough.

## Step 9 — sync the vault

Run every Git command in this step against the vault, using `git -C "$VAULT"`
or explicitly changing to that directory first, not the AIgregator repo or `/tmp`.

Recheck the staged diff is empty, inspect the worktree diff, then stage ONLY the
explicit task-owned changed paths recorded in Step 6, using `git add --` with
each quoted filename. Never use whole-vault staging or directory-wide pathspecs.
Inspect `git diff --cached --name-only` and `git diff --cached` against that list.
If no task changes remain, skip the commit rather than failing on an empty commit.
Otherwise commit with `Hermes: AIgregator weekly <slug> linked publication bundle`.

Fetch origin again. If the remote advanced during this run and a normal rebase
is blocked by unrelated dirty files, STOP and report the blocker; no unattended
stash/autostash, reset or broad commit. Never push other sessions' new local
commits. Push only after checking the outgoing commits belong to this run.
After push, fetch and verify local HEAD equals origin/main and no task-owned
changes remain. Check the committed blobs for the companion/index/copy and
attachment links, and confirm unrelated pre-existing dirty work was preserved.
The entire shared worktree need NOT be clean. On conflict or unverifiable sync,
emit `STATUS: FAIL vault git <error>` rather than claiming completion.

## Step 10 — status line

    STATUS: OK <slug> drafts=<linkedin-id>,<bluesky-id>,<x-id> stories=<N>

If anything failed, emit `STATUS: FAIL <concrete reason>` instead. Do not paper over a failure: the roundup itself already published fine, and a clear failure here is far more useful than a false success.

Use `STATUS: SKIP <slug> social tail already done` only if all three posts
already existed AND the vault bundle has now been verified and synced (including
any repaired graph links). If existing scheduled/sent posts were reused, name
their actual states in the summary before this final line. The wrapper's PDF
check is only a backstop; it does not independently verify the graph or git sync.
