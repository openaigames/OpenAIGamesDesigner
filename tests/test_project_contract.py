"""Guard the agreed toolkit layout and active local references against drift."""
from pathlib import Path
import re
import unittest
from urllib.parse import unquote


ROOT = Path(__file__).resolve().parents[1]


class ProjectContractTests(unittest.TestCase):
    def test_agreed_public_structure(self):
        self.assertEqual(
            {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")},
            {"game-preproduction", "game-concept", "game-design", "game-art-direction",
             "game-technical-design", "game-prototype-validation"},
        )
        self.assertEqual(
            {p.name for p in (ROOT / "workflows").glob("*.md") if p.name != "README.md"},
            {"project-intake.md", "prototype-build.md", "vertical-slice.md",
             "feature-change.md", "asset-production.md", "delivery.md"},
        )
        self.assertEqual(
            {p.relative_to(ROOT / "templates").as_posix()
             for p in (ROOT / "templates").rglob("*") if p.is_file()},
            {"project-management.md", "milestones/prototype.md", "milestones/vertical-slice.md",
             "task.md", "feature-spec.md", "asset-spec.md", "validation-report.md", "decision.md"},
        )

    def test_active_markdown_links_and_template_references(self):
        files = [ROOT / "README.md", ROOT / "THIRD_PARTY_NOTICES.md", ROOT / "licenses/README.md"]
        for folder in ("skills", "workflows", "templates", "tools", "adapters", "tests"):
            files.extend((ROOT / folder).rglob("*.md"))
        missing = []
        for path in files:
            content = path.read_text(encoding="utf-8-sig")
            for target in re.findall(r"\[[^\]\n]*\]\(([^)\n]+)\)", content):
                target = target.strip().split(' "')[0].strip("<>")
                if re.match(r"^[a-zA-Z][\w+.-]*:", target) or target.startswith("#"):
                    continue
                if "{{" in target:
                    continue
                target = unquote(target.split("#")[0])
                if target and not (path.parent / target).exists():
                    missing.append((str(path.relative_to(ROOT)), target))
            for target in re.findall(r"`(templates/[^`\n]+\.md)`", content):
                if not (ROOT / target).is_file():
                    missing.append((str(path.relative_to(ROOT)), target))
        self.assertEqual(missing, [], "Active references must resolve; historical dist is excluded.")

    def test_execution_structure_has_callable_entries(self):
        expected = ["tools/game_workflow.py", "tools/engine_workflow.py", "tools/asset_workflow.py", "tools/numeric_workflow.py", "tools/validate_records.py",
                    "tools/package_skills.py", "adapters/engines/godot/cli.py", "adapters/engines/unity/cli.py",
                    "adapters/engines/unreal/cli.py", "adapters/assets/hunyuan3d.py",
                    "adapters/assets/image_provider.py", "adapters/assets/audio_provider.py",
                    "adapters/processing/blender.py", "workflows/README.md", "tools/README.md",
                    "adapters/engines/godot/README.md", "adapters/assets/README.md", "adapters/README.md"]
        for name in expected:
            self.assertTrue((ROOT / name).is_file(), name)
        self.assertEqual({p.name for p in (ROOT / "schemas").glob("*.json")},
                         {"project.schema.json", "run.schema.json", "asset-job.schema.json", "artifact.schema.json", "engine-session.schema.json", "asset-library.schema.json"})


if __name__ == "__main__":
    unittest.main()
