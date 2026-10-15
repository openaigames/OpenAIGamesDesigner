# Data Formats

[English](README.md) | [简体中文](README.zh-CN.md)

Schemas describe project configuration and records written by tools. Field names and schema identifiers define the interface between tools and project records.

| Group | Purpose |
| --- | --- |
| asset-evidence-plan, asset-quality-review | [Quality review](../adapters/assets/quality-review.md) |
| asset-iteration-plan | [Result-driven correction plans](../adapters/assets/result-iteration.md) |
| asset-requirements, asset-input-plan | Requirements, reference roles, input routes, and declared review; [input preparation](../adapters/assets/input-preparation.md) |
| project, run, engine-session | Project configuration, execution, and engine sessions |
| task, evidence, observation, observation-record, project-links | Tasks, evidence, observations, and file relationships |
| asset-job, artifact, asset-library | Asset jobs, outputs, and provenance |
| asset-versions, asset-taxonomy | Asset version relationships and classification |
| character-profile | Bone mappings, reference poses, and contact configuration; [character profiles](../adapters/processing/CHARACTER_PROFILE.md) |

Names refer to the `.schema.json` files in this directory. Input profiles, frozen scene plans, and other formats are validated by their own tools and format fields; not every JSON document has a schema here. See the [template index](../templates/README.md) for examples.

`validate_records.py` implements the limited set of keywords used by these schemas, not the entire JSON Schema specification. When adding fields or changing formats, update readers, writers, compatibility behavior, and tests together. Unknown keywords must not be silently ignored. File hashes identify content changes.
