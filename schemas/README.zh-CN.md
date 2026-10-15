# 记录格式与兼容性

[English](README.md) | [简体中文](README.zh-CN.md)

本目录维护共享 JSON 记录结构。工具拥有读取、验证和写入逻辑；schema 本身不执行引擎，也不判断美术品质或用户认可。

| 文件组 | 用途 |
| --- | --- |
| asset-evidence-plan, asset-quality-review | [质量评审](../adapters/assets/quality-review.zh-CN.md) |
| asset-iteration-plan | [评审结果驱动的调整计划](../adapters/assets/result-iteration.zh-CN.md) |
| asset-requirements、asset-input-plan | 资产要求、参考职责、落实路径与核对记录；[输入准备](../adapters/assets/input-preparation.zh-CN.md) |
| project、run、engine-session | 工程配置、命令执行与编辑器会话 |
| task、evidence、observation、observation-record、project-links | 阶段任务、证据、观察与文件关联 |
| asset-job、artifact、asset-library | 资产任务、产物与来源登记 |
| asset-versions、asset-taxonomy | 资产版本关系与分类 |
| character-profile | 角色骨骼、参考姿势与接触配置；[角色配置说明](../adapters/processing/CHARACTER_PROFILE.zh-CN.md) |

表中名称对应本目录的 .schema.json 文件。输入 profile、场景冻结计划等另由所属工具的版本字段及校验器维护，不能假定所有 JSON 都在这里有独立 schema。具体例子见 [模板索引](../templates/README.zh-CN.md)。

validate_records.py 解释当前 schema 使用的有限关键字，不是通用 JSON Schema 实现。新增字段或版本需同步读取/写入工具、旧数据兼容策略和相应测试；未知关键字不能静默忽略。文件哈希只用于识别版本变化。
