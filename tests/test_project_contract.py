"""Guard the agreed toolkit layout and active local references against drift."""
from pathlib import Path
import re
import unittest
import tempfile
from document_links import local_reference_errors


ROOT = Path(__file__).resolve().parents[1]


class ProjectContractTests(unittest.TestCase):
    def test_agreed_public_structure(self):
        self.assertEqual(
            {p.parent.name for p in (ROOT / "skills").glob("*/SKILL.md")},
            {"game-preproduction", "game-concept", "game-design", "game-numerical-design", "game-art-direction",
             "game-technical-design", "game-prototype-validation", "game-animation-pipeline",
             "game-combat-design", "game-level-design", "game-technical-art", "game-character-art",
             "game-environment-art", "game-vfx-design", "game-audio-design", "game-ui-ux"},
        )
        self.assertEqual(
            {p.name for p in (ROOT / "workflows").glob("*.md")
             if p.name != "README.md" and not p.name.endswith('.zh-CN.md')},
            {"project-intake.md", "prototype-build.md", "vertical-slice.md",
             "feature-change.md", "asset-production.md", "delivery.md", "development-stages.md",
             "stage-execution.md", "content-production.md"},
        )
        self.assertEqual(
            {p.name for p in (ROOT / "templates").glob("*.md") if not p.name.endswith('.zh-CN.md')},
            {"README.md", "project-management.md", "task.md", "feature-spec.md",
             "asset-spec.md", "validation-report.md", "decision.md"},
        )
        self.assertEqual({p.name for p in (ROOT / 'templates').iterdir() if p.is_dir()},
                         {'milestones', 'engineering_example', 'motion', 'motion_playback', 'procedural', 'asset_preparation', 'asset_quality', 'asset_iteration',
                          'runtime_examples', 'runtime_feedback', 'runtime_input', 'runtime_interaction',
                          'runtime_navigation', 'runtime_scene', 'runtime_state', 'runtime_static', 'static_scene'})
        for name in ('prototype.md', 'vertical-slice.md', 'content-production.md'):
            self.assertTrue((ROOT / 'templates/milestones' / name).is_file(), name)

    def test_active_markdown_links_and_template_references(self):
        files = [ROOT / name for name in ("README.md", "README.zh-CN.md", "THIRD_PARTY_NOTICES.md", "THIRD_PARTY_NOTICES.zh-CN.md", "licenses/README.md", "licenses/README.zh-CN.md")]
        for folder in ("skills", "workflows", "templates", "tools", "adapters", "tests", "docs", "schemas"):
            files.extend((ROOT / folder).rglob("*.md"))
        missing = local_reference_errors(files)
        for path in files:
            content = path.read_text(encoding="utf-8-sig")
            for target in re.findall(r"`(templates/[^`\n]+\.md)`", content):
                if not (ROOT / target).is_file():
                    missing.append((str(path.relative_to(ROOT)), target))
        self.assertEqual(missing, [], "Active references must resolve; historical dist is excluded.")

    def test_link_check_detects_broken_sections_and_ignores_code_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            page = root / 'guide.md'
            page.write_text('# 接入 / 1\n# 接入 / 1\n<a id="old-anchor"></a>\n```md\n# 假标题\n[x](missing.md)\n```\n', encoding='utf-8')
            entry = root / 'README.md'
            entry.write_text('[one](guide.md#接入--1)\n[two](guide.md#接入--1-1)\n[old](guide.md#old-anchor)\n', encoding='utf-8')
            self.assertEqual(local_reference_errors([page, entry]), [])
            entry.write_text('[broken](guide.md#旧标题)\n[fake](guide.md#假标题)\n[missing](gone.md)\n', encoding='utf-8')
            self.assertEqual([row[3] for row in local_reference_errors([entry])], ['missing heading', 'missing heading', 'missing file'])

    def test_execution_structure_has_callable_entries(self):
        expected = ["tools/game_workflow.py", "tools/engine_workflow.py", "tools/asset_workflow.py", "tools/numeric_workflow.py", "tools/validate_records.py",
                    "tools/package_skills.py", "tools/asset_prepare.py", "tools/asset_quality.py", "tools/asset_iterate.py", "adapters/engines/godot/cli.py", "adapters/engines/unity/cli.py",
                    "adapters/engines/unreal/cli.py", "adapters/assets/hunyuan3d.py",
                    "adapters/assets/image_provider.py", "adapters/assets/audio_provider.py",
                    "adapters/processing/blender.py", "workflows/README.md", "tools/README.md",
                    "adapters/engines/godot/README.md", "adapters/assets/README.md", "adapters/README.md"]
        for name in expected:
            self.assertTrue((ROOT / name).is_file(), name)
        self.assertEqual({p.name for p in (ROOT / "schemas").glob("*.json")},
                         {"project.schema.json", "run.schema.json", "asset-job.schema.json", "artifact.schema.json", "engine-session.schema.json", "asset-library.schema.json",
                          "task.schema.json","evidence.schema.json","observation.schema.json","observation-record.schema.json","project-links.schema.json","asset-taxonomy.schema.json","asset-versions.schema.json","character-profile.schema.json",
                          "asset-requirements.schema.json", "asset-input-plan.schema.json", "asset-evidence-plan.schema.json", "asset-quality-review.schema.json", "asset-iteration-plan.schema.json"})


if __name__ == "__main__":
    unittest.main()
