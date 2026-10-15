# Motion Processing Regression Recipes

[English](README.md) | [简体中文](README.zh-CN.md)

Use the [processing tools](../../../adapters/processing/MOTION.md) to create isolated character and animation revisions, then verify them through [native sampling](../../../adapters/engines/motion/README.md). Choose your own engine executables, source files, bone mappings, and output directories.

| Case | What to verify |
| --- | --- |
| Different proportions and reference poses | Retargeted joint orientation, reach, skin deformation, and root ownership |
| Axis, unit, and object-transform changes | Consistent world scale, facing, and sampled bone positions after import |
| FBX and GLB round trips | Preserved clips, timing, skinning, materials, and dependent files |
| Missing or ambiguous bones | Clear rejection before output is activated |
| Altered capture or source revision | Rejection of stale or mismatched evidence |

For playback integration, use the [multi-source regression recipe](../motion_regression.md) and [locomotion cases](../motion_locomotion.md). Keep source snapshots and compare actual native captures; use visual inspection to assess deformed meshes and natural movement.

See [testing](../../README.md) for automated checks and [installation](../../../docs/INSTALLATION.md) for supported update and rollback commands.
