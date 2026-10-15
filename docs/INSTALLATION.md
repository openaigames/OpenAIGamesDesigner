# Installation, Layout, and Migration

[English](INSTALLATION.md) | [简体中文](INSTALLATION.zh-CN.md)

## Three Locations

| Location | Contents | Updates |
| --- | --- | --- |
| Source checkout | Skills, tools, adapters, templates, documentation, and maintenance tests | Development changes and version control |
| Skill installation root | Sixteen skills, root LICENSE/README, and game-preproduction/runtime | Complete installation or an explicit update with backups; preserve unrelated skills and local files |
| Game project | Native project, rules, assets, configuration, saves, and pinned component copies | The game maintainer chooses when to install or migrate components |

The shared runtime is a toolkit resource directory, not shared writable state between games. Godot core lives in `addons/oagd`; UE core lives in `Plugins/OAGDCore`. Playback is a separate animation component.

## Install and Check

Run from the repository root with a new output directory:

```sh
python tools/package_skills.py --output dist/skills-bundle
```

Copy the complete output into the skill directory supported by your agent, then reload the skills. Include the reference files, scripts, and shared runtime alongside each `SKILL.md`. Run installed tools from `game-preproduction/runtime`:

```sh
python tools/check_installation.py --skills-root "SKILLS_ROOT"
```

Replace `SKILLS_ROOT` with the absolute path to the installation directory. `missing` lists absent manifest files, `changed` lists files differing from the bundle, and `extra` lists additional files under managed skills. Any nonempty list produces a nonzero exit code. Unrelated skills are excluded. A hash manifest identifies content; it does not certify behavior or quality.

Optional [asset quality tools](../adapters/assets/quality-review.md) need Pillow in the Python environment running them (`python -m pip install Pillow`). GLB evidence capture also needs an installed Blender. These dependencies are not embedded in the skill bundle.

## Update the Toolkit

Run `tools/bundle_upgrade.py` from the repository root or installed runtime. In the commands below, `BASE` is the previous unmodified bundle, `NEW` is the new bundle, and `INSTALLED` is your current installation. Replace these placeholders with actual paths; use new locations for `CANDIDATE` and `NEW_BACKUP`:

```sh
python tools/bundle_upgrade.py prepare --baseline BASE --new NEW --installed INSTALLED --output CANDIDATE
python tools/bundle_upgrade.py apply --candidate CANDIDATE --target INSTALLED --backup NEW_BACKUP
python tools/bundle_upgrade.py rollback --backup NEW_BACKUP
```

Inspect the candidate receipt and diff, then rehearse in an independent copy before applying. `prepare` preserves local overrides and rejects ambiguous text-patch context. File removal requires a separate migration. `apply` checks that the installation has not changed and backs up the files it writes. Rollback refuses to overwrite edits made after installation. Do not regenerate a manifest to conceal unreviewed modifications.

## Update Components in a Game

Inspect the pinned state, then select core and/or playback:

```sh
python tools/runtime_components.py status --project GAME
python tools/runtime_migration.py plan --project GAME --engine godot --packages core playback --plan review.json
python tools/runtime_migration.py apply --project GAME --plan review.json --receipt BACKUP_OUTSIDE_GAME
python tools/runtime_migration.py rollback --project GAME --receipt BACKUP_OUTSIDE_GAME
```

For UE, use `--engine unreal`. Substitute real paths and use new plan/receipt destinations. See [integration and migration](../templates/engineering_example/SUPPORT.md) for details. Migration compares the lock, upstream files, and project files; it does not replace game rules, character bindings, input configuration, or saves. After installing source files, connect actual consumers and run the game checks.

## Validate an Installation

Use the integrity command above and exercise the tools with an isolated game project. The installation contains skills, runtime tools, templates, necessary examples, documentation, and licenses. Maintenance tests, their fixtures, and scenario runners remain in the source repository; see [source testing](../tests/README.md). Internal review receipts, local logs, credentials, and development plans are excluded from both public source and installation packages.

For a distribution with removed files, install into a new directory and transfer reviewed local customizations. The additive upgrade tool rejects removals; copying over an older installation can leave obsolete files behind.
