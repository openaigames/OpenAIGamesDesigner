# 设置、场景与本地游戏状态

[English](STATE.md) | [简体中文](STATE.zh-CN.md)

适用于 Godot 和 UE 5.8。该模块独立于角色动画，可沿用[输入、焦点和暂停](INPUT.zh-CN.md)的项目接入方式。

## 文件与职责

| 职责 | Godot | UE 5.8 |
| --- | --- | --- |
| 两代本地存储 | `godot/oagd_store.gd`：`OAGDStore` | `OAGDStore.h/.cpp`：`FOAGDStore` |
| 设置校验及引擎应用 | `godot/oagd_settings.gd`：`OAGDSettings` | `OAGDStore.h/.cpp`：`FOAGDSettings` |
| 候选场景及提交 | `godot/oagd_scene.gd`：`OAGDScene` | `OAGDScene.h/.cpp`：`UOAGDSceneComponent` |
| 游戏状态、稳定 ID、检查点、菜单、测试 | `templates/runtime_state/godot/` | `templates/runtime_state/unreal/` |

工具包保存 JSON 对象，不扫描并自动保存所有引擎对象。项目负责定义版本、校验引用、收集快照、准备候选场景并应用状态。示例声明 `scene`、`checkpoint`、`objects` 和 `player`；两扇门使用 `door-a`、`door-b`，与 Actor 枚举顺序无关。UE 用 Actor Tags 识别并拒绝重复 ID，Godot 的房间适配器声明所属房间及对应门。位置采用各引擎的原生坐标与单位，两个示例的存档不承诺互换。

## 接入存储

Godot：`Store.new(directory, project_id, data_version)`；`write_slot(slot, dictionary)` 返回错误字符串，空串表示成功；`read_slot(slot)` 返回 `error`，成功时还有 `data/seq/generation/recovered`。

UE：`FOAGDStore(Directory, ProjectId, DataVersion)`；`Write(Slot, Data, Error)`、`Read(Slot, Data, Recovered, Error)` 返回 bool。JSON 类型属于公开依赖。目录由宿主选择，应位于游戏自己的可写数据目录。示例使用 Godot `user://state`、UE `Saved/OAGDState/<project-id>`。

每个槽使用 `<slot>.0.json` 和 `<slot>.1.json`。外层有原始 JSON 字符串 `body` 及其 UTF-8 SHA-1 校验值；body 含 `schema=1`、`project`、`version`、递增 `seq` 和项目 `data`。校验用于识别意外损坏，不是防作弊或加密。每个文件最多 2 MiB；槽名仅支持 1–64 个小写英文字母、数字、下划线和连字符。

写入顺序：项目校验 → 找到最新有效代 → 写较旧代的 `.tmp` → 关闭并读回校验 → 提交这一代。最新有效代在提交期间保留。读取时忽略损坏代并设置 `recovered=true`；最新**完整**记录的项目、格式或数据版本不兼容时明确拒绝，不能悄悄回到更早的兼容记录。只有损坏文件且无有效代时不自动覆盖；将原槽备份后选择新槽或明确恢复。残留 `.tmp` 不作为已提交记录读取。

项目需要在写入**之前**校验跨对象引用和规则，在读取后、修改世界之前再次校验。组件无法判断“这个门 ID 是否存在于你的游戏”。重复加载应设置最终状态，不重复发奖励；示例的门开关、位置恢复均为幂等赋值。示例提供 `slot1` 和独立 `checkpoint`；组件接受多个命名槽，槽选择界面由游戏决定。

组件面向一个进程中的单一写入方。没有多进程锁、云存档、网络同步、自动旧版本迁移或任意对象序列化；没有进行物理断电测试。不能把文件提交成功解释为硬件掉电零丢失。项目格式升级应显式转换到新槽并保留原件，工具包代码回退不会回退玩家数据。

## 设置与实际消费者

`defaults/Defaults`、`validate/Validate`、`apply/Apply` 支持：

| 字段 | 范围 | 实际消费者 |
| --- | --- | --- |
| `fps` | 0（不限）、30、60、120 | Godot `Engine.max_fps`；UE `GameUserSettings` 帧率限制 |
| `vsync` | bool | Godot DisplayServer；UE GameUserSettings 非分辨率设置 |
| `camera_sensitivity` | 0.1–4 | 项目镜头控制器，示例确实乘到镜头旋转增量 |

