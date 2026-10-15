# Three.js · Web 3D

[English](README.md) | [简体中文](README.zh-CN.md)

This page covers project setup and execution. See [action timing](../action_timing/README.md) for event capture and comparison.

## Environment Setup

| Component | Configure | Check |
| --- | --- | --- |
| Node.js and npm / pnpm | Install Node compatible with the project's Vite; set node_executable and package_manager_cli | Query versions and install project dependencies |
| Framework and Vite dependencies | Install from the game's package.json directory using its lockfile | Build successfully and load the output in a browser |
| Browser | Open the development server or serve the exported directory over HTTP | Verify loading, controls, audio, and restart behavior |

Check Node compatibility against [Vite documentation](https://vite.dev/guide/) and the project's existing dependencies. No other game engine or dedicated framework MCP is required. Configure browser tools through the agent host.

The [framework entry](__init__.py) connects the selected `engine=threejs` to shared web execution. See [web execution](../web.md) for empty-project initialization, dependencies, the Vite server, and builds.

Three.js supplies rendering. Implement controls, collision, animation state, gameplay, and UI for the project. A visible image does not make a finished game. Retain existing web tools and lockfiles.

Use the host's real browser tools to test exported builds: input, canvas sizing, audio, load failures, console/resource errors, and restart behavior. Browser tools may be provided directly or through MCP. A connection alone does not mean gameplay has been tested. Command adapters preserve build and test reports.

Built-in smoke uses Playwright to load a selected build in a real browser, saving errors, screenshots, and resource hashes. See [browser check configuration](../web.md#browser-check-configuration). Gameplay behavior needs project-specific cases.
