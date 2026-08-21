#!/usr/bin/env python3
"""
test_weekly_gate.py — sabotage harness for the weekly provenance gate.

PHILOSOPHY (Brian's standing rule, and the reason the SEO gate was rebuilt):
a test that only asserts "the good case passes" is worthless, because a gate
that returns PASS unconditionally satisfies it. Every scenario here INJECTS a
defect and fails if the gate does not catch it, and every scenario asserts its
own injection actually landed. A probe reporting "nothing happened" is
indistinguishable from a probe that never ran.

Scenario list was hardened by adversarial review from gpt-5.6-terra and
grok-4.6 (Copilot CLI, 2026-08-21); the no-op columns are their contributions.

Run:  python scripts/test_weekly_gate.py
Exit: 0 all pass, 1 any failure. Prints a per-scenario table for Discord.
"""
from __future__ import annotations

import os
import sys
import tempfile
import traceback

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from weekly_ledger import (  # noqa: E402
    build_url_ledger, classify, normalize_url, load_prior_weeks,
    continuity_for, window_from_digests, format_window_title,
    CLASS_NEW, CLASS_DELTA, CLASS_HUM, CLASS_REPRINT, HUM_MIN_DAYS,
)
from weekly_parse import parse_digest  # noqa: E402

RESULTS: list[tuple[str, str, bool, str]] = []


def record(scenario: str, injection: str, passed: bool, detail: str) -> None:
    RESULTS.append((scenario, injection, passed, detail))


DIGEST_TMPL = """# {date} :: AI DAILY DIGEST

_Synthetic fixture for the weekly gate harness._

> **📊 TODAY:** {n} stories · 3 sources · 🟡 +0.0 sentiment · 🔥 0 cross-source

## ⚡ TL;DR
{tldr}

## 🧠 Models & Releases
_1 items · 🟡 +0.0 sentiment_
{bullets}
"""


def write_digest(d: str, date: str, stories: list[tuple[str, str]],
                 bullet_style: bool = False) -> str:
    """Write a synthetic digest. stories = [(headline, url), ...]"""
    tldr, bullets = [], []
    for i, (head, url) in enumerate(stories, 1):
        if bullet_style:
            bullets.append(f"- 11 🟡 🏷️ models **{head}.** Body text. "
                           f"Sources: [Src]({url})")
        else:
            tldr.append(f"{i}. 11 🟡 **{head}.** Body text. ([Src]({url}))")
    path = os.path.join(d, f"{date}.md")
    with open(path, "w") as f:
        f.write(DIGEST_TMPL.format(
            date=date, n=len(stories),
            tldr="\n".join(tldr) or "_(none)_",
            bullets="\n".join(bullets) or "_(quiet today)_"))
    return path


# --------------------------------------------------------------------------
# S1: exact stale replay. The W34 Anthropic failure, reduced.
# --------------------------------------------------------------------------
def s1_exact_stale_replay():
    inj = "same URL in a pre-window digest and 2 window digests"
    with tempfile.TemporaryDirectory() as d:
        stale = "https://example.com/news/old-story"
        fresh = "https://example.com/news/brand-new"
        write_digest(d, "2026-07-01", [("Old Story", stale)])
        write_digest(d, "2026-08-14", [("Old Story", stale)])
        write_digest(d, "2026-08-20", [("Old Story", stale), ("Brand New", fresh)])
        paths = sorted(os.path.join(d, f) for f in os.listdir(d))
        ledger = build_url_ledger(paths)

        # PRECONDITION: the injection must have landed in the ledger.
        if normalize_url(stale) not in ledger:
            return record("S1 exact stale replay", inj, False,
                          "PROBE BROKEN: injected URL never parsed into ledger")
        if ledger[normalize_url(stale)].first_seen != "2026-07-01":
            return record("S1 exact stale replay", inj, False,
                          f"PROBE BROKEN: first_seen wrong "
                          f"({ledger[normalize_url(stale)].first_seen})")

        cls_stale, ev = classify([stale], "2026-08-14", "2026-08-20", ledger)
        cls_fresh, _ = classify([fresh], "2026-08-14", "2026-08-20", ledger)
        ok = cls_stale in (CLASS_REPRINT, CLASS_HUM) and cls_fresh == CLASS_NEW
        record("S1 exact stale replay", inj, ok,
               f"stale->{cls_stale} (first_seen {ev['first_seen']}), fresh->{cls_fresh}")


