# 角色配置与重定向

[English](CHARACTER_PROFILE.md) | [简体中文](CHARACTER_PROFILE.zh-CN.md)

角色配置集中保存骨骼映射、参考姿势、方向与接触校准参数，供离线加工与播放接入使用。
配置属于各自游戏工程。共享工具解析配置、执行重定向与受限修复，不持有全局角色表，也不决定游戏的攻击、任务或伤害规则。

## 使用入口

`tools/motion_workflow.py` 的 `process` 同时接受既有 `oagd.motion/1` 显式映射，以及引用 `oagd.character-profile/1` 的配置。旧配置不需要迁移。示例在 `templates/motion/character-profile.json`、`templates/motion/profile-motion.json`；先替换文件、骨架、哈希与实际校准参数。

```sh
python tools/motion_workflow.py validate --spec project/motion.json
python tools/motion_workflow.py process --blender BLENDER --spec project/motion.json --output NEW_REVISION
python tools/motion_workflow.py verify --output NEW_REVISION
```

`validate` 检查配置与文件身份；`process` 才读取真实骨架、求值并检查。输出目录不可覆盖，失败修订也保留。变更配置必须更新引用的 SHA-256 和修订号；引擎和游戏内证据需要重新取得。

## 一个配置包含什么

| 字段 | 含义 |
| --- | --- |
| `id`、`revision` | 项目自己的角色配置身份与正整数修订号 |
| `source`、`target` | 相对配置文件的资产路径、SHA-256、明确的 Armature 名称 |
| `roles` | 16 个基础人形角色的源／目标骨名；名字不用改成模板的骨名 |
| `coordinates` | 实际加工副本的单位、上向、解剖前向；当前要求米、Z 向上，允许水平 ±X／±Y 前向并计算对齐旋转 |
| `reference_pose` | 相对原始 bind rest 的局部四元数 `xyzw` 及校准依据；不修改原始 bind matrices、网格、骨长或权重 |
| `unmapped_bones` | 每根额外骨的明确处理：源 `ignore`、目标 `inherit_rest`；未知骨不能静默略过 |
| `root_motion` | 根位移所有者、是否原地、平移比例、允许平移的角色骨 |
| `clip_policies` | 每个动作的修复窗口、骨链、方向、预算与可选骨盆等固定平移校准 |
| `repair_budget` | 全片最大的世界位置变化、局部旋转变化和改动帧比例；独立于单条接触修复的局部预算 |

`roles` 为 root、hips、spine、head，以及左右 thigh、shin、foot、upperarm、forearm、hand。此便捷配置面向约定的人形结构；非人形仍用旧显式 motion 配置，不强制套入人形角色。骨名要求适用于当前 UE／Godot 示例的 ASCII 名称，同名大小写冲突拒绝。

源 `ignore` 表示没有直接的目标轨道；若它是映射骨的祖先，其运动仍会反映在该映射骨的实际全局求值中。目标 `inherit_rest` 继承真实父骨，保持自己的原始局部静止变换。当前没有自动扭转分摊、手指语义推断或自动权重修复；需要这些功能的骨架应先制作明确的导出骨架或使用专用流程。

## 参考姿势与校准

先由原始 rest 和声明的局部旋转重建源、目标参考姿势。对于每根映射骨，以“源当前全局旋转 × 源参考旋转的逆”取得相对运动，经过角色坐标对齐后施加到目标参考旋转，再还原目标父骨的局部旋转。目标骨长和 bind rest 不变。

`translation_offsets_m` 按角色名给出目标角色空间中的常量米制偏移，只允许 `translation_roles` 已列出的非根骨，例如骨盆。它属于参考校准，发生在修复基线之前。不得用它冒充动态 IK 或地形适配。前后修复报告不把已声明的参考校准计算成修复动作；配置及 `profile-diagnostics.json` 单独保留校准依据。

工具检查真实骨骼是否存在、映射祖先关系、左右肩／髋位置是否与前向声明一致、辅助骨处理是否完整。姿势匹配与前向仍需在真实网格上复核；骨架位置检查不能证明模型面部和脚尖一定朝向正确。

## 原地走跑的接触坐标

接触规则可以声明 `controller_velocity_mps: [x,y,0]`。它是该片段校准时约定的恒定控制器速度，坐标为目标 Blender 世界米制。仅允许 controller 所有、in_place 的动作使用非零值。

```text
目标脚踝位置(t) = 首个实际支撑样本位置 - 控制器速度 × (t - 首样本时间)
接触漂移 = 实际脚踝位置 + 控制器累计位移 - 首样本位置
```

求解器仅修改声明的三骨链及窗口和过渡边缘，保持骨长，用明确 pole 控制膝盖方向；不可达或超过位置／角度预算时拒绝。没有设置速度的旧规则仍沿用固定世界锚点。支撑窗口由项目提供，自动拟合或建议没有自动批准效力。

`tools/motion_playback.py::profile_settings` 可以从实际加工结果取得观察骨映射和 walk／run 接触速度。`checked_bindings` 拒绝与配置不一致的骨名和速度，避免离线修复以一种速度计算、游戏以另一种速度播放。当前可玩模板固定要求目标解剖前向为 Blender -Y，其他前向应先规范化副本；通用离线重定向不受这个模板约束。

这是恒定速度、平地、已声明支撑区间的离线校准。运行转向和混合见[连续移动](../engines/motion_playback/LOCOMOTION.zh-CN.md)；坡面接触见[脚部约束](../engines/motion_playback/CONSTRAINTS.zh-CN.md)。

## 修复范围与证据

每个动作输出原生求值的 before／after／source capture，以及 `*-repair-scope.json`。后者从实际 before／after 变换还原局部变化，检查未声明的骨与时间、局部平移、全局位置变化及改动帧比例；祖先修复引起的后代世界变化单列。仅有求解目标达标不能代替烘焙后的求值检查。

Godot 与 UE 原生回传独立读取导入资源，按相同接触坐标比较。实际运行另外测量世界空间脚部位置，不能把“加上假定控制器速度”的离线曲线当作游戏运行结果。蒙皮、脚底间隙和抬手方向继续查看真实画面。

29.97 等非整数采样率：离线／GLB 沿用已有显式时间轴处理；当前 UE FbxFactory 回传拒绝非整数采样率，可玩模板仍要求 30 或 60 fps。需要先用有记录的实际重采样转换，不能只改 FPS 标签。
