"""Observable new-project layout, preservation and portable handoff checks."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
import game_workflow as workflow
import validate_records as records
import package_skills


class IntakeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / "新游戏 with spaces"
        self.brief = "我想做一场第三人称 Boss 战，观察和应对后反击。"

    def call(self, *args):
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            return workflow.main([args[0], "--project", str(self.root), *args[1:]])

    def test_scaffold_saves_intent_without_engine_or_invented_rules(self):
        self.assertEqual(self.call("scaffold", "--brief", self.brief), 0)
        self.assertEqual({p.name for p in self.root.iterdir()}, set(records.PROJECT_ENTRIES))
        concept = (self.root / "Game Concept.md").read_text(encoding="utf-8")
        self.assertIn(self.brief, concept)
        self.assertEqual(records.layout_errors(self.root), [])
        self.assertEqual(records.markdown_errors(self.root, list(self.root.glob("*.md"))), [])
        for name in records.PROJECT_ENTRIES[2:]:
            body = (self.root/name).read_text(encoding="utf-8")
            self.assertIn("状态：待讨论", body)
            self.assertIn("## 后续补充条件", body)

    def test_existing_record_blocks_partial_scaffold_and_preserves_edits(self):
        self.root.mkdir(parents=True)
        concept = self.root / "Game Concept.md"
        concept.write_text("用户手写", encoding="utf-8")
        self.assertEqual(self.call("scaffold", "--brief", self.brief), 2)
        self.assertEqual(concept.read_text(encoding="utf-8"), "用户手写")
        self.assertFalse((self.root / "Project Management.md").exists())

    def test_existing_engine_root_is_not_reorganized(self):
        self.root.mkdir(parents=True)
        engine = self.root / "Existing.uproject"
        engine.write_text("{}")
        self.assertEqual(self.call("scaffold", "--brief", self.brief), 2)
        self.assertEqual({p.name for p in self.root.iterdir()}, {engine.name})
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(records.main(["--project", str(self.root)]), 0)
            self.assertEqual(records.main(["--project", str(self.root), "--layout"]), 1)

    def test_misplaced_engine_is_detected_even_without_config(self):
        self.call("scaffold", "--brief", self.brief)
        wrong = self.root / "outputs/Demo"
        wrong.mkdir(parents=True)
        (wrong / "Demo.uproject").write_text("{}")
        self.assertTrue(any("outside game" in e for e in records.layout_errors(self.root)))

    def test_production_requires_current_inputs_and_real_handoff_links(self):
        self.call("scaffold", "--brief", self.brief)
        self.assertTrue(records.layout_errors(self.root, production=True))
        for name in ("Game Design Document.md", "Technical Design.md"):
            (self.root / name).write_text("本次规则与实现依据", encoding="utf-8")
        self.call("document", "--kind", "prototype", "--id", "P001")
        self.call("document", "--kind", "task", "--id", "T001")
        self.assertTrue(records.layout_errors(self.root, production=True))
        management = self.root / "Project Management.md"
        with management.open("a", encoding="utf-8") as f:
            f.write("\n[原型](production/milestones/P001.md)\n[任务](production/tasks/T001.md)\n")
        management.write_text(management.read_text(encoding="utf-8").replace("当前里程碑：尚未建立", "当前里程碑：P001"), encoding="utf-8")
        self.assertEqual(records.layout_errors(self.root, production=True), [])
        (self.root / "production/tasks/T001.md").unlink()
        self.assertTrue(records.layout_errors(self.root, production=True))

    def test_any_existing_professional_entry_prevents_partial_overwrite(self):
        self.root.mkdir(parents=True)
        existing = self.root / "Art Direction.md"
        existing.write_text("用户提供的美术参考", encoding="utf-8")
        self.assertEqual(self.call("scaffold", "--brief", self.brief), 2)
        self.assertEqual({p.name for p in self.root.iterdir()}, {existing.name})
        self.assertEqual(existing.read_text(encoding="utf-8"), "用户提供的美术参考")

    def test_missing_or_unlinked_professional_entry_fails_layout(self):
        self.call("scaffold", "--brief", self.brief)
        art = self.root / "Art Direction.md"
        art.unlink()
        self.assertTrue(records.layout_errors(self.root))
        art.write_text("待讨论", encoding="utf-8")
        management = self.root / "Project Management.md"
        management.write_text(management.read_text(encoding="utf-8").replace("[Art Direction.md](Art%20Direction.md)", "美术待讨论"), encoding="utf-8")
        self.assertTrue(any("index must link" in e for e in records.layout_errors(self.root)))

    def test_closeout_rejects_initial_state_and_unlinked_evidence(self):
        self.call("scaffold", "--brief", self.brief)
        self.call("document", "--kind", "prototype", "--id", "P001")
        self.call("document", "--kind", "task", "--id", "T001")
        self.assertTrue(records.closeout_errors(self.root))
        (self.root/'game').mkdir()
        (self.root/'game/Probe.uproject').write_text('{}')
        report = self.root/'tests/reports/V001.md'
        report.parent.mkdir(parents=True)
        report.write_text("# 未完成的验证\n用户停止操作，尚无实际试玩结论。下次继续检查输入。", encoding='utf-8')
        management = self.root/'Project Management.md'
        text = management.read_text(encoding='utf-8')
        text = text.replace('项目阶段：待依据现有工程和用户目标判断', '项目阶段：原型验证中断')
        text = text.replace('本轮目标：澄清并推进用户提出的游戏需求，原话见概览', '本轮目标：记录本次中断与下一步')
        text = text.replace('工程入口：待按实际项目定位', '工程入口：[工程](game/Probe.uproject)')
        text += '\n[任务](production/tasks/T001.md)\n[原型](production/milestones/P001.md)\n[报告](tests/reports/V001.md)\n'
        management.write_text(text, encoding='utf-8')
        self.assertTrue(records.closeout_errors(self.root))
        for path in [self.root/'Risk & Assumption List.md', self.root/'production/tasks/T001.md', self.root/'production/milestones/P001.md']:
            relative = 'tests/reports/V001.md' if path.parent==self.root else '../../tests/reports/V001.md'
            with path.open('a',encoding='utf-8') as f: f.write(f'\n[中断证据]({relative})\n')
        self.assertEqual(records.closeout_errors(self.root), [])
        report.unlink()
        self.assertTrue(records.closeout_errors(self.root))

    def test_existing_asset_spec_location_is_preserved(self):
        old = self.root / "assets/specs"
        old.mkdir(parents=True)
        (old / "A001.md").write_text("existing")
        self.assertEqual(self.call("document", "--kind", "asset-spec", "--id", "A002"), 0)
        self.assertTrue((old / "A002.md").is_file())
        self.assertFalse((self.root / "design/assets").exists())

    def test_relocated_bundle_scaffold_and_validation_cli(self):
        bundle = package_skills.package(Path(self.temp.name) / "portable")
        self.assertFalse((bundle / "archive").exists())
        self.assertFalse(list(bundle.rglob("open_dashboard.py")))
        self.assertFalse(list(bundle.rglob("browser-dashboard.md")))
        self.assertFalse(list(bundle.rglob("logo.png")))
        runtime = bundle / "game-preproduction/runtime"
        self.assertFalse((runtime / "docs").exists())
        for relative in ("workflows/README.md", "tools/README.md", "adapters/README.md",
                         "adapters/engines/godot/README.md", "adapters/assets/README.md", "tests/README.md"):
            self.assertTrue((runtime / relative).is_file(), relative)
        runtime_markdown = list(runtime.rglob("*.md"))
        self.assertEqual(records.markdown_errors(runtime, runtime_markdown), [])
        def cli(script, *args):
            return subprocess.run([sys.executable, "-B", "-X", "utf8", str(runtime / "tools" / script),
                                   *args], cwd=self.temp.name, capture_output=True, text=True, encoding="utf-8", timeout=20)
        created = cli("game_workflow.py", "scaffold", "--project", str(self.root), "--brief", self.brief)
        self.assertEqual(created.returncode, 0, created.stderr)
        checked = cli("validate_records.py", "--project", str(self.root), "--layout", "--markdown")
        self.assertEqual(checked.returncode, 0, checked.stdout)
        self.assertTrue(json.loads(checked.stdout)["layout_checked"])
        self.assertEqual(json.loads(checked.stdout)["quality_validation"], "not_performed")


if __name__ == "__main__":
    unittest.main()