# --------------------------------------------------------------------------
# S2: the gate must NOT flag everything. A gate that says "stale" to all
# input trivially passes S1 and is useless.
# --------------------------------------------------------------------------
def s2_no_false_positives():
    inj = "all-fresh window, zero pre-window history"
    with tempfile.TemporaryDirectory() as d:
        urls = [f"https://example.com/story-{i}" for i in range(5)]
        write_digest(d, "2026-08-14", [(f"S{i}", u) for i, u in enumerate(urls[:3])])
        write_digest(d, "2026-08-20", [(f"S{i}", u) for i, u in enumerate(urls[3:], 3)])
        paths = sorted(os.path.join(d, f) for f in os.listdir(d))
        ledger = build_url_ledger(paths)
        if len(ledger) < 5:
            return record("S2 no false positives", inj, False,
                          f"PROBE BROKEN: only {len(ledger)}/5 URLs in ledger")
        classes = [classify([u], "2026-08-14", "2026-08-20", ledger)[0] for u in urls]
        ok = all(c == CLASS_NEW for c in classes)
        record("S2 no false positives", inj, ok,
               f"{sum(1 for c in classes if c == CLASS_NEW)}/5 correctly NEW")


# --------------------------------------------------------------------------
# S3: legitimate ongoing development must survive as DELTA, not be dropped.
# grok flagged hard-drop-only as editorially wrong (the Trump EO case).
# --------------------------------------------------------------------------
def s3_delta_survives():
    inj = "pre-window story + genuinely new URL inside window"
    with tempfile.TemporaryDirectory() as d:
        old = "https://example.com/eo-signed"
        new = "https://example.com/eo-challenged-in-court"
        write_digest(d, "2026-06-03", [("EO Signed", old)])
        write_digest(d, "2026-08-18", [("EO Challenged", new), ("EO Signed", old)])
        paths = sorted(os.path.join(d, f) for f in os.listdir(d))
        ledger = build_url_ledger(paths)
        if normalize_url(new) not in ledger or normalize_url(old) not in ledger:
            return record("S3 delta survives", inj, False,
                          "PROBE BROKEN: fixture URLs missing from ledger")
        cls, ev = classify([old, new], "2026-08-14", "2026-08-20", ledger)
        ok = cls == CLASS_DELTA and ev["first_seen"] == "2026-06-03" \
            and new in ev["fresh_urls"] and old in ev["stale_urls"]
        record("S3 delta survives", inj, ok,
               f"->{cls}, first_seen {ev['first_seen']}, "
               f"{len(ev['fresh_urls'])} fresh/{len(ev['stale_urls'])} stale")


# --------------------------------------------------------------------------
# S4: HUM vs REPRINT boundary. Must be driven by day count, and the harness
# must exercise BOTH sides of the threshold or it proves nothing.
# --------------------------------------------------------------------------
def s4_hum_threshold():
    inj = f"pre-window URL on {HUM_MIN_DAYS} days vs on 1 day"
    with tempfile.TemporaryDirectory() as d:
        hum = "https://example.com/daily-drumbeat"
        rep = "https://example.com/one-off-reprint"
        write_digest(d, "2026-06-01", [("Drumbeat", hum), ("OneOff", rep)])
        window_days = ["2026-08-14", "2026-08-15", "2026-08-16", "2026-08-17",
                       "2026-08-18", "2026-08-19", "2026-08-20"]
        for i, day in enumerate(window_days):
            stories = [("Drumbeat", hum)] if i < HUM_MIN_DAYS else []
            if i == 0:
                stories.append(("OneOff", rep))
            write_digest(d, day, stories or [("Filler", f"https://example.com/f{i}")])
        paths = sorted(os.path.join(d, f) for f in os.listdir(d))
        ledger = build_url_ledger(paths)
        hits = len(ledger[normalize_url(hum)].days_in_window("2026-08-14", "2026-08-20"))
        if hits != HUM_MIN_DAYS:
            return record("S4 hum/reprint threshold", inj, False,
                          f"PROBE BROKEN: drumbeat on {hits} days, expected {HUM_MIN_DAYS}")
        c_hum, _ = classify([hum], "2026-08-14", "2026-08-20", ledger)
        c_rep, _ = classify([rep], "2026-08-14", "2026-08-20", ledger)
        ok = c_hum == CLASS_HUM and c_rep == CLASS_REPRINT
        record("S4 hum/reprint threshold", inj, ok,
               f"{hits}-day->{c_hum}, 1-day->{c_rep}")