项目先校验并保存设置，再应用并刷新自己的镜头参数。启动时读取并校验；缺失使用默认值，坏档／不兼容使用默认值并显示说明。恢复旧代同样显示说明。示例菜单支持切换设置和恢复默认值。输入改键继续由 的独立输入偏好接口管理。

帧率属性和 VSync 请求读回不是显示器刷新率或性能测量。无渲染模式不声称验证实际 VSync。不提供音量、分辨率确认倒计时或平台图形预设。

## 场景切换与检查点

采用**持久玩家／界面 + 可替换的被动场景块**。UE 使用真实 `.umap` 流送，Godot 使用真实 PackedScene。不是跨任意 GameMode 的 `OpenLevel` 通用迁移器；大型开放世界异步流送策略也不在模块范围内。场景块初始化不得触发不可回退的奖励、存档或全局事件。

Godot：`stage(path)` 同步加载并实例化候选，保留当前场景；项目检查适配器并对离树候选应用状态；`commit()` 才替换当前子场景。`cancel()` 释放候选。大资源同步加载可能阻塞帧，项目可换成自己的异步资源准备层。

UE：`Stage(Package, Error)` 异步加载隐藏候选；`Prepared` 后项目检查 `Staged->GetLoadedLevel()` 内的稳定 ID、应用状态，再调用 `Commit(Error)`。`OnLevelShown` 后替换 Current，卸载旧场景并广播 `Completed`。`Cancel()` 支持准备阶段，提交显示后不接受取消；30 秒墙钟超时丢弃候选并保留旧场景。对象生命周期由引擎驱动，项目不在候选 BeginPlay 中执行不可回退副作用。

宿主在请求前取得 `transition` 暂停原因，在所有成功／拒绝／取消／超时分支释放这一原因。示例保留菜单的独立 `menu` 原因，避免切换结束意外解除暂停；清空角色速度和旧输入。玩家仍在持久容器，提交成功后才恢复其位置。读取无效槽、缺地图、缺适配器／稳定 ID 时保留旧场景与状态。

检查点是项目声明的一份持久快照：示例记录场景、位置、门状态和 `a-entry/a-door/b-entry/b-door` 标识。设置检查点先保存成功，再更新运行时检查点标识；重生使用相同的校验与场景提交路径。它不是工程文件的版本回退，也不强制所有游戏使用同样的检查点规则。

## 创建与验证

```sh
python tools/runtime_components.py create --engine godot --scenario state --project NEW_GODOT_DIR
python tools/runtime_components.py create --engine unreal --scenario state --project NEW_UE_DIR --ue-root D:/UE_5.8
```

Godot 打开 `project.godot`；UE 编译 OAGDExamplesEditor 后运行项目 `create_map.py`，打开 `/Game/Example`。生成脚本保留已有地图；发布时需烘焙 Room_a、Room_b。InvalidRoom 是故意缺失状态对象的失败用例，包含在验证工程的烘焙配置中。

```sh
python tools/runtime_validation.py --engine godot --project NEW_GODOT_DIR --executable GODOT_EXE --visual
python tools/runtime_validation.py --engine unreal --project NEW_UE_DIR --executable UNREAL_EDITOR_EXE --visual
```

验证器自动识别 state 场景，使用新 evidence 目录，先运行 exercise，退出后再启动 resume，只有这两个独立进程都通过才返回成功。测试数据保存在 evidence 内，不读写交互运行的正常存档。报告检查实际场景对象、碰撞、玩家位置、设置消费者和恢复；不冒充真实玩家操作或物理设备测试。

直接运行案例时，Godot 参数为 `-- --self-test --state-phase=exercise --save-root=ABSOLUTE_DIR --report=ABSOLUTE_JSON`，UE 为 `-OAGDSelfTest -StatePhase=exercise -StateRoot=ABSOLUTE_DIR -StateReport=ABSOLUTE_JSON`；exercise 必须使用新目录，resume 显式复用它。交互运行无需任何测试参数。

新建工程生成不同的项目身份；同一游戏的后续发行应保留原身份和明确的数据版本。组件是项目锁定副本，工具包升级不自动修改已有游戏。更新时按差异显式迁移，保留项目定制。
