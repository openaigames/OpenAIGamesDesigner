# 连续移动混合

[English](LOCOMOTION.md) | [简体中文](LOCOMOTION.zh-CN.md)

可选的 Godot AnimationTree 与 UE 5.8 AnimBP 实现。项目持有输入、速度、加减速、转向、跳落规则和资产；共享组件只接收实际水平速度并求值动画。旧的 `oagd.playback/1` 绑定不写 `locomotion` 时保持离散播放。

## 配置与前提

在项目绑定 JSON 中显式添加：

```json
"locomotion": {
  "mode": "speed_phase",
  "acceleration_mps2": 3.0,
  "deceleration_mps2": 4.0,
  "turn_speed_deg_s": 240.0,
  "transition_s": 0.18,
  "contact_phase": {"L": [0.16666666666666666, 0.3333333333333333], "R": [0.6666666666666666, 0.8333333333333334]}
}
```

这里的相位窗口是两个技术案例的声明，不能原样套给未知动作。相位为片段时间除以完整周期时长。`motion_playback create/stage` 会检查 walk/run 的源加工接触区间扣除修复淡入淡出后，是否同时覆盖每只脚的声明窗口；缺失或相反会拒绝。尚不自动寻找脚步相位，也不重新排列帧来强行对齐。首先校准源动作，再创建混合图。

idle/walk/run 必须循环、没有片段事件；走速必须小于跑速，速度继续使用角色配置中已校准的值。仍只支持原地、控制器持有位移的资产；根骨平移与旋转检查覆盖全部加工采样。`locomotion` 是生成状态保留名。原始八个片段仍可独立播放。

## 实际运行

组件计算待机到移动权重、走到跑权重，并使用混合步长计算周期频率。两个片段分别按各自时长缩放播放率，因此 1 秒走路与 0.6 秒跑步保持一致的左右脚相位。低速时先混入待机，接近跑速时逐渐提高跑步权重。输入松开不会立即选中待机；实际减速会自然降低移动权重。

- Godot：`configure_locomotion(speeds)` 后调用 `set_locomotion_speed(actual_speed)`，选择 `locomotion`，再 `advance(delta)`。嵌套 BlendTree 的两个 Blend2 使用 `sync=true`，零权重子片段仍更新。TimeScale 使走跑周期一致。`locomotion_times()` 返回原生子节点的实际时间。
- UE 5.8：`UOAGDPlaybackSet` 保存启用状态和校准速度；项目在 `OnCharacterMovementUpdated` 后调用 `SetLocomotionSpeed`。原生 TwoWayBlend + SequencePlayer 同步组组成可编辑 AnimBP；零权重子节点保持更新，原生求值后读取 WalkTime/RunTime。未使用逐帧 SetPosition 模拟播放。
- 示例使用 CharacterBody3D／CharacterMovement 实际碰撞移动，水平加减速和限速转身由项目代码处理。当前是面向移动方向的控制方式，侧向输入会转身；不提供独立侧步或倒退动作。
- 跳、下落、落地、完整交互仍是外层状态，按配置时间过渡。快速走跑变化留在同一 locomotion 状态，不反复重置周期。全身交互暂时锁定移动；上半身分层见[分层说明](LAYERS.zh-CN.md)。
- `P` 暂停／恢复整个示例角色；骨骼、动画混合与位移一起冻结。E 交互、Q 取消、R 重开沿用原入口。播放组件本身的 rate 只表示动画播放率，项目若需要冻结物理，应像示例一样单独处理。

旧工程不会自动换图。对新模板使用 `create`；对已采用此模板的工程，用 `stage → 原生 prepare → activate` 保留旧图和绑定。复杂既有 AnimationTree/AnimBP 应按上述接口接入，不能用生成器覆盖。

## 检查与边界

原生记录包含实际子片段时间、权重、水平速度、骨骼世界变换、朝向、暂停状态和真实帧步长。分别统计直线匀速走、跑、中间速度、起停、改速、转向的接触漂移；同一接触窗口不会因类别改变而重置测量锚点。骨骼姿态连续性另在角色坐标系检查，重开导致的明确传送单列排除。

这不是脚部锁定或运动扭曲系统。只有已声明的平地接触窗口可用于脚滑结论；急转仍可能滑脚，缺少专用起停、180 度转身、侧移、倒退以及移动落地片段。现有示例是技术手工动作，直线稳态与过渡质量不能互相替代。不得将小样的宽松转向诊断预算当作正式动画品质验收。

连续移动使用原地动作与明确支撑窗口。根运动、地形 IK 和手部约束见对应模块的接入说明。
