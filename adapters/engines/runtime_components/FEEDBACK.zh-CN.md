# 通用反馈

[English](FEEDBACK.md) | [简体中文](FEEDBACK.zh-CN.md)

Godot `OAGDFeedback` 与 UE 5.8 `UOAGDFeedbackComponent` 管理原生声音、可选视觉对象及附加镜头角度。游戏提交事件后决定使用哪个 cue；开门条件、伤害、任务和资源选择属于游戏。无需安装角色动画插件。

## 接入与项目归属

运行 `tools/runtime_components.py create --engine godot --scenario feedback --project <新目录>`，或使用 `--engine unreal --ue-root D:/UE_5.8`。Godot 首次打开会导入 WAV；UE 先编译编辑器，再执行工程 `create_map.py`，生成地图、SoundWave 和材质。已有游戏可沿用组件安装入口，自己调用反馈接口，不必采用示例角色或菜单。

示例以 `feedback-profile.json` 绑定 door、zone、ui、action，分别由开门提交、真实玩家进入区域、菜单选择和项目动作回调触发。四份 WAV 来自 `templates/runtime_feedback/generate_audio.py` 的原创校准配方，没有第三方采样。视觉示例为程序网格：Godot 环、UE 圆盘；它们用于观察实例位置、时间和清理，不是成品美术。

Godot 的入口为 `main.gd`、`audio/`、`pulse.gd`、`pulse.tscn`；UE 为 `Source/OAGDExamples/ExampleGame.cpp`、`Content/OAGDData/feedback-profile.json`、`Content/Feedback/`。复制到游戏的资源、映射和组件锁归该游戏所有；升级工具包不会修改已有游戏副本。

## 接口与规则

| 用途 | Godot | UE 5.8 |
| --- | --- | --- |
| 配置 | `configure(profile, audio, visuals)`，空字符串成功 | `Configure(TMap<FName,FOAGDFeedbackCue>, budget, error)` |
| 播放 | `play(cue, event_id, owner, position, follow, scope, intensity)` | `Play(Cue, Event, Owner, Position, Follow, Scope, Intensity)` |
| 停止 | `stop(handle, reason)` | `Stop(Handle, Reason)` |
| 场景清理 | `stop_scope("scene")` | `StopScope(TEXT("scene"))` |
| 整体清理 | `clear()` | `Clear()` |
| 暂停 | `set_game_paused(value)` | `SetGamePaused(Value)` |
| 相机贡献（角度） | `camera_offset` Vector3 | `CameraOffset` FRotator |
| 生命周期 | `lifecycle(handle,event,cue,state)` | `Lifecycle` 动态委托 |

播放成功返回递增句柄；拒绝返回 -1 并写入 `last_error/LastError`。只读观察 `active/Active`；调用方不应直接修改内部集合或销毁组件持有的资源。停止同一句柄第二次返回 false。

`event_id` 必须是一次事件的唯一 ID，不是 cue 名。保留最近 256 个已接受 ID，停止后仍去重；`Clear` 或成功重配置清除记录。不提供跨会话或网络上的严格一次执行。

每个 cue 最多 1–16 个实例，全局预算 1–32。单 cue 满额时按配置拒绝或替换最旧句柄；全局满额且本 cue 没有可替换实例时拒绝。无优先级抢占队列。配置失败保留上次有效配置；存在活跃实例时拒绝重配。

配置 schema=1，cue 需 domain=`game|ui`、overflow=`reject|oldest`、loop/spatial 布尔值、duration 0.02–60 秒、volume 0–1、camera 0–3 度、limit 整数、color 三个 0–1 数值、audio/visual 资源 ID（空字符串表示不使用该通道）。强度 0–2；拒绝非有限数值。Godot 配置器接收 JSON 和已解析资源；UE 示例解析 JSON 并构建原生结构，组件也可由 C++／蓝图直接传入结构。

## 生命周期、位置与时钟

单次效果按声明 duration 结束；音频文件可先自然结束。循环效果必须有活着的 owner，且音频资源启用原生循环；不支持 UI 循环。停止会立即关闭音频并删除视觉实例。任意音效淡出尾音、复杂混音、遮挡、配乐和中间件不由此组件提供。

`follow=false` 时 position 为世界位置；`follow=true` 时为 owner 世界位置加世界轴偏移（Godot 米、UE 厘米）。这只是位置跟随，不自动继承旋转、缩放或骨骼 socket。项目可用自己的挂点节点或代理 Actor 传递位置。owner 销毁后其所属效果在下一次更新停止；不影响无 owner 的独立世界效果。

游戏暂停需显式通知反馈组件，示例接入 输入路由的暂停信号。游戏音频暂停、视觉和相机时间冻结，新的 game cue 被拒绝；UI cue 使用真实时间并继续播放。UE 声音由组件明确控制暂停；设为可在引擎暂停时播放，然后按 domain 调用 SetPaused。游戏恢复后继续其剩余时间。UI 到期在下一次引擎更新处理，不能在主线程完全阻塞时执行清理。

视觉资源契约：Godot PackedScene 根为 Node3D，实现 `sample(age,strength,color)`；UE 派生 `AOAGDFeedbackVisual` 并实现 `Sample`。UE 应保留独立可移动根锚点，在子组件上做局部动画。提供网格示例，尚未实现通用 Niagara／粒子编辑器适配。

组件输出相机的绝对附加角度，项目每帧先减去上次贡献再加本次贡献；不得直接逐帧累加。总俯仰限 ±3 度，滚转限 ±1.5 度。Godot 组件优先级 -10，示例相机默认 0；UE 示例控制器通过 `AddTickPrerequisiteComponent(Feedback)` 在反馈更新后读取结果。清理后贡献归零，基础镜头角度保留。

回调可 Stop／StopScope／Clear；快照遍历可承受回调清空其他实例。生命周期回调期间拒绝新 Play 和 Configure，调用者需延后到下一帧。视觉 Sample 应仅调整视觉，不在内部变更反馈管理器。

## 验证入口与证据边界

`tools/runtime_validation.py --engine godot|unreal --project <工程> --executable <引擎程序> --visual` 生成独立结果目录和临时存档。Godot 自动进行首次导入；UE 需先编译和建图。反馈案例使用真实时间，不能加固定帧时间参数代替音频时间。UE 无前台焦点的自动检查设置 `[Audio] UnfocusedVolumeMultiplier=1.0`；仅当前启动命令生效。

报告包含 33 项原生断言、实例事件、混音 WAV 和渲染截图。运行器额外检查 WAV 非静音及未削波；这只能证明信号输出，不能替代人耳试听。`--visual` 去掉时不取得画面验收，Godot 的无声 headless 驱动也可能使混音检查失败，应使用有音频设备的原生运行。

面向 Windows 单机 3D 工程。项目应分别验证声音听感、最终混音、长时性能、设备输入和交接运行。
