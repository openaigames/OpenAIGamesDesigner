# Asset Evidence and Quality Review

[English](quality-review.md) | [简体中文](quality-review.zh-CN.md)

Collect repeatable evidence, compare calibrated views, and record explicit Agent judgments against a fixed rubric. Reports apply to particular files, references, and uses. A passing source review does not approve an asset for an engine or game.

The workflow follows [input preparation](input-preparation.md). It uses local files and does not submit generation jobs, read API keys, replace assets, or select a new asset version.

## Requirements

Run `tools/asset_quality.py` with Python 3.10+ and Pillow installed in that Python environment. Image collection accepts single-frame PNG, JPEG, and WebP files up to 16 million pixels each and 64 million pixels per collection, with normalized EXIF orientation. Supply transparent backgrounds or explicit foreground masks for silhouette measurements. An opaque image without a mask remains unmeasured.

Model capture additionally needs an installed Blender with the `BLENDER_EEVEE_NEXT` renderer. Pass its absolute executable path. Capture accepts self-contained GLB files with supported material/geometry extensions; external buffers, external textures, and unknown extensions are rejected. Convert other formats through the existing [processing tools](../processing/README.md) first and retain their dependencies.

## Collect and Review

Copy the [model or image plan](../../templates/asset_quality/README.md) into the project and replace its example paths, requirements, use, and environment. All project paths use forward slashes and stay inside the project. Each output directory must be new.

```sh
python tools/asset_quality.py --project MyGame capture --model assets/door.glb --blender "C:/Tools/Blender/blender.exe" --front=-Y --units meters --output evidence/door-capture
python tools/asset_quality.py --project MyGame collect --plan production/door-quality.json --output evidence/door-review
python tools/asset_quality.py --project MyGame assess --evidence evidence/door-review/evidence.json --review production/door-review.json --output evidence/door-assessment
python tools/asset_quality.py --project MyGame check --report evidence/door-assessment/quality.json
```

`collect` writes a contact sheet, measurements, findings, and a review template. Inspect the original images as well as the sheet; thumbnails may conceal defects. Copy `review-template.json` to the review path, name the actual reviewer, and replace unknown entries only after inspecting the cited evidence. Collection itself never supplies an artistic judgment.

`capture` freezes a copy of the source, renders front/right/back/left at one orthographic scale, and records cameras, bounds, evaluated vertex/triangle counts, materials as rendered, and Blender settings. Directions are object-relative: right is front × up; up is Blender +Z after GLB import. `--front` declares the source's forward axis; the tool cannot infer a character's face. `--units` labels the coordinate units used for measurements; it does not rescale geometry or verify the source's intended physical size. Leave it unknown when no scale basis exists.

The captures use EEVEE, AgX, fixed lighting, transparent backgrounds, and the first animation frame. They do not validate animation, deformation, engine materials, collision, or gameplay. They share a camera scale; the contact sheet fits thumbnails for display only. All measurements use the original pixels.

## Evidence Plan

The [plan schema](../../schemas/asset-evidence-plan.schema.json) defines:

- `asset_id`, `kind`, `use`, `environment`, and `files`: the reviewed source and its intended use. Include all dependencies needed to reproduce the asset.
- `views`: image IDs, paths, set names, directions, projection, optional segmentation, calibration, and landmarks. `capture` can append views and model metrics from a GLB capture.
- `required_views`: directions that must be present in each set. Missing directions remain pending; a reviewer cannot explain them away.
- `checks`: image measurements, each with a mandatory or preferred priority and a task-specific tolerance.
- `model_checks`: optional minimum/maximum bounds for `triangles`, `vertices`, `meshes`, or `size_x/y/z`. Dimension checks also require `units`; absent or incompatible units remain unknown.
- `criteria`: named Agent judgments, grouped into structure, style, readability, technical, or multiview dimensions. Describe observable expectations before reviewing.
- Optional `preparation`: a ready `preparation.json` from input preparation. Every mandatory requirement must map to a mandatory criterion through `requirement`, or appear in `deferred` with an `engine`/`game` gate and a reason. Deferred work remains visible and unverified.
- Optional `version`: `{ "group": "VG…", "version": "V…" }` pins an existing asset version. `files` must match its full snapshot. Changing the working source does not invalidate a review of an unchanged snapshot; changing the snapshot or its metadata does.
- Optional `media`: ID/path/type entries for local audio, video, or report evidence. These are hashed attachments; they are not automatically listened to, decoded, or assessed.