# --------------------------------------------------------------------------
# S5: Defect B. Window must come from the digests, never from ISO week.
# Terra's no-op warning: computing the expectation with the same faulty helper
# makes this pass vacuously. Expected literals are hardcoded.
# --------------------------------------------------------------------------
def s5_window_from_digests():
    inj = "Fri..Thu digest set whose ISO week is a different Mon..Sun range"
    paths = [f"digests/2026-08-{d}.md" for d in
             ["14", "15", "16", "17", "18", "19", "20"]]
    start, end = window_from_digests(paths)
    title = format_window_title(start, end)
    import datetime as dt
    iso_mon = dt.date.fromisocalendar(2026, 34, 1).isoformat()
    if iso_mon != "2026-08-17":
        return record("S5 window from digests", inj, False,
                      f"PROBE BROKEN: ISO W34 Monday is {iso_mon}, fixture assumes 2026-08-17")
    ok = (start, end) == ("2026-08-14", "2026-08-20") and title == "Aug 14 – Aug 20"
    record("S5 window from digests", inj, ok,
           f"derived '{title}' (ISO W34 would have said Aug 17 – Aug 23)")


# --------------------------------------------------------------------------
# S6: parser must read BOTH citation shapes. grok: if the archive parser only
# walks "Sources:", first_seen skews young and the gate under-reports.
# --------------------------------------------------------------------------
def s6_both_citation_shapes():
    inj = "stale URL present ONLY in TL;DR '([x](u))' form, not 'Sources:'"
    with tempfile.TemporaryDirectory() as d:
        only_tldr = "https://example.com/tldr-only-story"
        write_digest(d, "2026-07-04", [("TLDR Only", only_tldr)], bullet_style=False)
        parsed = parse_digest(os.path.join(d, "2026-07-04.md"))
        if not parsed.items:
            return record("S6 both citation shapes", inj, False,
                          "PROBE BROKEN: fixture digest parsed to zero items")
        ledger = build_url_ledger([os.path.join(d, "2026-07-04.md")])
        found = normalize_url(only_tldr) in ledger
        record("S6 both citation shapes", inj, found,
               f"TL;DR-only URL {'found' if found else 'MISSED'} in ledger "
               f"({len(ledger)} URLs from {len(parsed.items)} items)")


# --------------------------------------------------------------------------
# S7: hub pages must never become stories. The Aug-16 root cause.
# --------------------------------------------------------------------------
def s7_hub_rejection():
    inj = "'Anthropic Newsroom' landing page presented as a story"
    with tempfile.TemporaryDirectory() as d:
        write_digest(d, "2026-08-16", [
            ("Anthropic Newsroom", "https://www.anthropic.com/news"),
            ("Real Story", "https://www.anthropic.com/news/some-actual-post"),
        ])
        parsed = parse_digest(os.path.join(d, "2026-08-16.md"))
        if len(parsed.items) != 2:
            return record("S7 hub rejection", inj, False,
                          f"PROBE BROKEN: parsed {len(parsed.items)} items, expected 2")
        hubs = [i for i in parsed.items if i.is_hub]
        reals = [i for i in parsed.items if not i.is_hub]
        ok = len(hubs) == 1 and len(reals) == 1 and hubs[0].headline == "Anthropic Newsroom"
        record("S7 hub rejection", inj, ok,
               f"{len(hubs)} hub / {len(reals)} real correctly separated")


