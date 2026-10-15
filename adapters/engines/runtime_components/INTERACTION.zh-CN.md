# 交互组件

[English](INTERACTION.md) | [简体中文](INTERACTION.zh-CN.md)

可选原生组件负责发现候选、距离／方向／遮挡筛选、提示、按住进度、取消及请求生命周期。游戏负责条件和提交后的规则；不需要角色动画插件，也不强制使用示例角色、钥匙或门。

## 新工程与文件

```powershell
python tools/runtime_components.py create --engine godot --scenario interaction --project C:/Trials/InteractionGodot
python tools/runtime_components.py create --engine unreal --scenario interaction --project C:/Trials/InteractionUE --ue-root D:/UE_5.8
```

Godot 打开 `project.godot`。UE 编译 `OAGDExamplesEditor Win64 Development`，运行新工程 `create_map.py`，再打开 `/Game/Example`。地图脚本保存持久地图和 `Content/Interaction/Tint.uasset`，房间对象由原生游戏代码创建，按房间生命周期集中销毁。

WASD 移动并改变面向；Space／手柄 South 按下开始，松开取消；Esc 打开暂停菜单。可以用菜单中的 Face key／Face door 调整面向。先拾取蓝色方块钥匙，再按住打开门。测试是软件原生输入和直接案例调用，不是实物手柄或人工试玩。

配置位于 Godot 根目录／UE `Content/OAGDData/interaction-profile.json`：schema=1、range_m、half_angle_degrees、door_hold_seconds。输入沿用 `input-profile.json`。生成器为每个工程提供独立输入身份和本地配置；升级工具包不会自动升级已有游戏内的锁定组件。

## 模块和接口

| 职责 | Godot | UE 5.8 |
| --- | --- | --- |
| 可交互对象 | `OAGDInteractable` Node3D | `UOAGDInteractableComponent` ActorComponent |
| 查询与请求 | `OAGDInteraction` Node3D | `UOAGDInteractionComponent` ActorComponent |
| 参数 | `configure(distance_m, half_angle)` | `Configure(distance_cm, half_angle)` |
| 候选登记 | `register_target(target)`／`unregister_target(id)` | `RegisterTarget(target)`／`UnregisterTarget(id)` |
| 最新视点和推进 | `update_query(requester, origin, direction, delta)` | `UpdateQuery(requester, origin, direction, delta)` |
| 按下、松开 | `begin(unique_request_id)`／`cancel(reason)` | `Begin(unique_request_id)`／`Cancel(reason)` |
| 暂停、切场景 | `set_suspended(true)`／`clear()` | `SetSuspended(true)`／`Clear()` |
| 提示读回 | `focused_id()`、`prompt`、`allowed`、`reason`、`progress` | `FocusedId()`、`Prompt`、`Allowed`、`Reason`、`Progress` |
| 事件 | `lifecycle(request_id,target_id,state,reason)` | `Lifecycle` 动态委托，同字段 |

组件不自行选择相机或监听按键。项目每次更新给出交互原点、方向和游戏 delta，再将输入动作接到 Begin／Cancel。示例原点为角色中心，方向为最近移动面向；选择镜头方向或手部原点是项目的接入选择。Godot 在物理更新中查询；输入时再以 delta=0 刷新当前视点。UE 在控制器 Tick 中刷新，并在输入开始时再刷新。

候选数量最多 128；稳定 ID 非空且最长 80 字符；提示最长 160 字符；按住时长 0–10 秒。0 表示即时交互。距离必须大于 0 且不超过 100 米／10,000 厘米，方向半角大于 0 且不超过 89 度。无效或重复对象 ID 拒绝登记；对同一对象再次登记为幂等操作。目标属性变化也会在后续查询时检查。

Godot 对象的 `condition` Callable 返回 `{allowed: bool, reason: String}`，`commit` Callable 返回严格 bool。未绑定条件默认允许；未绑定提交或返回其他类型视为失败。UE 派生组件用 `Query` 返回 `FOAGDInteractionOffer`，用 `Execute` 返回 bool，也可通过蓝图重写。这两个查询／提交职责不能混用：Query 应只读，不能在里面改登记表、销毁对象或修改管理器。

