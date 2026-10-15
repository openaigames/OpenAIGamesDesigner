# 可选原生动作播放案例

[English](README.md) | [简体中文](README.zh-CN.md)

使用 `tools/motion_playback.py` 将模板复制到新工程。角色资产、映射、速度、输入和玩法规则由项目持有；已有项目通过 stage → 原生 prepare → activate 替换资产，组件代码按[安装与迁移](../../docs/INSTALLATION.zh-CN.md)更新。

| 示例 | 配置与行为 |
| --- | --- |
| [基础播放](../../adapters/engines/motion_playback/README.zh-CN.md) | 控制器负责移动，动画状态与事件由项目驱动 |
| [连续移动](../../adapters/engines/motion_playback/LOCOMOTION.zh-CN.md) | 配置加减速、转向速度、步态相位和跳落过渡；P 暂停人物 |
| [踏步转向](../../adapters/engines/motion_playback/TURNING.zh-CN.md) | 制作平地左右转向动作，校准停止与重新起步 |
| [动作分层](../../adapters/engines/motion_playback/LAYERS.zh-CN.md) | E 播放上半身手势，F 在站稳时触发全身手势，Q 取消 |
| [地面根运动](../../adapters/engines/motion_playback/ROOT_MOTION.zh-CN.md) | 显式策略选择 root_main.gd / UE RootGame，动画提供轨迹 |
| [脚 IK 与握持](../../adapters/engines/motion_playback/CONSTRAINTS.zh-CN.md) | constraints 选择 constraints_main.gd / UE ConstraintsGame；feet、grip 分别配置 |

每条路径需要匹配的动作、绑定与动画图。握持例使用 hold/carry 源动作，挂点按引擎导入结果校准。源 FBX 可嵌入支持的图像贴图；复杂材质节点仍需在原生画面中检查。

## 角色配置

将 [character_profile.example.json](character_profile.example.json) 中的 `observation_bones`、`movement_speeds_mps` 合并到完整的 playback bindings 文件。示例数值来自一个 CesiumMan 案例，不适用于任意角色。

- `observation_bones` 的 11 个 `dst_*` 键是稳定的报告角色，值才是实际骨骼名。必须完整、互异；根骨必须与加工结果一致。创建／暂存会检查实际逐帧捕获中是否存在这些骨骼，运行时也会检查原生骨架，缺失时失败退出。
- `movement_speeds_mps` 明确设置 walk/run 控制器速度，单位米／秒。应按实际重定向后的稳定支撑轨迹校准；不能用原角色的速度推断新角色无滑步。
- 省略两个字段时，保持原人偶骨骼名和 1／2.5 米／秒速度。此兼容默认值不适合其他骨架。
- 八段动作和事件、根运动所有权等原有字段仍必填。这两个新增字段不是完整的角色重定向配置系统；参考姿态偏差、接触漂移和复杂蒙皮另行校验。

## 项目制作注意

保留原始资产、许可、编辑源及处理报告。Godot 工程的制作源目录可使用 `.gdignore`，避免自动导入 `.blend`；导出预设需指向本机实际版本的 Windows 模板。UE 目标为 5.8，实际运行版本须记入证据。

导入成功、骨骼数值往返、自然运行、变形网格画面及人类试玩是不同的验证范围。脚部残差、未检查的蒙皮姿态以及源动作风格限制应明确写入项目说明。
