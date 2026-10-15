# Project Overview

[English](README.md) | [简体中文](README.zh-CN.md)

OpenAIGamesDesigner is an open-source game development toolkit for AI agents and game developers. It combines specialist methods, production workflows, command-line tools, and engine adapters for creating prototypes, taking over existing projects, producing assets, changing features, and validating delivery.

## Project Structure

| Directory | Purpose |
| --- | --- |
| [skills](../../skills/README.md) | Specialist methods for design, art, animation, audio, engineering, and testing |
| [workflows](../../workflows/README.md) | Development stages from project definition to delivery; enter at any applicable stage |
| [tools](../../tools/README.md) | Project execution, workbench, asset jobs, numerical exchange, and checks |
| [adapters](../../adapters/README.md) | Engines, asset generation services, and local processing tools |
| [templates](../../templates/README.md) | Project documents, asset specifications, runtime components, and example projects |
| [schemas](../../schemas/README.md) | Formats for configuration, tasks, assets, and execution records |
| [tests](../../tests/README.md) | Automated checks, behavioral scenarios, and native-tool validation |

## Using the Toolkit

Start with an idea, existing designs, available assets, or a game already in development. The agent selects relevant skills and tools, keeping designs, editable sources, engineering changes, and validation results in the game's directory.

Specialist skills work independently. Copy runtime components into a game as needed: Godot uses project scripts and UE uses project plugins. The project defines its own input actions, rules, save fields, assets, and character bindings. Updating the toolkit does not automatically change existing games.

Adapters cover Godot, Unity, Unreal Engine, Three.js, and Phaser; see the [engine index](../../adapters/engines/README.md). Shared runtime components and animation playback provide Godot and UE 5.8 implementations. Other engines use their own adapter guides.

## Deliverables

Keep editable designs, asset sources, and game projects. Automated checks verify files, interfaces, and runtime behavior. Visuals, audio, controls, and target-platform performance need validation in the specific game. Example projects demonstrate module integration; their rules and art can be replaced.

Start with [installation](../INSTALLATION.md), or find a module in the [documentation index](../README.md).
