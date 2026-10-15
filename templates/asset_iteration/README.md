# Asset Iteration Plans

[English](README.md) | [简体中文](README.zh-CN.md)

Start with `asset_iterate.py draft` against a real quality report so issue IDs match its evidence. [prompt-plan.json](prompt-plan.json) illustrates a confirmed door-opening defect. Its paths and observations are examples; review flags intentionally remain false.

Copy the draft into the game project, select actual failed/unknown items, and record the correction and expected result. For an image-based route, replace the relevant reference and recheck its requirement routes instead of adding an unsupported prompt. For uncertain observations, use `collect_evidence` with tasks. See [result-driven iteration](../../adapters/assets/result-iteration.md) for commands, reference fields, comparisons, and stopping rules.

Keep outputs outside this template directory. A plan is not evidence of generation, processing, or acceptance.
