"""Archive folder tree: year split stays bounded and links resolve."""
import io
import re
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import build  # noqa: E402


def ent(slug):
    return {"slug": slug, "title": f"t {slug}", "read_min": 3,
            "meta": {"themes": {"agents": 1}, "diversity_warn": False,
                     "total_sources": 4, "sources": {}}}


SLUGS = ["2026-10-20", "2026-10-19", "2026-01-02", "2025-12-31",
         "2025-06-01", "2024-03-03", "2023-01-01"]


class ArchiveTreeTests(unittest.TestCase):
    def build(self, td):
        d = Path(td)
        (d / "archive").mkdir()
        (d / "archive" / "1999.html").write_text("stale")
        with patch.object(build, "DOCS_DIR", d), redirect_stdout(io.StringIO()):
            build.build_archive([ent(s) for s in SLUGS])
        return d

    def test_main_page_holds_only_hot_years(self):
        with tempfile.TemporaryDirectory() as td:
            main = (self.build(td) / "archive.html").read_text()
            self.assertEqual(re.findall(r'data-slug="([^"]+)"', main), SLUGS[:5])
            self.assertEqual(re.findall(r'href="(archive/\d+\.html)"', main),
                             ["archive/2024.html", "archive/2023.html"])
            self.assertEqual(re.findall(r'data-month="([^"]+)" open', main), ["2026-10"])

    def test_year_pages_written_and_stale_removed(self):
        with tempfile.TemporaryDirectory() as td:
            d = self.build(td)
            self.assertEqual(sorted(p.name for p in (d / "archive").glob("*.html")),
                             ["2023.html", "2024.html"])
            y = (d / "archive" / "2024.html").read_text()
            self.assertIn('href="../digests/2024-03-03.html"', y)
            self.assertIn('href="https://aigregator.news/archive/2024.html"', y)

    def test_terminal_archive_command_regex_still_matches(self):
        # templates/app.js doArchive() scrapes archive.html with this regex.
        with tempfile.TemporaryDirectory() as td:
            main = (self.build(td) / "archive.html").read_text()
            hits = re.findall(r'<a href="digests/([^"]+)\.html">([^<]+)</a>', main)
            self.assertEqual(len(hits), 5)


if __name__ == "__main__":
    unittest.main()
