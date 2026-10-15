# Templates and Example Projects

[English](README.md) | [简体中文](README.zh-CN.md)

Templates provide editable starting points. Generated rules, assets, configuration, and save fields belong to the game project; existing projects do not need to adopt the examples' structure. Use the corresponding tools to create a new directory rather than treating a template directory as a finished game.

| Directory or file | Purpose and entry |
| --- | --- |
| asset_preparation/ | [Asset requirements and generation input examples](asset_preparation/README.md) |
| asset_iteration/ | [Review-driven correction plans](asset_iteration/README.md) |
| project-management.md, task.md, feature-spec.md, asset-spec.md, decision.md, validation-report.md | Project, task, specification, decision, and validation records; [workflows](../workflows/README.md) |
| milestones/ | Prototype, vertical-slice, and content-production milestones |
| runtime_examples/ | Training and puzzle grayboxes; [core](../adapters/engines/runtime_components/README.md) |
| runtime_input/, runtime_state/ | [Input](../adapters/engines/runtime_components/INPUT.md), [settings and state](../adapters/engines/runtime_components/STATE.md) |
| runtime_feedback/, runtime_interaction/, runtime_navigation/ | [Feedback](../adapters/engines/runtime_components/FEEDBACK.md), [interaction](../adapters/engines/runtime_components/INTERACTION.md), [navigation](../adapters/engines/runtime_components/NAVIGATION.md) |
| procedural/, runtime_scene/, runtime_static/ | [Generation specifications](../adapters/processing/PROCEDURAL.md), [traversal](../adapters/engines/runtime_components/SCENE.md), [single-mesh replacement](../adapters/engines/runtime_components/STATIC_ASSETS.md) |
| motion/, motion_playback/ | [Motion processing](../adapters/processing/MOTION.md), [playback templates](motion_playback/README.md) |
| engineering_example/ | [Combined project](engineering_example/README.md), requiring a verified character revision and matching bindings |
| static_scene/ | Original geometry fixtures, replacement configuration, and a [reception recipe](../adapters/engines/static_scene/RECEPTION.md); projects must supply authorized third-party art |

Generators copy components into new projects. Existing games keep their own copies, use [explicit migration](../docs/INSTALLATION.md) for updates, and validate the resulting integration.

See [asset quality templates](asset_quality/README.md) for evidence collection, calibrated view comparisons, and explicit review criteria.
