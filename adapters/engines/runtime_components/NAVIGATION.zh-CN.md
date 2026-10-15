# 导航与基础 NPC

[English](NAVIGATION.md) | [简体中文](NAVIGATION.zh-CN.md)

可选导航组件用原生导航网格查询路径，输出世界空间的期望地面速度。项目的碰撞移动器执行速度，项目行为决定何时移动、追踪、搜索或返回。无需角色动画插件，不向已有工程强加 AIController、行为树或统一敌对规则。

## 新建和接入

```powershell
python tools/runtime_components.py create --engine godot --scenario navigation --project C:/Trials/NavigationGodot
python tools/runtime_components.py create --engine unreal --scenario navigation --project C:/Trials/NavigationUE --ue-root D:/UE_5.8
```

Godot 打开 `project.godot`，启动时从灰盒静态碰撞几何烘焙导航。UE 编译 `OAGDExamplesEditor`，在新工程运行 `create_map.py`，打开 `/Game/Example`；地图保存静态碰撞和导航边界，Recast 运行时生成网格。建图脚本只在地图不存在时创建，不覆盖已有地图。编辑导航几何后按原生引擎流程重新烘焙或更新；本组件不替代地图生产工具。

WASD 移动黄色目标，蓝色 NPC 巡逻；目标进入距离和可见性条件后被追踪。Space 开始／重试巡逻，Esc 暂停；按钮可重置 NPC、切换物理挡板或退出。按钮为工程调试入口，不代表完整手柄菜单验收。自动测试使用软件原生输入，不冒充实体设备或人工试玩。

项目配置 `navigation-profile.json` 位于 Godot 根目录或 UE `Content/OAGDData/`。包括速度、到达距离、停滞／总超时、重规划间隔、检测距离、失去目标时间、搜索时间与巡逻点。JSON 长度单位为米，点格式 `[x,y,z]`（Y 向上）；UE 示例映射为 `(x,z,y)*100`，只为本例统一配置，不声明任意工程坐标转换。

## 组件契约

| 作用 | Godot | UE 5.8 |
| --- | --- | --- |
| 类型 | `OAGDNavigation` Node3D | `UOAGDNavigationComponent` |
| 配置 | `configure(speed, arrival, blocked, deadline, repath)` | `Configure(SpeedCm, ArrivalCm, BlockedSeconds, MaxSeconds, RepathSeconds)` |
| 新请求 | `request(id,mover,destination,target,foot_offset,target_offset)` | `Request(Id,Mover,Destination,Target,FootOffset,TargetOffset)` |
| 每帧推进 | `step(delta)` | `Step(Delta)` |
| 取消／暂停／卸载 | `cancel(reason)`、`set_suspended(value)`、`clear()` | `Cancel`、`SetSuspended`、`Clear` |
| 读回 | `desired_velocity`、`path`、`goal`、`state`、`reason`、`last_error`、`busy()` | `DesiredVelocity`、`Path`、`Goal`、`State`、`Reason`、`LastError`、`Busy()` |
| 生命周期事件 | `lifecycle(request_id,state,reason)` | `Lifecycle` 委托，同字段 |

Godot 世界单位为米，UE 为厘米。偏移为世界轴偏移，示例胶囊中心到脚底分别 `(0,-0.9,0)`、`(0,0,-90)`。目标对象存在时使用目标位置加 target_offset，否则使用固定 destination。移动者和目标均为弱引用，不延长其寿命。Godot 使用组件所在 World3D 默认导航地图；UE 使用默认支持代理的导航数据，不选择多种代理或过滤器。

先通过 Configure 配置，再请求；进行中或回调内不能重配／再请求。速度范围 `(0,20]` 米/秒，到达半径 `(0,2]` 米，停滞时间 `(0,60]` 秒，总时限 `(0,600]` 秒，重规划间隔 `[0.1,5]` 秒。项目应校准到达半径与碰撞尺寸；示例追踪使用 1 米停止距离，避免两只半径 0.35 米的胶囊互相挤压后永远无法到达。

