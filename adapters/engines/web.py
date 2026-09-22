"""Three.js / Phaser projects using Node and project-local Vite.

Only dependency preparation, serving and bundling have defaults. Browser and
game tests require project-owned commands and real reports.
"""
import json
from pathlib import Path
from .common import configured

FRAMEWORKS = {"threejs": ("three", "0.186.0"), "phaser": ("phaser", "4.2.1")}
VITE_VERSION = "8.3.0"


def executable(config):
    path = Path(config.get("node_executable", ""))
    if not path.is_absolute() or not path.is_file():
        raise ValueError("node_executable must identify an existing absolute Node executable")
    return path.resolve()


def inspect(config, project):
    executable(config)
    package = json.loads((project / "package.json").read_text(encoding="utf-8-sig"))
    if not isinstance(package, dict):
        raise ValueError("package.json must be an object")
    dependencies = {**package.get("devDependencies", {}), **package.get("dependencies", {})}
    name, _ = FRAMEWORKS[config["engine"]]
    if not isinstance(dependencies.get(name), str) or not dependencies[name]:
        raise ValueError(f"package.json must declare the chosen framework: {name}")
    return {"engine": config["engine"], "project_version": dependencies[name],
            "version_source": str(project / "package.json"), "editor_version_verified": False,
            "dependency_installed": (project / "node_modules" / name / "package.json").is_file()}


def command(config, project, action, run, output):
    if action in config.get("commands", {}):
        return configured(config, action, project, run, output)
    node = str(executable(config))
    if action == "prepare":
        cli = Path(config.get("package_manager_cli", ""))
        if not cli.is_absolute() or not cli.is_file() or cli.name not in {"npm-cli.js", "pnpm.cjs"}:
            raise ValueError("Set package_manager_cli to an absolute npm-cli.js or pnpm.cjs; other managers use commands.prepare")
        if cli.name == "npm-cli.js":
            return [node, str(cli), "ci" if (project / "package-lock.json").is_file() else "install"]
        return [node, str(cli), "install", "--frozen-lockfile" if (project / "pnpm-lock.yaml").is_file() else "--no-frozen-lockfile"]
    if action in {"play", "build", "export"}:
        vite = project / "node_modules/vite/bin/vite.js"
        if not vite.is_file():
            raise ValueError("Project-local Vite is missing; prepare dependencies or configure a project command")
        if action == "play":
            return [node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"]
        # A unique build output outside the source avoids source-fingerprint churn.
        return [node, str(vite), "build", "--outDir", str(output)]
    return configured(config, action, project, run, output)


def starter(engine):
    """Return a blank rendering bootstrap, not invented game rules or art."""
    name, version = FRAMEWORKS[engine]
    package = {"name": "game-project", "version": "0.0.0", "private": True, "type": "module",
               "scripts": {"dev": "vite --host 127.0.0.1", "build": "vite build", "preview": "vite preview --host 127.0.0.1"},
               "dependencies": {name: version}, "devDependencies": {"vite": VITE_VERSION}}
    if engine == "threejs":
        main = """import * as THREE from 'three';
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x151b2e);
const camera = new THREE.PerspectiveCamera(60, 1, 0.1, 1000);
camera.position.z = 5;
const renderer = new THREE.WebGLRenderer({ antialias: true });
document.querySelector('#game').appendChild(renderer.domElement);
function resize() {
  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
  renderer.setSize(window.innerWidth, window.innerHeight);
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
}
window.addEventListener('resize', resize);
resize();
renderer.setAnimationLoop(() => renderer.render(scene, camera));
"""
    else:
        main = """import Phaser from 'phaser';
class MainScene extends Phaser.Scene {
  constructor() { super('main'); }
  create() { /* Add only the game's agreed objects, rules and assets here. */ }
}
new Phaser.Game({ type: Phaser.AUTO, parent: 'game', width: 960, height: 540,
  backgroundColor: '#151b2e', scene: MainScene,
  scale: { mode: Phaser.Scale.FIT, autoCenter: Phaser.Scale.CENTER_BOTH } });
"""
    return {"package.json": json.dumps(package, indent=2) + "\n", "src/main.js": main,
            "index.html": '<!doctype html>\n<html lang="en"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Game project</title><style>html,body,#game{margin:0;width:100%;height:100%;overflow:hidden;background:#151b2e}canvas{display:block}</style></head><body><div id="game"></div><script type="module" src="/src/main.js"></script></body></html>\n',
            "vite.config.js": "import { defineConfig } from 'vite';\nexport default defineConfig({ base: './' });\n",
            ".gitignore": "node_modules/\ndist/\n"}
