# Asset Quality Templates

[English](README.md) | [简体中文](README.zh-CN.md)

Use [model.plan.json](model.plan.json) for a self-contained GLB capture or [images.plan.json](images.plan.json) for existing views. Copy a plan into the game project and replace the example paths, intended use, calibration, and acceptance criteria. Read the [quality workflow](../../adapters/assets/quality-review.md) before interpreting results.

Run `collect` to generate a review template with unknown entries. Keep it unknown until the evidence has actually been inspected. Required checks and view directions should reflect the asset's use. A character's front and side must not be compared with same-view silhouette IoU.

The image template has no calibration by default, so measurements remain unknown. Add shared camera/scale information only when supported by the source. To link input preparation, add `preparation` and map each mandatory requirement to a mandatory criterion or an explicit later gate.
