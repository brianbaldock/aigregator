# AIgregator Weekly Roundup — local SimplePost producer preparation

The roundup is already written and published by a separate step. This task prepares
only the local artifacts consumed by `scripts/simplepost_weekly_handoff.py`. It does
not authorize, schedule, publish, send, or create any Buffer post. Do not use Buffer,
its helpers, credentials, API, exports, or fallbacks.

The wrapper has validated `/tmp/aig-weekly-handoff.json` and supplied these values:

- `AIG_WEEKLY_WORK_DIR`
- `AIG_WEEKLY_SLUG`
- `AIG_WEEKLY_URL`

Write only these regular files in `AIG_WEEKLY_WORK_DIR`; do not use a symlink:

    <slug>-linkedin.txt
    <slug>-bluesky.txt
    <slug>-x.txt
    <slug>-carousel.pdf

Keep failed partial artifacts for a safe retry. Do not invoke SimplePost: the wrapper
does the deterministic import and database readback outside this model invocation.

## Organization policy and vault preflight

Read these files directly. This Copilot run does not inherit Hermes skills:

- `~/.hermes/skills/note-taking/obsidian/SKILL.md`
- `~/.hermes/skills/note-taking/obsidian/references/knowledge-organization.md`

If either is unavailable, fail before writing vault content. Their organization and
scoped-sync rules apply. Keep topics, note type, provenance, and lifecycle distinct;
folder placement alone is not integration. Do not change publishing transport,
schedules, or the approved carousel design as part of organizing the vault.

Compatibility paths (not a new subject taxonomy):

    VAULT="$HOME/Documents/Obsidian Vault"
    VAULT_REL="Projects/LinkedIn Posts/AIgregator Weekly"
    VAULT_DIR="$VAULT/$VAULT_REL"
    INDEX_REL="$VAULT_REL/AIGregator Weekly.md"

Inspect `git status --short --branch` and the staged diff in the vault, fetch origin,
and reconcile with `git merge --ff-only origin/main` before writing. Require the
vault main branch, no pre-existing staged changes, and no local unpushed commits; do
not publish another session's commits. Fast-forward is safe with unrelated dirty
files when Git accepts it. If Git refuses, stop and report the conflict; do not stash,
reset, clean, or commit unrelated work unattended. Record pre-existing dirty and
untracked paths so they are preserved.

Read the existing weekly index and `00 - Home.md`, plus any relevant existing
project/publication hub. Require the directory and index above to already exist. If
either is missing, stop and report the layout change; do not recreate the old tree.
Abort if this edition's intended files or an index that needs editing have
pre-existing uncommitted changes. Do not take ownership of Brian's edits.

Maintain the existing publication lineage under those rules. If any vault preflight,
lineage validation, scoped sync, or verification step fails, fail the entire run
before reporting artifact completion:
`<slug>-linkedin.md` is the exact paste-ready LinkedIn copy, with no frontmatter,
index text, or wikilinks. The companion is a `type: publication-edition` note with
the real edition slug, exact published URL, and vault-relative links to the index,
copy, and PDF. Keep article state separate from social review state; do not claim
that a review card is scheduled, sent, approved, or published. Preserve user-authored
content and make targeted edits. Add exactly one edition link to the existing index,
and add a descriptive Home link only when no existing Home-to-hub path exists.

Only the edition PDF, one-liner, companion, weekly index, and a necessary existing
hub/Home note may be staged. Before sync, resolve every introduced wikilink and
verify Home -> hub -> index -> edition -> copy/PDF, one index entry, the exact source
URL, and no private navigation metadata in the copy. Stage only those explicit paths,
inspect the staged diff, commit only nonempty task changes, and push only this run's
commit after confirming it belongs to this run. Re-fetch and verify `HEAD` equals
`origin/main`; preserve unrelated dirty work. On conflict or unverifiable sync,
report failure rather than claiming completion.

## Produce the locked review artifacts

1. Read `weekly/<slug>.md` for substance and use the existing approved carousel
   generator unchanged. Generate the five-page PDF at
   `$AIG_WEEKLY_WORK_DIR/<slug>-carousel.pdf`; it must be nonempty, openable, and
   derived from the current source. Preserve the approved carousel design.
2. Write three exact UTF-8 copy files. Every copy must contain the exact weekly URL.
   LinkedIn is exactly one line:

       Latest AI Weekly Roundup just dropped → <url>

   Bluesky is under 300 characters including the URL. X is under 280 characters
   including the URL and takes a different concrete angle. All copy is plain and
   direct, leads with a concrete fact, has no em/en dash, and has minimal emoji.
3. Use that exact LinkedIn line and PDF to update the scoped vault lineage and sync
   it according to the policy above. Vault preflight and sync are mandatory; any
   failure must terminate this worker nonzero. Vault work does not authorize social
   distribution.

Do not print a success status that represents import, review, approval, scheduling,
or publication. The wrapper determines success exclusively from the producer's
canonical output and local database readback.
