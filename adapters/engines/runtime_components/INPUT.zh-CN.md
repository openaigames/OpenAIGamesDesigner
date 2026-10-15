# 输入、焦点与暂停

[English](INPUT.md) | [简体中文](INPUT.zh-CN.md)

Godot 与 UE 5.8 的可选单玩家输入组件。它不依赖 OAGDPlayback、角色骨架、动画图或特定游戏规则。项目可以只采用输入路由与焦点辅助器，继续使用自己的角色和菜单。

## 创建与接入

```powershell
python tools/runtime_components.py create --engine godot --scenario input --project C:/Trials/GodotInput
python tools/runtime_components.py create --engine unreal --scenario input --project C:/Trials/UnrealInput --ue-root D:/UE_5.8
```

使用新目录。Godot 打开 `project.godot`；UE 编译 `OAGDExamplesEditor Win64 Development` 并运行工程 `create_map.py`，再打开 `/Game/Example`。原有 training／puzzle 入口继续保留。

示例支持开始、移动、动作计数、暂停、改键、恢复默认和退出。WASD／左摇杆移动，Space／South 为示例动作，Escape／Start 打开菜单；上下方向键／D-pad 切换菜单，Enter／South 确认。选择绑定后按新键，Escape 取消；同一输入上下文冲突会被拒绝并显示原因。按钮也可以用鼠标点击。示例布局和动作计数属于项目文件。

安装到已有工程仍使用 `runtime_components.py install`。已有版本或本地修改会报冲突，先在独立副本合并和迁移；不会自动替换主场景、PlayerController、角色或输入框架。

| 位置（相对工程） | 接入职责 |
| --- | --- |
| Godot `addons/oagd/oagd_input.gd` | 添加节点，configure 项目配置；读取 strength 或订阅 action_changed；节点以 ALWAYS 处理模式接收原生事件 |
| Godot `addons/oagd/oagd_focus.gd` | 可选 push／pop 焦点辅助器；只恢复仍存在且可见的 Control |
| UE `Plugins/OAGDCore/.../OAGDInput.h` | 添加 UOAGDInputComponent；LoadProfile；PlayerController 的 `InputKey(const FInputKeyEventArgs&)` 转发到 HandleInput；已有输入框架只转发一个入口，避免重复执行 |
| UE `Plugins/OAGDCore/.../OAGDFocus.h` | 可选 Slate 焦点栈；UMG 项目可使用原生焦点 API，并沿用相同的进入／退出职责 |
| 示例 `main.gd`／`Source/OAGDExamples/ExampleGame.cpp` | 菜单、焦点目标、移动消费者、动作计数、真实引擎暂停和验证；可编辑项目代码，不属于共享规则 |

Godot 消费者不要同时使用 `Input.get_vector`／`is_action_pressed` 直接绕过路由器；全局 Input 状态不受 GUI 事件消费控制。UE 既有 Enhanced Input／其他控制器也需明确谁消费动作，不能同时执行旧回调和新路由。

## 配置

权威示例为 `templates/runtime_input/input-profile.json`。创建工程会生成独立 profile ID；Godot 示例应用名也使用独立 ID，避免不同示例共用用户偏好。

| 字段 | 约定 |
| --- | --- |
| schema / id | `oagd.input/1` 和项目配置身份；读取偏好时身份必须匹配 |
| deadzone | 0.05–0.8，左摇杆单轴死区，超过后重新映射到 0–1；不是径向死区 |
| actions | 最多 128 个具名动作；项目定义含义，建议使用小写 ASCII 名称，UE FName 大小写不敏感 |
| context | game、ui 或 global；当前上下文之外的动作输出为零，game 另受暂停原因限制 |
| keys | 每动作 1–8 个绑定；同一动作多个输入取最大强度，不累加；二维移动由项目合成并限制长度 |
| rebindable | 是否允许玩家替换现有槽位；保留操作和 UI 操作可设置 false |

支持 A–Z、0–9、Space、Escape、Enter、Tab、Backspace、Up／Down／Left／Right、Shift／Ctrl／Alt，MouseLeft／MouseRight／MouseMiddle／MouseWheelUp／MouseWheelDown，以及 PadSouth／East／West／North、PadStart／Back、PadL1／R1、PadUp／Down／Left／Right、PadLeftX+／X-／Y+／Y-。手柄左 Y 统一为向下为正，UE 原生输入由适配器转换。当前不提供组合快捷键、IME 输入、触摸、右摇杆／扳机配置或多人本地设备分配。

Shift、Ctrl、Alt 分别合并左右物理键：两侧都按住时只按动作聚合规则输出一次按下，放开一侧仍保持，全部放开才释放。Godot 使用 InputEventKey.location，UE 使用左右独立 FKey；无法提供位置的外部 Godot 事件只能作为一个未区分左右的来源。暂停／上下文屏障要求合并后的键完全释放才重新启用；失焦清空物理来源。可把修饰键绑定为独立动作，不能把 `Ctrl+K` 当作支持的组合键。