请求先投影脚底起点和目标到原生网格。水平方向最多偏移 0.5 米、垂直最多 0.6 米；超出返回 outside_navigation。Godot 检查路径末点是否匹配投影目标；UE 同时拒绝 IsPartial。拒绝返回 false 和 LastError，不发 started。ReadyMap 仅表示地图／数据存在，**不保证某条路线已生成或可达**；项目需检查实际请求结果。

已接受请求按配置周期重新查询真实导航网格，不是自行造直线绕障路径。组件用实际移动位置判断进度：累计移动不足 3 厘米达到停滞时间，返回 blocked；超过总时限返回 timeout。每个路径点容差 20 厘米，最终到达使用配置半径和 60 厘米垂直容差，抵达前再核对完整路径。点间输出水平速度，斜坡垂直位移由地面移动器处理。

一个实例同时只有一个请求。最近 256 个已接受 ID 去重，每个 ID 产生 started 和唯一的 arrived／failed／cancelled；Clear 清空此房间的 ID 历史。请求成功受理不等于已到达。failed 原因包括目标／移动者丢失、无有效导航、目标移至断开区域、停滞或超时。Cancel、暂停、Clear 和退出场景清零期望速度；暂停恢复不复活旧请求。

项目必须持续调用 Step 并将输出送入移动器，终止后要清除已缓存输入或惯性。Godot 示例设置 OAGDActor.move_wish；UE 示例对原生 CharacterMovement 输入并在停止时清空输入和速度。组件不瞬移角色，不自行处理加速度、空中运动、根运动或转身动画。周期查询发现网格更新，但不会自动使物理挡板成为导航障碍；示例动态挡板验证碰撞停滞失败，不宣称自动绕过任意动态物体。

生命周期回调中拒绝嵌套请求和重配置，可 Cancel／Clear。请在场景卸载前 Clear；组件自身离开树／EndPlay 也清理。项目不得在事件回调中继续消费该请求的旧路径。

## 项目行为示例

Godot 为 `npc_behavior.gd`，UE 为 `ExampleGame.cpp` 中 BehaviorTick／ChangeBehavior／BehaviorMove。示例状态为 patrol、chase、search、return、blocked、stopped；职责可整体替换。

- patrol 在项目巡逻点之间请求移动。
- 距离与原生射线满足时进入 chase，导航跟随弱引用目标。
- 持续失去目标后进入有时限的 search，随后 return；返回出生点后恢复巡逻。目标销毁时直接进入 return。
- 请求失败后停在 blocked，等待显式重试，不无限循环重发失败请求。暂停取消移动；恢复后行为根据当前状态生成新请求。

detectable 是示例用于校准“失去目标”的项目开关；正常运行仍使用真实距离和遮挡。没有复制任务、伤害、阵营或背包系统。反馈与 交互可以由项目事件组合，不是本例必装的行为依赖。

## 验证和范围

使用已有 `runtime_validation.py --engine godot|unreal --project ... --executable ... --visual`；Godot 自动先导入，UE 要先编译与建图。每次新报告位于 `.openaigame/runtime-validation/<id>/navigation.json`。当前面向 Windows、单个地面 NPC、静态已烘焙或引擎已生成的完整导航路线。测试包含原生绕墙和实际位置、孤立导航平台、移动目标变为不可达、真实物理阻挡、暂停、取消、目标／移动者销毁、时限、回调清理和项目状态转换。并非完整战斗 AI、群体避让、自动动态障碍重烘焙、智能跳跃链接、飞行、移动平台、开放世界导航流送或联网同步。坡道与复杂高度连接未作为本例覆盖结论。

实现依据包括本地 UE 5.8 `NavigationSystem.h`、`NavigationPath.h` 和 ActorFactory 体积创建接口；Godot 原生烘焙／查询职责参考 [NavigationRegion3D](https://docs.godotengine.org/en/stable/classes/class_navigationregion3d.html) 与 [NavigationServer3D](https://docs.godotengine.org/en/stable/classes/class_navigationserver3d.html)。