## 选择、提交与取消

1. 对已登记且 enabled 的目标，先检查范围、方向与原生射线可见性。Godot 复用 `OAGDQuery.ray` 的碰撞层 1；UE 复用 `UOAGDQuery::VisibleHit` 的 Visibility 通道，忽略请求角色。Godot 目标自身或其子物理对象算目标命中；UE 目标所属 Actor 算目标命中。复杂角色附属碰撞需由项目设置通道，不提供任意忽略列表。
2. 按方向夹角优先、距离其次、稳定 ID 最后排序。角度差容差 0.00001（1-dot），距离容差 1 毫米。没有自动“跳过上锁对象选中背后对象”：上锁目标仍显示原因；disabled 的目标不参与选择。
3. Begin 使用最近一次提供的视点重新查询、重新检查项目条件，固定本次目标和按住时长。持续 Update 时若目标消失、退出范围、被遮挡、面向变化导致选中别的对象、条件变化或目标禁用，本次请求取消，不自动改为操作其他目标。
4. 达到时间后再次检查条件，先将请求移出等待状态，再调用项目的同步提交函数，最后发出 completed／failed。调用方要在提交函数内部保证自己的状态修改完整；组件不自动回滚部分库存／费用变化。

每个被接受的请求发出一个 started 和一个 completed／failed／cancelled。Begin 返回 true 表示请求被接受，不保证最终成功；即时交互也应读取事件判断结果。拒绝的请求不发 started，错误见 LastError。最近 256 个已接受请求 ID 去重；取消后要使用新的 ID。Clear 清空房间登记和去重记录，ID 不提供跨进程或网络保证。

同时只允许一个等待请求。重配置在持有请求时拒绝。生命周期回调和提交函数执行期间禁止嵌套 Begin、登记或重配；回调可 Cancel／Clear。Godot 节点引用、UE 对象引用均不延长目标寿命；对象销毁在下一次有效 Update 中被观察。项目必须持续调用 Update，并在暂停与场景卸载前显式暂停／清空管理器。

输入上下文切到菜单时，输入路由先释放游戏动作，再由暂停信号暂停交互组件；不会恢复一个已取消的按住动作。返回游戏后需要重新按下。组件移出场景／结束运行也执行 Clear。例子的 Reset room 会销毁旧房间对象、创建新对象并重新登记，不冒充完整关卡流送或存档恢复。

## 游戏规则示例

公共层不知道“钥匙数量”和“门已开”。案例在 `main.gd`／`ExampleGame.cpp` 内保存它们。钥匙提交增加数量，隐藏并禁用拾取物；门条件读取数量，门提交旋转门并关闭其碰撞。提示和进度只读取交互组件及这些项目状态。

需要音效或特效时，项目可在 completed 事件中调用 Feedback，使用 request_id 派生事件 ID。交互案例使用状态、原生几何变化和 UI 提示；声音与特效由项目配置。

## 验证与限制

```powershell
python tools/runtime_validation.py --engine godot --project C:/Trials/InteractionGodot --executable C:/Tools/Godot.exe --visual
python tools/runtime_validation.py --engine unreal --project C:/Trials/InteractionUE --executable D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe --visual
```

新报告保存在工程 `.openaigame/runtime-validation/<运行 ID>/interaction.json`。Godot 首次自动导入，UE 需先编译与建图。案例检查 49 项，包括请求确实启动的前提、遮挡、距离、目标选择、条件变化、重复提交、取消、对象销毁、房间替换、执行失败及逐请求唯一结束事件。截图检查进度提示与真实门几何状态，不用自动操作冒充人工体验。

当前为 Windows 单玩家、同步提交、显式登记候选、射线到单个锚点、即时或按住交互。没有联网仲裁、多人争用、异步交互任务、多个动作菜单、候选空间索引、选择迟滞、NPC 导航或生产级背包。原生物理与相机可按游戏替换，并在目标工程验证查询、遮挡与取消行为。
