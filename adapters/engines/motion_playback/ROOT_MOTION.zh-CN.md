# 地面根运动

[English](ROOT_MOTION.md) | [简体中文](ROOT_MOTION.zh-CN.md)

下文引用的审计脚本保留在源码仓库，不随安装包分发。

可选 `planar_v1` 模式把动画根骨的平移交给原生角色物理。普通原地动画继续由控制器移动；每个游戏保存自己的组件、动画图、角色和规则副本。

## 契约与范围

```json
"root_motion": {
  "mode": "planar_v1",
  "vertical": "physics",
  "rotation": "controller",
  "transition_s": 0.0
}
```

动画条目显式写 `motion_owner: "animation"`、`in_place: false`、`loop: false`。控制器条目保持 `controller / true`。检查加工报告、全部根轨迹样本和同一目标参考骨架；拒绝根高度变化、根旋转、零位移、循环根动作、混合层和连续 locomotion 图。根位移可在平面任意方向，开始动作前由项目确定角色朝向。

示例使用立即状态切换，避免混合尾部残余位移。翻滚的身体旋转写在髋部，根骨只提供地面轨迹；高度由重力和物理控制。这不是任意 3D 根变换、Motion Warping、网络同步或脚 IK。其他动作图可自行接入原生系统，需检查各自的位移提取和碰撞语义。

## 生成与接入

1. 通过已有 `motion_workflow.py process` 输出 `owner=animation, translation=scaled` 的独立动作版本。输入源可自行制作，必须保留实际根轨迹。
2. 用 `motion_root.py --base IN_PLACE_REVISION --rooted ROOT_REVISION --output NEW_COLLECTION` 合并同一目标骨架的已验证结果。原件不改动，片段分别保留根策略和依赖。
3. 完整 bindings 加入上述策略和根片段，用 `motion_playback.py create --engine godot|unreal --project NEW --revision NEW_COLLECTION --bindings BINDINGS [--ue-root UE_5.8]` 创建例子。模板还要求原八段基线动作及 animation-owned `dash`、`roll` 两段；这是样例约定，共享组件不限制其他动作名。
4. 原生 prepare 生成 AnimationTree 或 editable AnimBP。模板自动选择 Godot `root_main.gd` / UE `RootGame`。旧版角色资产更新仍可 stage → prepare → activate；根模式和旧模式之间禁止仅用 stage 偷换移动消费者，应新建例子或显式改造游戏代码。

`author_root_sample.py` 是针对已采用 Cesium 角色的可复现技术配方，非通用动作生成器。它保留原网格和权重，在源骨架实际写入冲刺／翻滚轨迹及姿态，并以求值后的蒙皮最低点校准髋高度。角色来源和许可仍随工程传递。

## Godot

`prepare.gd` 找到所有动作相同的根位置轨迹，设置 `AnimationTree.root_motion_track`。`OAGDPlayback.configure(tree, clips, {}, root_policy)` 检查立即切换图，动画由 `advance` 原生求值。非循环动作最后一帧按剩余时长截断，变速不多提取尾部距离。

`oagd_root_motion.gd`：`configure(playback, CharacterBody3D, Skeleton3D)`、`start(id, restart=false)`、`cancel()`、`prepare_step()`、`step(dt, controller_velocity)`。每个物理帧先 `prepare_step`，再决定控制器输入，最后调用一次 `step`。不要同时调用另一个 motor 的物理移动。根 delta 属于 Skeleton3D 坐标空间，必须包含导入对象的旋转和缩放；不能只用模型外层节点变换。实际接口语义参见 [Godot AnimationMixer 文档](https://docs.godotengine.org/en/stable/classes/class_animationmixer.html)。

## UE 5.8

根序列打开 `bEnableRootMotion`，使用第一帧根锁定，AnimInstance 使用 `RootMotionFromEverything`。原生 `CharacterMovement` 提取并消费 delta，项目不额外平移 Actor。`UOAGDRootMotionComponent` 管理控制权、取消缓存和末帧交还；其转换后回调读回实际提取量并限定平面，已有同类回调时 Configure 拒绝占用。

`RootGame` 构造时明确设 `bTickBeforeOwner=false`，移动组件依赖角色输入 tick，mesh 保持引擎原本的移动后求值关系。项目每帧先 `PrepareStep()`，再处理输入；Active 时不再 `AddMovementInput`。完成事件不立即取消，下一次 PrepareStep 再清理，因此最后一帧位移仍由物理消费。取消清空旧根缓存、速度及输入；重入从新代次开始，角色位置不回到动作起点。

## 验证与交付

模板接受 `--report=... --fps=60`（Godot）或 `-MotionReport=... -UseFixedTimeStep -FPS=60`（UE），执行 14 个项目场景：两种动作、斜向、撞墙、贴墙滑移、慢速、快速、途中变速、暂停、取消、重入、重启、完成后移动与移动中接管。键盘例子 E 冲刺、F 翻滚、Q 取消、WASD 移动；程序输入验证不是 OS 按键或人类试玩。

`tests/scenarios/motion_root_audit.py` 检查真实引擎报告中的胶囊位置、提取量、实际骨骼与事件，共 167 项断言。源工程、打包程序和接收工程必须分别运行；输出文件存在不等于通过。动作是技术样例，不宣称成品表演、任意角色适配、全姿态无穿模或碰撞胶囊随翻滚缩小。