Prepared references remain linked to their frozen snapshots. A collection also hashes the current plan, source files, supplied images, masks, capture metadata, and contact sheet. Editing any of these requires a new collection. Reports additionally bind the filled review. Hashes establish freshness, not proof that a reviewer actually looked or listened.

## Multiview Measurements

| Measurement | Conditions and meaning |
| --- | --- |
| `height` | Relative height difference after conversion by declared pixels per unit; tolerance is a fraction |
| `baseline` | Difference in the silhouette's bottom height above the declared ground; tolerance is in calibration units |
| `landmark_height` | Vertical difference of the same named, visible landmark; normalized coordinates are declared by the reviewer, not detected automatically |
| `silhouette_iou` | Overlap ratio for the same view direction, canvas, calibration, and alignment; tolerance is the minimum acceptable overlap |

Calibrated comparisons need orthographic images from the same pose and coordinate group. Use a shared `calibration.group`, positive `pixels_per_unit`, and a pixel `baseline_y`. The group declaration also asserts compatible alignment. Derive these from camera records or measured reference scales. Do not invent calibration from independently fitted images. Perspective, missing masks, cropped silhouettes, or occluded landmarks produce unknown results.

Front and side silhouettes are not expected to match. They cannot pass a same-view IoU check. Exact duplicate or horizontally mirrored pixels across directions create review cues; symmetry can be legitimate. The reviewer must cite both views and explain the symmetry or confirm a defect. Lighting, pose, seams, handedness, identity, and hidden surfaces still need visual inspection. These checks do not reconstruct a 3D object from drawings or prove all views depict the same shape.

## Judgments and Scores

The [review schema](../../schemas/asset-quality-review.schema.json) requires every criterion exactly once, expected and observed behavior, confidence, and evidence IDs. Optional image regions use normalized `x`, `y`, `width`, and `height` coordinates within a cited image.

Use `pass` with score 3–4, `fail` with score 0–2, or `unknown` with a null score. Optional criteria may be `na` with a null score, evidence, and an explanation. Mandatory criteria cannot be waived. Low-confidence passes of mandatory criteria stay pending. The report shows each dimension's mean score and reviewed/total coverage; unknown entries never become zero or a pass. Scores summarize declared judgments and are not an automated perceptual rating.

An automatic mandatory failure or a confirmed multiview defect makes the external result `fail`. Missing mandatory evidence makes it `needs_review`. Aesthetic scores cannot compensate for either. A `pass` applies only to the stated external scope; deferred requirements, engine acceptance, and game acceptance remain separate.

## Asset Review Integration

To revise a failed result, use [result-driven iteration](result-iteration.md). It connects confirmed issues to input changes, requests evidence for unknowns, and compares subsequent results without weakening the rubric.

Start a testing record in the existing [asset review workflow](../../tools/workbench/README.md) with the same source files, use, and environment, then publish:

```sh
python tools/asset_quality.py --project MyGame publish --report evidence/door-assessment/quality.json --record REVIEW_RECORD_ID
```

This updates only the external/source-asset check: pass → pass, fail → fail, needs_review → blocked. It never qualifies the asset or marks the source-license, engine, or game gates as passed. The registry follows transitive evidence hashes; a changed reference, mask, render, review, or source invalidates a previous pass.

CLI exit codes are 0 for successful collection/publication or a passing report, 1 for fail/needs_review assessments, and 2 for invalid inputs or stale evidence. `quality.json` is the machine-readable conclusion; `report.md` is its readable companion. Keep the referenced project files with either report.

From the source repository, run reproducible synthetic cases through `python tests/scenarios/asset_quality_audit.py --output NEW_DIRECTORY`. They exercise the installed CLI with network calls denied and explicitly synthetic judgments. They do not certify production art. Run engine and gameplay acceptance through the corresponding project tools after source review.
