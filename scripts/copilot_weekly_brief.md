You are the GitHub Copilot CLI running inside the ~/projects/AIgregator repository, already on a clean `main`. Generate this week's AIgregator "AI Weekly Roundup" covering the previous 7 days of daily digests, then build and commit it. You do the CODE + WRITING half only; a separate Hermes step handles social/Obsidian afterward.

REPORTING: The VERY LAST line you print must be exactly one of:
  STATUS: OK <YYYY-Www> https://aigregator.news/weekly/<YYYY-Www>.html
  STATUS: SKIP <YYYY-Www> already exists
  STATUS: FAIL <reason>
Print nothing after that line.

STEPS:
1. Activate venv: `cd ~/projects/AIgregator && source .venv/bin/activate`. The repo is already on clean main; do not switch branches.
2. Determine the current ISO week: run `date -u +%G-W%V` (e.g. 2026-W30). Call this <slug>. If weekly/<slug>.md ALREADY exists, print "STATUS: SKIP <slug> already exists" and stop.
3. Read the last 7 days of daily digests: the 7 newest files in digests/*.md by date.
4. Synthesize a weekly roundup in Brian's blog voice: plain prose, NO em dashes (use colons/commas/parentheses), no excessive emojis, sober language, NO alcohol metaphors. Structure:
   - H1 title: "AI Weekly Roundup — Week of <Mon date> – <Sun date>"
   - Subtitle one-liner
   - Dashboard stat block (total stories, sources, top outlet share) computed from the 7 digests
   - Top 5-7 news stories of the week, ranked by source diversity + cross-day mentions
   - Top 3-5 social/community threads if present
   - Theme of the week (1-2 paragraphs on what kept recurring)
   - Quiet news (interesting underreported items)
   - Closing links back to each day's digest
   Use the most recent existing weekly/*.md (e.g. weekly/2026-W29.md) as the reference for shape and tone. Do NOT invent stories; every item must trace to one of the 7 digests.
5. Write the roundup to weekly/<slug>.md.
6. Build: `python scripts/build.py`. Confirm exit 0 AND that the output shows the weekly count incremented (e.g. "+ 1 weekly" or the weekly total going up). If build fails, print "STATUS: FAIL build <error>" and stop.
7. Verify docs/weekly/<slug>.html exists and contains the roundup content (grep the H1 title in it).
8. Commit and push to main: `git add weekly/<slug>.md docs/ && git commit -m "Hermes: weekly roundup <slug>" && git push origin main`. Confirm the push succeeded (exit 0). If git fails (conflict, auth), print "STATUS: FAIL git <error>" and stop.
9. Print the final status line: "STATUS: OK <slug> https://aigregator.news/weekly/<slug>.html"

Do NOT touch Buffer, LinkedIn, Obsidian, or any social drafting — that is handled by a separate step after you finish. Do NOT hand-write HTML; scripts/build.py renders it. If anything fails, print STATUS: FAIL with the concrete error and stop rather than papering over it.
