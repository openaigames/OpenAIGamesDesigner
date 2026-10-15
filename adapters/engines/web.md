# Web Games: Three.js and Phaser

[English](web.md) | [简体中文](web.zh-CN.md)

Use Three.js for 3D web games and Phaser for 2D web games. Keep the framework and build system of an existing project. For new projects, choose the platform with the user before initialization; design, assets, and playtest goals follow the shared workflow.

## Initialize or Adopt

Save the six project entry documents and define the task. Choose one engine; do not initialize both in the same project:

```sh
python tools/game_workflow.py init --project "MyGame" --engine threejs --create-engine --node "C:/Tools/node/node.exe" --package-manager-cli "C:/Tools/node/node_modules/npm/bin/npm-cli.js"
```

For 2D, replace threejs with phaser. Existing projects omit --create-engine and point --engine-root at the actual package.json directory. Initialization creates an empty rendering entry, not gameplay, assets, or passed tests. Keep the six project documents at the project root and the web code in `game/`.

Node/package-manager paths must match the local machine. pnpm.cjs is supported; configure other managers through commands.prepare. Windows invokes package-manager JS with Node rather than relying on npm.cmd shell behavior. Generated package.json declares dependencies. Preserve the first lockfile, then use npm ci / pnpm frozen-lockfile. Existing projects are not upgraded automatically. Consult the matching Vite documentation for Node compatibility; path checks alone are insufficient.

## Commands and Evidence

| Action | Default | Meaning |
| --- | --- | --- |
| doctor | Check Node path and selected framework declaration | Readable configuration, not verified runtime/site |
| prepare | Install dependencies, respecting existing locks | Installation completed with actual logs |
| build / export | Local Vite into independent builds/run-id | Nonempty index.html and artifact hashes |
| play | Dev service at 127.0.0.1:5173; port conflicts fail | Long-running process; timeout stops it and remains timeout, not a playtest pass |
| smoke | Playwright loads an explicitly selected build | HTTP, console, resources, visible canvas, screenshot |
| test | Project test command | Real game assertions and reports required |

```sh
python tools/game_workflow.py run --project "MyGame" --action prepare --timeout 600
python tools/game_workflow.py run --project "MyGame" --action export --timeout 180
```

Use the [command/report contract](../README.md); commands override defaults. Test wrappers propagate failure and write summaries of actual results to {run}/test-results.json. Default browser smoke requires a build directory, Playwright, and browser. Behavioral tests require project commands/reports. Missing requirements produce blocked; builds do not substitute for browser/game tests.

Agents can manage development processes through terminal tools, recording working directory, command, URL, and shutdown, then open the URL in a browser. CLI play is for bounded sessions, not background service management. Do not load games through file://. Before delivery, serve the export over HTTP and check subpaths, asset requests, console, input, restart, and target devices. Starting a server is not public deployment; export does not deploy.

## Project Rules

- Three.js supplies rendering; implement input, characters, physics, animation state, and flow for agreed requirements without automatically adding a full framework.
- Phaser uses Scene, Loader, Input, and selected physics. A renderer startup is not a completed level/combat system.
- Technical documents record dependencies/locks, module responsibilities, and build/test entries. Art documents record actual assets, uses, formats, sources, and imports. Check load failures, texture/audio compatibility, canvas scaling, and download size.
- Project JSON may be the numerical source of truth. Reload and verify behavior after numerical exchanges. Record whether data is bundled at build time or fetched at runtime; table edits do not automatically update exported builds.

References: [Three.js manual](https://threejs.org/manual/), [Phaser installation](https://docs.phaser.io/phaser/getting-started/installation), [Vite requirements](https://vite.dev/guide/).

## Browser Check Configuration

Export first, then explicitly set web.smoke_root to the build being checked. The tool does not silently choose the latest directory:

```json
{
  "web": {
    "smoke_root": "C:/MyGame/builds/RUN_ID",
    "playwright_module": "C:/Tools/node_modules/playwright/index.js",
    "browser_executable": "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
    "smoke_seconds": 3
  }
}
```

Playwright and an actual Chromium-family browser are required and are not downloaded automatically. smoke binds a temporary random localhost port, checks HTTP/console/resource requests/nonempty visible canvas, saves browser-result.json, screenshots, and read-resource hashes, then closes browser/server. It does not prove correct canvas content or input/win/loss/restart behavior. Use commands.smoke for custom renderers, authenticated services, or non-canvas games.
