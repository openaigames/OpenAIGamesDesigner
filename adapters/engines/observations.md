# 真实运行与空间观察

共享协议是 [observation.schema.json](../../schemas/observation.schema.json)，登记入口是 [observation.py](../../tools/observation.py)。原始 capture 与登记记录分别保存；登记不修改原始证据。文件和工程依赖变化时显示历史适用性，不能沿用旧通过结论。

```sh
python tools/observation.py --project MyGame register --capture runs/R001/observation.json --id O001 --dependency game/Content/Map.umap
python tools/observation.py --project MyGame show --id O001
python tools/observation.py --project MyGame elapsed --id O001 --start hero:cancel-1 --end hero:cleanup-1
```

依赖包括真正消费的规则、资源、配置和运行执行记录。不会根据同名文件推断使用方；登记时应覆盖影响本次结论的源。引擎记录精确的来源时钟、对象、输入方式、辅助条件和采样成本。通用记录不包含所有引擎内部状态，不是确定性回放系统。

## Godot 2D

将 [OAGDObservation.gd](godot/OAGDObservation.gd) 作为项目测试场景子节点。先 `register_object(id, actual_node, kind)`，再由实际规则分支调用 `mark_event(id, name, details)`；正常请求、接受/拒绝、规则提交、命中、各反馈层、取消和清理分别标记。没有事件不可补造成功命中。

`sample_parameter` 读运行中的真实属性；`capture(scene, context)` 读取 Node2D 世界位置、碰撞形状边界/多边形和 Camera2D 数据；`save_capture` 只写指定工程内的新文件。游戏时钟累计 process delta，会受 time scale 影响。Shape2D 矩形是边界代理，不能单凭该图断言通行或视线成立。游戏代码生成的场景可直接从活跃节点读取；需额外语义时由项目显式提供对象 ID 和事件。

参考测试场景在源码 `tests/fixtures/godot-observation/`；该场景故意在取消后延迟清理，用于测试观察能力，不能作为正确战斗逻辑复制。

## Unreal 3D

复用 [engine_workflow / 会话恢复](sessions.md) 的 Playback。请求示例：

```json
{
  "engine":"unreal","mode":"playback","scene":"/Game/Map",
  "seconds":3,"capture_interval":0.5,"camera_target":"ReviewCamera",
  "observe":{"interval":0.05,"bindings":true,"max_samples":2400,
    "conditions":["按本次真实运行填写"],
    "actors":[{"id":"hero","target":"Hero","kind":"player",
      "markers":["weapon_r","hand_r"],
      "properties":[{"id":"speed","component":"CharacterMovement","property":"max_walk_speed","unit":"cm/s"}],
      "event_exporter":"ExportObservationEvents"}]}
}
```

`event_exporter` 是项目提供的只读 UFunction 名称，返回 JSON 字符串数组。每项只有 `id`、`time`、`event` 和可选 `data`；时间使用该 PIE 世界的 GetTimeSeconds。ID 在同次运行内稳定，重新查询可返回累积记录，已出现事件不得改写。工具不会调用不存在的通用攻击接口，也不从血量/状态变化猜出反馈发生时点。导出函数需项目明确保证只读。

动作请求按 **自第一次采样起的游戏秒** 调度；截图开销不算成游戏推进。墙钟 watchdog 仍约束停滞。`actions` 的 position 是传送、method 是组件调用，不能当真人操作。`readonly_preview:true` 拒绝编辑与 actions；游戏本身的启动逻辑仍会正常执行，只读指不修改作者资源，不是冻结游戏。

输出包括 `observation.json`、`runtime-bindings.json`、帧序列、帧时间和已有会话执行记录。绑定读回包含实际模型/动画引用、父组件、附件名、相对/世界变换、标记是否存在及组件创建方式（API 未开放则注明）。单节点动画、已有 AnimBP 引用可读；某次没有采样到的动作并不等于角色不具备该动作。

空间记录读取实际 Actor 位置与边界，相机使用实际 CameraComponent 投影参数。Actor 边界不是精确地形或导航网格；通行、遮挡和可达性应结合项目碰撞/导航查询和实际路线。相机不是实体障碍，不用编辑器相机图标的边界充当空间尺寸。旋转请求统一为 `[pitch, yaw, roll]` 度，运行转换使用具名参数。

指定 `camera_target` 时，截图锁定明确的 CameraActor；PNG 时间记录的是请求时的世界时钟，完成可能更晚。帧序列没有音频，采集会影响帧时；不能当无采集开销的性能测量。参数和绑定取样数有上限，到达上限时记录缺口。

UE 的启动日志若含错误，会保留 needs_review，不能忽略退出码以外的异常。可在项目配置中显式设置 `unreal.automation_culture` 固定本次进程语言，便于复现；不要为了清日志屏蔽未知错误。

相关 API 以当前引擎为准：[SceneComponent](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/SceneComponent)、[AutomationLibrary](https://dev.epicgames.com/documentation/en-us/unreal-engine/python-api/class/AutomationLibrary)。

## 记录评审

工作台不再提供独立运行评审页。使用 `observation.py show/elapsed` 读取记录与事件间隔，并按实际问题查看原始媒体或生成对照报告；观察采集、版本检查及批注数据接口继续保留。

当前记录与对照记录保留独立时钟。通过两条已观测事件选择对齐锚点，明确这是人工选定的一次时间平移，不假设不同设备时钟相同。视频只在提供的锚点区间内插值，暂停或变速片段应分段登记；图片对应请求/取帧时间，不证明亚帧延迟。

需要空间分析时，根据实际采样生成 XY 俯视、XZ/YZ 剖面或路线对照图。位置批注应记录完整的三维实测坐标，不能从二维图推测未投影轴，保存前核对对应对象与时间。两个空间只有在同一坐标约定、单位和范围下才可比较；相同单位本身不证明坐标原点相同。

批注只保存观察与锚点，不自动批准阶段或关闭问题。任务记录仍由同一个 `game_workflow task` 入口和兼容 API 读写，专业判断有实际依据后再关联证据。
