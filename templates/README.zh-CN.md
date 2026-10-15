# 模板与工程案例

[English](README.md) | [简体中文](README.zh-CN.md)

模板提供可编辑起点。生成的玩法规则、资源、配置与存档字段归项目所有，不要求已有工程迁移到示例结构。通过对应工具在新目录创建工程，不直接把模板目录当作完成的游戏运行。

| 目录或文件 | 用途与入口 |
| --- | --- |
| asset_preparation/ | [资产要求与生成输入示例](asset_preparation/README.zh-CN.md) |
| asset_iteration/ | [评审结果驱动的调整计划](asset_iteration/README.zh-CN.md) |
| project-management.md、task.md、feature-spec.md、asset-spec.md、decision.md、validation-report.md | 项目、任务、规格、决定与验证记录；[工作流](../workflows/README.zh-CN.md) |
| milestones/ | 原型、垂直切片、内容制作里程碑 |
| runtime_examples/ | training / puzzle 基础灰盒工程；[core](../adapters/engines/runtime_components/README.zh-CN.md) |
| runtime_input/、runtime_state/ | [输入](../adapters/engines/runtime_components/INPUT.zh-CN.md)、[设置与状态](../adapters/engines/runtime_components/STATE.zh-CN.md) |
| runtime_feedback/、runtime_interaction/、runtime_navigation/ | [反馈](../adapters/engines/runtime_components/FEEDBACK.zh-CN.md)、[交互](../adapters/engines/runtime_components/INTERACTION.zh-CN.md)、[导航](../adapters/engines/runtime_components/NAVIGATION.zh-CN.md) |
| procedural/、runtime_scene/、runtime_static/ | [生成规格](../adapters/processing/PROCEDURAL.zh-CN.md)、[通行](../adapters/engines/runtime_components/SCENE.zh-CN.md)、[旧单网格替换](../adapters/engines/runtime_components/STATIC_ASSETS.zh-CN.md) |
| motion/、motion_playback/ | [动作加工配置](../adapters/processing/MOTION.zh-CN.md)、[播放模板](motion_playback/README.zh-CN.md) |
| engineering_example/ | [组合工程](engineering_example/README.zh-CN.md)，需已采用角色 revision/bindings |
| static_scene/ | 原创几何夹具、替换配置及[组合接收配方](../adapters/engines/static_scene/RECEPTION.zh-CN.md)；原第三方美术需由项目合法提供 |

生成工具将组件复制到新工程。已有游戏保留自己的副本，通过[显式迁移](../docs/INSTALLATION.zh-CN.md)更新，并按项目重新验证。

[资产质量模板](asset_quality/README.zh-CN.md)提供证据采集、标定视图比较和明确评审条件的计划示例。
