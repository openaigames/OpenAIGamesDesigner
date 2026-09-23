"""Record and link checks do not execute commands or infer quality."""
from pathlib import Path
import contextlib
import io
import json
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import validate_records as records


class RecordTests(unittest.TestCase):
    def test_nonempty_summaries_do_not_claim_document_content_validation(self):
        # Structurally valid links and summaries cannot establish adequate design facts.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            for name in records.PROJECT_ENTRIES:
                (root / name).write_text("# 摘要\n已完成。\n", encoding="utf-8")
            management = root / records.PROJECT_ENTRIES[0]
            management.write_text("\n".join(
                f"[{name}](<{name}>)" for name in records.PROJECT_ENTRIES[1:]
            ), encoding="utf-8")
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                result = records.main(["--project", str(root), "--layout", "--markdown"])
            report = json.loads(output.getvalue())
            self.assertEqual(result, 0)
            self.assertEqual(report["errors"], [])
            self.assertEqual(report["document_content_validation"], "not_performed")
            self.assertEqual(report["quality_validation"], "not_performed")

    def test_schema_rejects_bad_types_missing_fields_and_unknown_keywords(self):
        self.assertTrue(records.contract("project", {"schema_version": True, "engine": "godot", "engine_root": "."}))
        self.assertTrue(records.contract("project", {"schema_version": 1, "engine": "unknown", "engine_root": "."}))
        self.assertTrue(records.contract("asset-job", {}))
        self.assertTrue(records.validate("text", {"unsupported": True}))
        self.assertEqual(records.contract("project", {"schema_version": 1, "engine": "godot", "engine_root": "."}), [])

    def test_relative_links_and_project_escape(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp).resolve()
            folder = root / "design"
            folder.mkdir()
            target = root / "notes.md"
            target.write_text("design")
            doc = folder / "spec.md"
            doc.write_text("[notes](../notes.md) [web](https://example.com) [section](#rules)")
            self.assertEqual(records.markdown_errors(root, [doc]), [])
            target.unlink()
            self.assertTrue(records.markdown_errors(root, [doc]))
            with self.assertRaises(ValueError): records.contained(root, "../outside")


if __name__ == "__main__":
    unittest.main()
