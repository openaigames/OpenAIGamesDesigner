# 可选上半身与全身分层

[English](LAYERS.md) | [简体中文](LAYERS.zh-CN.md)

适用于 Godot 和 UE 5.8。未声明 `layers` 的绑定使用基础动画图。组件复制到游戏工程后由该工程持有，配置、动作与请求逻辑可独立修改。

## 范围和职责

基础层保留待机、移动、转身及跳落。可选 `upper` 从校准后的 spine 骨开始，包含头、双臂，排除根骨、髋和腿；`full` 在其上覆盖全身。导入端检查实际骨架祖先关系，不能仅凭“spine”名称认定遮罩正确。权重是姿态覆盖混合，**不是 additive 动画**。

Godot 使用 AnimationTree 的过滤 Blend2、TimeScale、TimeSeek 和双 AnimationNodeAnimation 槽位。UE 使用可编辑 AnimBP，Upper 为 LayeredBoneBlend，Full 为 TwoWayBlend，每层两台 SequencePlayer。每个 UE 槽位有独立同步组，不与其他槽位对齐时钟。选择新动作时只重置选中的槽位一次；正常播放不逐帧 seek，不直接写骨骼。

共享组件负责播放代次、权重、优先级和事件。游戏自行决定能否在移动／空中使用某个动作、是否锁移动、交互结果、技能和伤害。示例的全身手势只允许站稳时触发，上半身手势可叠加移动、转身与跳跃。

## 绑定

在完整 playback bindings 中加入：

```json
{
  "layers": {
    "mode": "upper_full_v1",
    "upper_root": "角色配置中 dst_spine 对应的实际骨名",
    "clips": ["upper_wave", "upper_alt", "upper_loop", "full_tuck"],
    "fade_in_s": 0.12,
    "fade_out_s": 0.16,
    "replace_s": 0.12,
    "event_policy": "current_visible"
  }
}
```

列出的 clip ID 都须是独立 `layer_only: true` 条目，保留 `clip`、`duration_s`、`loop`、`motion_owner: controller`、`in_place: true`。可复用同一个加工片段作为别名；基础层动作 ID 和默认动作不能变成 layer-only。创建／暂存仍检查原始加工报告、角色配置、根骨与资源哈希，循环层还核对源动作首尾姿态。

以上四个 ID 是样例约定：E／F 默认使用 `upper_wave`／`upper_alt`，自动回放还使用 `upper_loop`／`full_tuck`。共享组件不要求这些名字；游戏改用其他 ID 时，同时修改自己工程的请求逻辑。片段及动作质量仍由项目选择。

非循环标记可位于 `[0, duration]`；循环标记只允许 `[0, duration)`，接缝统一使用零点。名称唯一、时间有序。循环标记可以每圈重复，旧基础层事件约束保持原样。

## 调用与规则

Godot 在 `configure(tree, definitions, layer_policy)` 后通过 `motion.layers` 调用；UE 给角色挂 `UOAGDLayersComponent`，先 `Configure(Bindings)`，与 `UOAGDPlaybackAnimInstance` 及生成图配套使用。

| 操作 | Godot | UE |
| --- | --- | --- |
| 请求动作 | `play(channel, action, priority, weight, speed, restart)` | `Play(Channel, Action, Priority, Weight, Speed, Restart)` |
| 改权重 | `set_weight(channel, value)` | `SetLayerWeight(Channel, Value)` |
| 改播放率 | `set_rate(channel, value)` | `SetLayerRate(Channel, Value)` |
| 取消 | `cancel(channel, reason)` | `Cancel(Channel, Reason)` |
| 清空层 | `reset()` | `ResetLayers()` |

- 有效请求权重 `(0.001, 1]`，播放率 `[0, 4]`；不支持倒放。渐变参数为满量程 0→1 所需秒数；例如从 0 到 0.5 只需半段时间。播放率 0 冻结片段时间，权重渐变仍可继续。
- 同层低优先级请求拒绝；同动作且 `restart=false` 为幂等。新动作使用另一个槽位，交叉混合未完成时再次替换返回 `transition_busy`，由游戏决定重试／丢弃。没有任意长度动作队列。
- 全身层接受请求时中止上半身的逻辑播放；全身仍有效或正在淡出时，拒绝上半身请求。跨层覆盖关系先于数值优先级。
- 将权重设为 0 表示取消（`weight_zero`）；不会隐藏播放后等待恢复。取消、抢占立即停止旧代次事件，旧姿态按配置淡出。
- 重置清除权重和逻辑代次。示例的 `P` 冻结整个角色与所有层；项目若只改某一层速率，其他层和角色可继续。

## 事件

Godot `event(Dictionary)` 与 UE `Event(FOAGDLayerEvent)` 提供 channel、action、run、kind、name、cycle、片段位置、累计实际播放时间和权重。UE 字段采用 PascalCase（如 `TotalSeconds`），样例报告归一为 `total_s`。

UE 报告中由 FName 转成字符串的通道、请求操作和拒绝原因，可能在编辑器与独立包中显示不同大小写（如 `upper`／`Upper`、`priority`／`Priority`）。读取报告时按这些控制标识符的大小写不敏感语义比较；工具包验收器已处理，原始记录保留。

只由当前有效且有可见权重的代次发标记。循环跨多圈时按圈数和标记时间排序；非循环可在首帧完成，也不会额外重发终点标记。旧混合槽位不发送玩法事件。标记回调可取消当前动作；取消后同一帧剩余标记不再派发。正在执行中断／重置通知时拒绝递归替换请求，避免重入。

这是可见时段的事件策略，不是不可见阶段的通知缓存。示例暂停时停止整棵树的推进并拒绝新动作输入；其他项目若在全局速率 0 或不可见状态请求新动作，需要自行确定零点事件的补发策略。

读取的是引擎原生序列位置。Godot 用本次真实 advance 的 delta 和播放率解开循环次数，并与原生位置核对；UE 读取 SequencePlayer 的 DeltaTimeRecord。超过 2 ms 的不一致记为 `clock_mismatch` 并取消，不能假设动画一定推进。结束原因有 completed、interrupted、cancelled、overridden、reset、weight_zero、callback_cancelled、clock_mismatch。

## 接入和验证边界

新项目沿用 `motion_playback.py create`；已有生成项目须显式更新项目拥有的组件／模板，再 stage → 原生 prepare → activate。仅 stage 资产不会自动更新旧项目代码。复杂现有图、Montage、异步并行更新、网络同步需单独适配，不能直接覆盖。

样例按键为 WASD 移动、Shift 跑、Space 跳、E 上半身、F 全身、Q 取消、R 重置、P 暂停。F 的站稳要求属于样例。测试中的 `full_tuck` 复用原 jump 片段，仅用来证明全身遮罩影响腿部，不能当成完成的跳跃玩法。

分层覆盖需要检查骨骼遮罩、混合权重、循环标记和中断清理。与根运动或接触约束组合时，需明确更新顺序并单独验证。
