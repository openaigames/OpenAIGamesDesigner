"""Record and link checks do not execute commands or infer quality."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import validate_records as records


class RecordTests(unittest.TestCase):
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
