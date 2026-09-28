# Unreal 原生工程验证内容

自制 C++ 验证模块，许可沿用仓库 LICENSE，只使用 Engine BasicShapes，不包含用户剑术包。它证明原生数据、可操作规则、运行绑定、观察和交付接口；不代表成品角色动画或游戏美术。

在隔离项目创建 `ToolkitObservation.uproject`，开启 PythonScriptPlugin、EditorScriptingUtilities，添加 Runtime 模块 ToolkitObservation；将 Source 目录放入工程。UE 5.8.2 / Win64 实际编译与运行；需要兼容的 C++ 工具链。

编译编辑器目标后依次通过共享 `engine_workflow.py execute` 运行本目录 requests：

1. `create-space.json` 建立真实地面、掩体、尺度参照物、镜头、光源。
2. `create-native-fixture.json` 建立原生 UObservationSettings 及使用它的 Pawn。
3. `patch-native.json` 演示显式 read/write 方法、expected 基线检查、保存和角色位置校准。
4. `read-native.json` 在独立进程读回原生值。
5. `observe-complete-flow.json` 在实际 PIE 中驱动并记录命中、取消、胜利、恢复与重试。

这些创建请求只运行一次；失败或超时先用既有 session inspect/recover 确认实际副作用，不能盲重建。新引擎保存的浮点读回若与 expected 不同，先检查真实结果，再构造有依据的新基线，不移除冲突保护。

原生控制：W/S 移动，鼠标左键攻击，Space 取消，R 重试。Pawn 的 Capsule/FloatingPawnMovement 实际碰撞；250cm射线决定命中；原生 CurveFloat 在 .5 处给出21伤害，两次清除42HP目标。HUD 分别显示输入、HP/状态与结束提示。武器是 BeginPlay 动态创建的调试几何，绑定项目自定义 GripAnchor；这个挂点不适用于别的角色。

`observe-complete-flow` 的动作是定时调用游戏处理函数，不能报成人工按键试玩。截图不含声音；本 UE 夹具没有制作音频，声音观察由 Godot 自制夹具覆盖。阶段交付为可编辑原生工程，在明确的 UE 5.8.2 接收环境打开/编译/运行；未声称完成商店包、跨平台发布或任意游戏类型。

Unreal 原包角色与真实动画由 [共享原生动画接口](../../../adapters/engines/unreal/native-animation.md) 处理，与这个无骨架的规则探针分开。旧动画测试场 C++ 可另放入独立实验模块，并启用 ProceduralMeshComponent；不要将其默认附着答案套到业务角色上。
