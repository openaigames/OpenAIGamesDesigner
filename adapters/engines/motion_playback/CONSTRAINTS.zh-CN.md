# 可选脚部接触与握持

[English](CONSTRAINTS.md) | [简体中文](CONSTRAINTS.zh-CN.md)

下文引用的审计脚本保留在源码仓库，不随安装包分发。

使用 `constraints.mode = contacts_v1`。`feet` 和 `grip` 可以分别省略，不依赖根运动；适用于 Godot 和 UE 5.8 的原生动画播放。

## 接入位置

- Godot：`oagd_constraints.gd` 作为 `Skeleton3D` 的子 `SkeletonModifier3D`，在源动画之后修改原生骨骼；手动动画工程设置 skeleton 的 manual callback，先 `prepare()`，再推进动画与 `Skeleton3D.advance()`。在 `modification_processed` 读取最终骨骼。
- UE：`UOAGDConstraintsComponent` 管理输入、物理查询和道具；`FAnimNode_OAGDConstraints` 接在源姿态之后，`UAnimGraphNode_OAGDConstraints` 是可编辑的图节点。可在既有 AnimBP 中使用，不要求改为本工具的移动框架。查询在 PreUpdate 主线程执行，Evaluate 只读快照；骨骼最终刷新后附着道具并发布结果。
- `motion_playback.py create` 检查角色骨名及参数并生成独立 Contacts 示例。模板为 `constraints_main.gd` / `ConstraintsGame.*`。已有项目的 `stage` 只换资产；不能用它隐式安装新的项目代码。
- 创建示例需要既有 8 个基础动作，加上本例使用的 `hold`、`carry`。现有游戏可直接接运行组件，用自己的片段、输入和接触窗。

## 数据与职责

`feet`：pelvis、left/right 三段连续骨链；sole_offset_m、probe_up_m、probe_down_m、max_step_m、max_slope_deg、max_pelvis_m、blend_s；knee_pole 为角色局部 `[前,右,上]` 方向。探测使用世界上方向，接触目标按脚踝到脚底的实际距离校准。骨盆仅做有限的向下补偿；两段 IK 不拉长骨骼。

`grip`：main_hand、offhand 三段骨链、blend_s、elbow_pole；`sockets.godot` 和 `sockets.unreal` 各显式提供 main/support 的 `position` 与 `rotation_xyzw`。Godot 的原生位置单位为米，UE 为厘米；位置和旋转都是局部挂点值。两个导入器骨轴不同，不能直接复制四元数。main 是相对主手的道具姿态，support 是相对道具的辅助手姿态。挂点使用去掉骨骼缩放后的坐标系；道具自身几何尺寸不被骨骼缩放覆盖。

游戏每帧提供 grounded、左右 stance 权重和辅助手 contact。组件不猜测“哪个动作正在踩地或握住道具”；示例从实际片段时钟给出接触窗。站立双脚接触，行走只在已声明的支撑相启用。hold/carry 源动作已把双手放在身体前方，IK 只补接触差异。

Godot：`configure(actor, settings, excluded_rids)`；`prepare(dt, grounded, Vector2(left,right), contact)`；`take(prop, both)`、`release()`、`reset()`。

UE：`Configure(mesh, json)`；`Prepare(dt, grounded, contacts, contact)`；`Take(prop_component, both)`、`Release()`、`Reset()`。调用者必须在原生 Mesh 动画更新前提交本帧输入。

常规接触窗口通过 blend_s 混合进入／退出。显式取消、放下或目标消失立即撤销手部约束；道具保留释放时的世界姿态，后续掉落物理或库存规则由游戏负责。再次拿取建立新约束，不使用旧目标。单手不会启用辅助手 IK。

## 结果与限制

脚：disabled、contact、swing、airborne、no_ground、slope_limit、step_limit、unreachable。手：released、attached、single_hand、window_closed、contact、missing_target、unreachable。拒绝结果不会延长骨链；失去地面／支撑权重／腾空时释放接触。观察 weights、pelvis_offset / Result.Pelvis、goals 和实际骨骼，不能把目标位置当作已达到。

此模块范围是静态平面、有限坡度、有限台阶、双足三段骨链、主手附着的单／双手道具。UE 先用上一帧脚 XY 射线取得局部平面，再投影当前源姿态；台阶边缘有一帧查询延迟。快速跨越地形边界、移动平台、非均匀缩放骨架、四足、自动手指贴合、自碰撞消除和联网预测不在该约束实现的支持范围内。

示例的 step_down / foot_reach 使用固定高度的接触测试夹具，steep / high_step 使用对脚射线可见、对移动胶囊无阻挡的负例表面，用来独立覆盖回退。air_land 使用真实移动组件跳跃和落地。它们不表示已实现爬阶能力。根运动示例保留自己的移动所有权，跨模块组合需明确移动所有权，参见[组合示例](../../../templates/engineering_example/README.zh-CN.md)。

## 复现

`python tools/motion_playback.py create --project NEW_DIRECTORY --engine godot|unreal --revision VERIFIED_REVISION --bindings BINDINGS_JSON [--ue-root UE58_ROOT]`

执行生成工程中的原生 prepare 后运行。示例 E 拿取、Q 释放、Space 跳跃、WASD 移动；提供 report 参数时跑固定场景。`tests/scenarios/motion_constraints_audit.py REPORT BINDINGS --output AUDIT` 检查实际骨骼、骨段长度、接触误差、释放和异常回退。原生画面检查单独记录，脚本通过不等于成品动作或人工试玩认可。

Godot 的求值顺序和最终骨骼读回依据：[SkeletonModifier3D 官方文档](https://docs.godotengine.org/en/stable/classes/class_skeletonmodifier3d.html)。UE 节点依据本机 5.8 的 AnimNodeBase、BoneContainer、SkeletalMeshComponent 原生接口实现。