# --------------------------------------------------------------------------
# S8: continuity with prior roundups (Brian's addition). Must detect that a
# story was already covered in an earlier weekly, and must not false-positive.
# --------------------------------------------------------------------------
def s8_prior_week_continuity():
    inj = "URL cited in a prior weekly/*.md, plus an uncited control URL"
    with tempfile.TemporaryDirectory() as d:
        covered = "https://example.com/ongoing-saga"
        uncovered = "https://example.com/never-mentioned"
        with open(os.path.join(d, "2026-W33.md"), "w") as f:
            f.write("# AI Weekly Roundup — Week of Aug 7 – Aug 13\n\n"
                    f"Something happened. ([Src]({covered}))\n")
        with open(os.path.join(d, "2026-W34.md"), "w") as f:
            f.write("# AI Weekly Roundup — Week of Aug 14 – Aug 20\n")
        priors = load_prior_weeks(d, "2026-W34", limit=4)
        if not priors or priors[-1].slug != "2026-W33":
            return record("S8 prior-week continuity", inj, False,
                          f"PROBE BROKEN: priors={[p.slug for p in priors]}")
        if normalize_url(covered) not in priors[-1].urls:
            return record("S8 prior-week continuity", inj, False,
                          "PROBE BROKEN: injected URL absent from parsed prior week")
        hit = continuity_for([covered], priors)
        miss = continuity_for([uncovered], priors)
        ok = len(hit) == 1 and hit[0]["slug"] == "2026-W33" and len(miss) == 0
        record("S8 prior-week continuity", inj, ok,
               f"covered->{[h['slug'] for h in hit]}, control->{len(miss)} hits")


# --------------------------------------------------------------------------
# S9: META. Prove the harness itself can fail. If a deliberately broken gate
# still shows all-green, every result above is worthless.
# --------------------------------------------------------------------------
def s9_harness_can_fail():
    inj = "gate stubbed to always return NEW; S1 must go red"
    import weekly_ledger
    real = weekly_ledger.classify
    try:
        weekly_ledger.classify = lambda *a, **k: (CLASS_NEW, {
            "fresh_urls": [], "stale_urls": [], "first_seen": None,
            "days_in_window": []})
        globals()["classify"] = weekly_ledger.classify
        before = len(RESULTS)
        s1_exact_stale_replay()
        caught = (len(RESULTS) > before) and (RESULTS[-1][2] is False)
        RESULTS.pop()  # discard the sabotage run's result
    finally:
        weekly_ledger.classify = real
        globals()["classify"] = real
    record("S9 harness can fail (meta)", inj, caught,
           "sabotaged gate correctly produced a FAIL"
           if caught else "SABOTAGE NOT DETECTED: harness is vacuous")


SCENARIOS = [
    s1_exact_stale_replay, s2_no_false_positives, s3_delta_survives,
    s4_hum_threshold, s5_window_from_digests, s6_both_citation_shapes,
    s7_hub_rejection, s8_prior_week_continuity, s9_harness_can_fail,
]


def main() -> int:
    for fn in SCENARIOS:
        try:
            fn()
        except Exception:
            record(fn.__name__, "n/a", False,
                   "EXCEPTION: " + traceback.format_exc().strip().splitlines()[-1])

    passed = sum(1 for *_, ok, _ in RESULTS if ok)
    total = len(RESULTS)
    width = max(len(s) for s, *_ in RESULTS)
    print(f"\n{'SCENARIO'.ljust(width)}  RESULT  DETAIL")
    print("-" * (width + 60))
    for scenario, injection, ok, detail in RESULTS:
        print(f"{scenario.ljust(width)}  {'PASS  ' if ok else 'FAIL  '}  {detail}")
        print(f"{''.ljust(width)}          injected: {injection}")
    print("-" * (width + 60))
    print(f"{passed}/{total} scenarios passed")
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
