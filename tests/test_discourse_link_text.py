"""Regression: Reddit flair like "[P]" in a title broke Discourse link parsing
and failed the 2026-10-18 digest ("Discourse rows differ from selected social records")."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from write_digest import render_discourse, safe_link_text  # noqa: E402
from validate_digest import links  # noqa: E402

URL = "https://www.reddit.com/r/MachineLearning/comments/1x8j8kg/17_ais_7700_hands_of_poker_frontier_vs_cheap_vs/"


def _rows(title, source="r/MachineLearning"):
    item = {"url": URL, "title": title, "source": source}
    out = render_discourse([item], {})
    return [l for l in out.splitlines() if l.startswith("- ")]


def test_trailing_flair_is_stripped_and_link_parses():
    rows = _rows("17 AIs, 7,700 hands of poker: frontier vs cheap vs local vs Jev [P]")
    assert len(rows) == 1
    assert links(rows[0]) == [URL]
    assert "[P]" not in rows[0]


def test_inner_brackets_are_neutralized():
    rows = _rows("[D] Is [this] the end of scaling?")
    assert links(rows[0]) == [URL]


def test_other_subreddit_row_also_parses():
    rows = _rows("Something [R]", source="r/somewhere")
    assert links(rows[0]) == [URL]


def test_safe_link_text_unit():
    assert safe_link_text("Title [P]") == "Title"
    assert safe_link_text("a [b] c") == "a (b) c"


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print("ok", name)
