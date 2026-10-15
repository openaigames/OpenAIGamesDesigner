# Asset Input Examples

[English](README.md) | [简体中文](README.zh-CN.md)

Copy a specification and matching plan into your game project, adapt them to the actual brief, and use [input preparation](../../adapters/assets/input-preparation.md). These are editable examples, not approved requests. Review flags intentionally remain false.

| Pair | Demonstrates |
| --- | --- |
| [crate.spec.json](crate.spec.json), [crate.plan.json](crate.plan.json) | Text-to-model requirements and explicit exclusions |
| [door.spec.json](door.spec.json), [door.plan.json](door.plan.json) | Visual requirements with pending dimension, pivot, and collision checks |
| [icon.spec.json](icon.spec.json), [icon.plan.json](icon.plan.json) | Image input and small-size UI validation |
| [impact.spec.json](impact.spec.json), [impact.plan.json](impact.plan.json) | Sound description with a separate in-game timing check |
| [speech.spec.json](speech.spec.json), [speech.plan.json](speech.plan.json) | Literal spoken text; replace the voice ID with an accessible voice |
| [video.spec.json](video.spec.json), [video.plan.json](video.plan.json) | Camera, lighting, and exclusion requirements |

References must be actual project-local files. Declare their paths and roles in the specification, make explicit send/local-only decisions in the plan, and record observations for reference-routed requirements. Do not invent image evidence or treat generated views as verified geometry.
