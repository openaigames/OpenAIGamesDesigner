# 资产质量模板

[English](README.md) | [简体中文](README.zh-CN.md)

自包含 GLB 使用 [model.plan.json](model.plan.json)，已有视图使用 [images.plan.json](images.plan.json)。复制到游戏工程后，替换示例路径、用途、标定和验收条件。解读结论前阅读[质量工作流](../../adapters/assets/quality-review.zh-CN.md)。

执行 `collect` 会生成全为未知的评审模板，实际查看证据后再填写。必需检查和视图方向应服务资产用途；不能用同视角轮廓 IoU 比较角色正面和侧面。

图片模板默认不含标定，测量会保留未知。有源相机或尺度依据后才能加入共同标定。要接入输入准备，加入 `preparation`，并将每个必需要求映射到必需检查项或明确的后续检查阶段。