滚轮是离散输入，每个原生方向按下事件同步送入 1 再送入 0；同帧重复事件可以分别触发。通过 action_changed／ActionChanged 的正值回调执行换枪、翻页等动作，帧间轮询 strength 不会读到持续按住的滚轮。原生释放不会额外触发。幅度按每个事件一步处理，不模拟触控板滚动距离；UE 只消费 MouseScrollUp／Down，忽略同时发出的 MouseWheelAxis，避免同次滚动重复触发。直接 Feed／feed 也遵循相同脉冲规则，调用方不能同时转发两种原生通道。

同动作绑定多个键仍取最大强度：若持续键已把该动作保持为 1，再滚动不会产生第二个正沿。需要逐步计数的操作应使用独立滚轮动作，并在项目回调中组合效果。捕获滚轮只完成改键，不执行游戏动作；捕获完成后下一次滚动可用，修饰键则需释放后重按。

例如项目可定义 `sprint: Shift`、`crouch: Ctrl`、`next_weapon: MouseWheelUp`。输入组件只输出动作，冲刺速度、蹲伏碰撞／镜头、可选武器与切换规则由项目实现。配置仍为 `oagd.input/1`；旧配置无需增加新动作。新增或删除项目动作后，旧偏好若不符合动作合同仍明确拒绝，不能静默丢弃玩家设置。

game 与 ui 可以复用同一个键；global 与任一上下文冲突都拒绝。改键前检查完整候选，失败保持原配置；Escape 为捕获取消键，不能在捕获界面将它重新绑定。捕获期间不发送游戏或菜单动作，捕获完成的按键需要释放后重新按下才执行动作。

## 暂停与生命周期

`set_context / SetContext` 切换 game／ui；切换时已按住的输入进入等待释放状态，关闭菜单不会把仍按着的确认键或移动键直接送给游戏。

`set_pause / SetPause(reason, active)` 维护具名原因，例如 menu 和 dialog。移除 menu 不解除 dialog；同一原因重复设置是幂等操作。它输出暂停状态，不擅自暂停整个引擎。项目订阅 pause_changed／PauseChanged，按需求设置 SceneTree.paused 或 PlayerController.SetPause；已有框架可以将状态接到自己的会话机制。

示例在 UE 暂停入口清除角色残余移动，避免当帧继续消耗移动；移动规则和暂停策略仍由项目负责。不要将此示例策略直接推广到所有物理物体或需要保持惯性的游戏。

Godot 监听 joy_connection_changed 和应用失焦；UE 监听原生设备连接通知、应用失焦并检查 viewport 焦点。断连清除选中设备的轴／按钮状态，允许之后重新选定设备；首个事件选择一个手柄，后续其他手柄忽略。失焦释放状态和取消捕获，不静默替游戏决定是否自动打开暂停菜单。

项目销毁菜单、切场景或替换输入组件时，应取消捕获、释放自己取得的暂停原因并清理焦点栈。组件自身会移除原生设备监听；游戏规则的其他订阅由所属项目管理。

## 输入偏好

Godot 使用 `user://`，UE 使用 `Saved/OAGDInput/<文件名>`。示例保存每个绑定和死区；加载时同时检查 profile ID、动作集合、上下文、绑定数量和禁止修改的操作。配置不匹配或损坏时返回错误，当前有效配置不改变。

保存先写临时文件，再替换目标，错误会返回；输入偏好文件不提供完整存档事务；游戏存档、检查点和设置见[本地状态](STATE.zh-CN.md)。Godot 导出模板路径由本机配置，不把作者机器路径固化到分发模板。

## 验证与边界

既有 `tools/runtime_validation.py` 可识别 input 场景并传入正确报告位置。Godot 原生例用 `Input.parse_input_event`；UE 使用 PlayerController InputKey，并在菜单阶段经过 Slate 焦点路由。软件事件、断连处理函数和真实硬件分别标注；模拟断连不能证明实体手柄热插拔兼容。

功能案例检查实际角色移动、暂停期间菜单可操作、恢复时无输入泄漏、多个暂停原因、冲突拒绝、重绑定、恢复默认、偏好加载、无效配置、轴死区、断连清理和焦点恢复。独立包需要另外启动，导出成功不能替代运行检查。

接入后分别检查键鼠、目标手柄、改键、失焦和暂停；实体设备与操作体验需要在游戏中验证。

原生依据：[Godot 输入与 GUI 传播](https://docs.godotengine.org/en/stable/classes/class_input.html)、[Godot 用户数据路径](https://docs.godotengine.org/en/stable/tutorials/io/data_paths.html)、[UE PlayerController InputKey](https://dev.epicgames.com/documentation/unreal-engine/API/Runtime/Engine/APlayerController/InputKey)，以及本机 UE 5.8.2 头文件和实际编译运行。
