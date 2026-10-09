# 文件与数据约定

`source/` 保存可编辑场景与参考，`exports/` 保存 FBX，`capture/` 保存真实采样，`reports/` 保存诊断/录屏，`unreal/` 为独立工程。manifest 是当前任务动画/绑定权威数据；原游戏伤害数值仍由原系统负责。

## animlab.manifest/1

- space：此适配器统一为厘米、X 前/Y 右/Z 上、左手坐标、脚底地面原点。DCC 通过显式矩阵映射，不能把换算藏在挂点中。
- rig：实际 UE Mesh/Skeleton、FBX 参考。不得自动造一个相似骨架充当目标。
- root_motion_owner：character 或 animation；本版不支持双重主驱动。
- weapons：稳定 ID、持握骨、binding `{p,q,s}`、接触点、诊断几何段/半径和可见网格 sections。武器网格没有伤害职责。
- clips：稳定 ID、baseline/candidate、FBX、UE 资源、fps、duration_s、weapon_events、事件时点、目标距离、进入/退出姿态与 foot_contacts。
- foot_contacts：每项为 bone/start_s/end_s，表示作者声明的支撑区间；空数组代表未测脚滑，不代表整段脚掌贴地。
- tolerances：项目诊断阈值及校准状态。超过阈值指向需观察样本，不自动裁定艺术质量。
- evidence_dependencies：本工作区内的可编辑源、参考骨架/网格和 UE 资源文件路径。报告快照这些文件及 FBX 的哈希；评审之后任何变化都会使交接失效。

## animlab.capture/1

bones 按父骨在前排列，记录 name、parent 索引与 canonical 参考变换。clips.frames 记录严格递增的秒时钟、同序骨骼全局（角色地面空间）变换和武器变换。骨骼/武器必须在同一帧实际求值完成后取样，不能当前时间配上一帧姿态。weapon_id 支持连段换武器。stage 为 runtime_baseline、blender_source 或 unreal_roundtrip，分别来自真实运行和真实 DCC 求值，不能把分析器合成轨迹当作引擎采样。

p 单位厘米，q 顺序 x/y/z/w 且归一，s 为缩放。采样者记录构建、骨架和动画层；有角色整体运动时另存 actor 轨迹，不能归零掩盖位移问题。关闭整体位移或 AI 的采样只能说明对应局部动作，历史适配器的限制见 [采样范围说明](legacy-capture.md)。

## audit / review / handoff

audit 关联 manifest/capture/comparison 哈希和问题 ID/时点。代理碰撞可能误报，采样可能漏过快速交叉；需要实际蒙皮播放复查。

review 关联同版本清单/报告，填写观察者、每招决定、播放证据 evidence 路径数组、evidence_sha256 路径到哈希的映射与逐项豁免理由。过期证据、baseline、未做 UE 回传、缺少评审或未处理问题均使 gate 返回 2。它只输出交接计划，不覆盖游戏资产，也不代表真人手感认可。

测试场 B 保存 binding-draft，包含加载时的 manifest 快照。apply-binding 拒绝过期草稿，只写新清单版本。绑定修改后，重新观察并重新采样受影响动作。
