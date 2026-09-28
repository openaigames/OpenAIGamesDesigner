"""The animation skill must ship and run without its former local install."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import package_skills
import check_installation
import run_tests


class AnimationPackageTests(unittest.TestCase):
    def test_animation_suite_is_discovered_and_bundle_runs_when_relocated(self):
        self.assertEqual(run_tests.suites()['game-animation-pipeline'],
                         ROOT / 'skills/game-animation-pipeline/scripts/tests')
        with tempfile.TemporaryDirectory() as temp:
            bundle = package_skills.package(Path(temp) / 'relocated bundle')
            skill = bundle / 'game-animation-pipeline'
            manifest = json.loads((bundle / check_installation.MANIFEST).read_text(encoding='utf-8'))
            for source in (ROOT / 'skills/game-animation-pipeline').rglob('*'):
                if not source.is_file() or '__pycache__' in source.parts or source.suffix == '.pyc':
                    continue
                packaged = skill / source.relative_to(ROOT / 'skills/game-animation-pipeline')
                self.assertEqual(packaged.read_bytes(), source.read_bytes())
                self.assertIn(packaged.relative_to(bundle).as_posix(), manifest['files'])
            entry = subprocess.run([sys.executable, '-B', '-I', str(skill / 'scripts/anim_pipeline.py'), '--help'],
                                   cwd=temp, capture_output=True, text=True, timeout=30)
            self.assertEqual(entry.returncode, 0, entry.stderr)
            tests = subprocess.run([sys.executable, '-B', '-I', str(skill / 'scripts/tests/test_pipeline.py'), '-q'],
                                   cwd=temp, capture_output=True, text=True, timeout=30)
            self.assertEqual(tests.returncode, 0, tests.stderr)
            self.assertNotIn('Ran 0 tests', tests.stderr)
            report = check_installation.check(bundle)
            self.assertEqual(report['missing'], [])
            self.assertEqual(report['changed'], [])


if __name__ == '__main__':
    unittest.main()
