import importlib.util
import json
from pathlib import Path, PurePosixPath
import subprocess
import tempfile
import unittest
from urllib.parse import unquote


SPEC = importlib.util.spec_from_file_location(
    "build_site", Path(__file__).resolve().parents[1] / "tools" / "build_site.py"
)
site = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(site)


class BuildSiteTests(unittest.TestCase):
    def test_link_rewriting_preserves_fragments_and_external_urls(self):
        current = PurePosixPath("reports/company/main.md")
        destinations = {"reports/中文/a.md": PurePosixPath("reports/中文/a.md.html")}
        content = '<a href="../%E4%B8%AD%E6%96%87/a.md?q=1#分析">read</a>'
        self.assertIn("a.md.html?q=1#分析", site.rewrite_links(content, current, destinations))
        external = '<a href="https://example.com/a.md">external</a><a href="#local">local</a>'
        self.assertEqual(site.rewrite_links(external, current, destinations), external)

    def test_dates_are_valid(self):
        self.assertEqual(site.report_date("reports/company/20261002.md"), "2026-10-02")
        self.assertEqual(site.report_date("reports/2026-06-01/test.md"), "2026-06-01")
        self.assertEqual(site.report_date("reports/20260231.md"), "")

    def test_snapshot_excludes_ignored_files_and_renders_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output = root / "source", root / "output"
            source.mkdir()
            subprocess.run(["git", "init", "--quiet", str(source)], check=True)
            (source / "LICENSE").write_text("MIT test license", encoding="utf-8")
            reports = source / "reports"
            reports.mkdir()
            (reports / "tracked-private.md").write_text("private", encoding="utf-8")
            subprocess.run(
                ["git", "-C", str(source), "add", "--", "reports/tracked-private.md"], check=True
            )
            (source / ".gitignore").write_text(
                "reports/tracked-private.md\nreports/ignored.md\n", encoding="utf-8"
            )
            for name in ("portfolio-latest.md", "ignored.md"):
                (reports / name).write_text("private", encoding="utf-8")
            (reports / "code.py").write_text("do not publish", encoding="utf-8")
            company = reports / "中文"
            company.mkdir()
            (company / "report-20261002.md").write_text(
                "# 中文研究\n\n## 风险\n\n| A | B |\n|---|---|\n| 1 | 2 |\n\n"
                "[Next](other.md#结论)\n", encoding="utf-8"
            )
            (company / "other.md").write_text("# Other\n\n## 结论", encoding="utf-8")
            (company / "other.html").write_text(
                '<!doctype html><title>Designed</title><a href="other.md">Source</a>',
                encoding="utf-8",
            )
            entries = site.build(source, output)
            self.assertEqual(len(entries), 3)
            for name in ("portfolio-latest.md", "ignored.md", "tracked-private.md", "code.py"):
                self.assertFalse((output / "reports" / name).exists())
            page = (output / "reports" / "中文" / "report-20261002.md.html").read_text(encoding="utf-8")
            self.assertIn("<table>", page)
            self.assertIn('id="风险"', page)
            self.assertIn("other.md.html#结论", page)
            self.assertIn('name="viewport"', page)
            self.assertTrue((output / "reports" / "中文" / "index.html").is_file())
            self.assertTrue((output / "reports" / "中文" / "other.html").is_file())
            self.assertTrue((output / ".nojekyll").is_file())
            for entry in json.loads((output / "reports.json").read_text(encoding="utf-8")):
                self.assertTrue((output / unquote(entry["url"])).is_file())
            with self.assertRaisesRegex(ValueError, "empty"):
                site.build(source, output)


if __name__ == "__main__":
    unittest.main()
