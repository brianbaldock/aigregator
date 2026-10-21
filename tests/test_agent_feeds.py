"""Agent feeds: every story parsed, anchors resolve, license present."""
import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import agent_feeds as a  # noqa: E402

SITE = "https://aigregator.news"
FIXTURE = """# 2026-10-20 :: AI DAILY DIGEST

## ⚡ TL;DR
1. 16 🔥 🟡 **Skip Me.** Not a feed item. ([X](https://x.example/a))

## 🧠 Models & Releases
_1 item_
- 11 🔥🌱 🟡 ▤×2 🏷️ models, opensource **Model Ships.** Lab released it. Sources: [a.com](https://a.com/1), [b.com](https://b.com/2)

## 🛡️ Responsible AI, Safety & Policy
- 9 🟡 🏷️ policy **Rule Passes.** Body text. Sources: [Reuters](https://reuters.com/x)

## 📈 Prediction Markets
- **Will X?** - 10% Yes · [Polymarket](https://polymarket.com/event/x)

## 💬 Discourse
- [Thread title](https://www.reddit.com/r/x/comments/1/t/) Community discussion.
- [HN](https://example.org/story) Real headline here. Some note.
"""


class AgentFeedTests(unittest.TestCase):
    def test_parse_fixture(self):
        s = a.parse_stories(FIXTURE, "2026-10-20", SITE)
        self.assertEqual([x["title"] for x in s], ["Model Ships", "Rule Passes", "Thread title", "Real headline here. Some note."])
        self.assertEqual(s[3]["summary"], "via HN")
        self.assertEqual(a.section_anchor("🧠 Models & Releases"), "models-amp-releases")
        self.assertEqual(s[0]["source_count"], 2)
        self.assertEqual(s[0]["themes"], ["models", "opensource"])
        self.assertEqual(s[0]["section"], "models")
        self.assertEqual(s[1]["section"], "safety")
        self.assertEqual(s[2]["sources"][0]["name"], "reddit.com")
        self.assertNotIn("polymarket", json.dumps(s))

    def test_real_digests_lose_no_bullets(self):
        for f in sorted((ROOT / "digests").glob("*.md"))[-14:]:
            md = f.read_text(encoding="utf-8")
            key, expect = "", 0
            for line in md.splitlines():
                if line.startswith("## "):
                    key = a.section_key(line[3:])
                elif line.startswith("- ") and key and key not in a.SKIP_SECTIONS:
                    expect += 1
            with self.subTest(edition=f.stem):
                self.assertEqual(len(a.parse_stories(md, f.stem, SITE)), expect)

    def test_edition_anchors_exist_in_built_html(self):
        docs = ROOT / "docs" / "digests"
        for f in sorted((ROOT / "digests").glob("*.md"))[-7:]:
            html_path = docs / f"{f.stem}.html"
            if not html_path.exists():
                continue
            html = html_path.read_text(encoding="utf-8")
            for s in a.parse_stories(f.read_text(encoding="utf-8"), f.stem, SITE):
                anchor = s["edition_url"].split("#", 1)[1]
                with self.subTest(edition=f.stem, anchor=anchor):
                    self.assertIn(f'id="{anchor}"', html)

    def test_llms_txt_carries_license_terms(self):
        t = a.llms_txt(SITE)
        for needle in ("CC BY 4.0", "not covered by this license", "Polymarket", "14:00 UTC", "/feed.json"):
            self.assertIn(needle, t)


if __name__ == "__main__":
    unittest.main()
