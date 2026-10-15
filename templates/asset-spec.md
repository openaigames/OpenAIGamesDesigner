# {{id}} — {{title}}

[English](asset-spec.md) | [简体中文](asset-spec.zh-CN.md)

- Type: asset delivery specification.
- Use, consuming character/scene/system, feature/task: to fill.
- State: to verify; acquisition, selection, production, import, and runtime checks are separate.

Retain applicable content only and follow existing project specifications/workflows.

## Goals and References

Record intended information/experience, agreed constraints, actual references, and borrowed ideas. State whether requirements or asset exploration led the task. Exploration may retain candidate roles without completing specs before searching. Separate reference images, usable sources, and authorization; unknowns remain open.

### Character and Motion Fit, If Relevant

| Decision | Evidence and conclusion |
| --- | --- |
| Roles and required behavior | Player/enemy interactions, information, responses; distinguish rules, asset-inspired candidates, hypotheses |
| Asset capability and design | Verified and unknown capabilities, intended gameplay and presentation, gaps and costs, next representative test |
| Fixed and adjustable conditions | Explicit goals/rules, delegated choices, provisional placeholders |
| Model, motion, equipment fit | Rig/body, pose/grip, movement/contact, readability evidence and unknowns |
| Mismatch route | Keep role and change assets, or retain assets and adjust design within authority; record reasons/gaps |
| Impact and representative checks | Affected rules/assets/consumers, sample findings, regression entry |

Reuse existing specs/decisions rather than another status table. Download/import success does not establish role fit. Choices beyond authority stay pending.

## Production and Delivery Contract

### Model and Skeleton Route, If Relevant

| Handoff item | Evidence, files/revisions, decision state |
| --- | --- |
| Route and style | Model-first rigging or authoring to existing rig/motion; actual choice/delegation, objects, style |
| Motion/rig baseline | Actual rig, mesh, clips, versions, licenses; playback quality, root/contact requirements, gaps |
| Proportions | Units, axes, reference pose, joint positions/distances; distinguish rig/mesh measurements, art targets, unknowns |
| Prompts/references | Proportions, length notes/measurements, necessary references; dimension lines optional; record actual transmitted inputs |
| Tools and limits | Selected generation/rigging interfaces, skeleton-constraint support, actual execution rather than platform claims |
| Calibration/binding | Mesh-to-rig differences, changes, skinning/rigid attachment, preserved sources/revisions |
| Dynamic validation | Representative motion, deformation/contact, actual consumers, unperformed checks, retest scope |

Reuse valid decisions/records. Equal height, matching bone names, and import success do not prove skinning/motion fit. See game-technical-art references/rig-aware-asset-production.md.

### Maps from Drawings to Models, If Relevant

| Handoff item | Evidence, files/revisions, decision state |
| --- | --- |
| Goal/spatial hypothesis | Player activities, structure, unknowns, valid designs, required judgment |
| Sketch/prototype observations | Chosen representations/areas/initial states, actual abilities/rules, expected versus observed; distinguish estimates, software input, player experience |
| Visual concept/blockout | Selected appearance, spatial functions/style, correspondence to playable space; visual selection is not layout acceptance |
| Production drawings | Needed region/plan/layer/elevation/section views with consistent IDs, axes, scale, assumptions; no mandatory complete set |
| Style | Theme versus representation, selection/delegation, excluded looks, placeholders |
| Performance conditions | Target device/platform/engine, resolution/quality/frame rate, unknowns, sample coverage |
| Modeling sample/comparison | Representative region, cameras/scale, geometry/material/light targets, actual comparisons/gaps |
| Resource strategy/retests | LOD/Nanite/instancing, collision/material/texture budget basis; source counts, persistence, visuals, frame time separately |
| Progress/regression | Authorized scope, sketch/drawing feedback, affected space/states/activities, retest evidence |

Unknowns remain pending; template examples are not user choices. Link existing map specs and update only affected content for local fixes.

### Resources and Delivery Records

| Resource/asset ID | Object/use | Name/revision, placeholder/final | Provenance/license/files | Selection | Production/import/validation |
| --- | --- | --- | --- | --- | --- |

Categories differ from formats. Use workbench file categories and object usage tags, referencing existing entries rather than duplicating them. Classify animated models versus standalone animation, and effects versus dependent textures, by actual content.

One row per resource; split long records by ID or use a property table for one item. Link authoritative inventories. Missing files/evidence stay pending, not invented links. Distinguish selected, produced, imported, and validated.

### Specification Constraints

| Item | Requirement/source | State/pending decision |
| --- | --- | --- |
| Sources/outputs | Editable source, formats, locations, revision relationships | To fill |
| Scale/structure | Dimensions, units, origin, orientation, atlases/materials/rigs | To fill |
| States/variants | Required states, versions, loops/transitions | To fill |
| Events/lifecycle | Start, sustain, end, cancel, corresponding rules/interfaces | To fill |
| Presentation/performance | Camera, resolution, load, justified budgets | To fill |
| Provenance/rights | Author/channel, URLs, authorization, restrictions | To fill |

Use professional references for applicable 2D/3D/UI/animation/VFX/audio constraints. Do not invent dimensions, counts, or budgets.

## Integration, Replacement, and Dependencies

Record source/native mappings, actual consumers, imports, IDs/attachments/events, and shared references. Preserve editable sources and real recovery baselines.

## Acceptance and Actual Delivery

| Layer | Method/expectation | Files/revisions/evidence | Result/limits |
| --- | --- | --- | --- |
| Source usability | According to actual type | To link | Unverified |
| Engine integration | Actual consumer and imports | To link | Unverified |
| Runtime presentation | Representative scenarios, dynamics/audio/load | To link | Unverified |

Link detailed validation reports. File existence, selected direction, import success, and runtime quality are separate conclusions.
