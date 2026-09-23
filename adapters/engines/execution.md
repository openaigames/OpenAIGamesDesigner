# 引擎执行配置

先由用户明确选择引擎、已有工程和目标平台，再填写游戏项目 `.openaigame/project.json`。本页各配置段合并到现有配置；不覆盖已有 `engine_root` 或设计记录。所有示例路径都需要替换。

## 能力范围

| 动作 | Godot | Unity | Unreal | Three.js / Phaser |
| --- | --- | --- | --- | --- |
| doctor | 查询实际二进制版本 | 检查工程及版本声明 | 检查工程及版本声明 | 检查框架声明和本地依赖 |
| prepare | 导入资源 | 批处理导入、编译 | Python commandlet 加载工程并记录真实版本 | 恢复 npm / pnpm 依赖 |
| smoke | 有限帧无画面运行 | 指定场景限时 Play Mode | 指定地图限时 NullRHI 游戏进程 | 真实无头浏览器加载选定构建 |
| test | 项目 GDScript 断言 | Unity Test Framework XML | Automation JSON | 项目自己的行为测试命令 |
| play | 运行游戏 | 打开编辑器，进入 Play 需另操作 | 编辑器 `-game` | 启动本地 Vite 服务 |
| build | 按预设导出 | BuildPipeline.BuildPlayer | UBT 编译明确目标 | Vite 构建 |
| export | 同 build | 同 build，登记交付文件 | UAT 构建、Cook、Stage、Archive | Vite 构建，登记交付文件 |

这些是已实现的执行入口，不表示所有引擎版本和目标平台已实机验证。缺少场景、目标、模块、许可证、测试框架等条件时，应保留 blocked / failed 证据并补齐环境。测试用例仍由当前游戏提供；引擎自带测试通过不能证明游戏规则正确。

## Unity

配置、默认动作与限制见 [对应执行说明](unity/execution.md)。

## Unreal

配置、默认动作与限制见 [对应执行说明](unreal/execution.md)。

## Three.js / Phaser

配置、默认动作与限制见 [对应执行说明](web.md#浏览器检查配置)。

## Godot

配置、默认动作与限制见 [对应执行说明](godot/execution.md)。

## 运行与证据

```sh
python tools/game_workflow.py run --project "MyGame" --action smoke --timeout 180
python tools/game_workflow.py run --project "MyGame" --action test --timeout 600
python tools/game_workflow.py run --project "MyGame" --action export --timeout 3600
```

每轮保存命令、日志、输入哈希和结果；引擎返回错误、缺报告或未生成产物不能通过。超时仅停止该次运行的进程树。Godot 另加实际 `--script` / `--preset`。

Godot、Unity、Unreal 和网页框架的 `commands.<action>` 优先于对应默认执行动作；doctor 始终进行内置环境/配置检查，不运行命令覆盖。自定义测试仍按 [报告协议](../README.md) 生成真实结果。编辑器场景操作和资产制作继续走 [MCP 接入](mcp.md) 或项目脚本，不把命令行补齐当作所有 MCP 已接通。阶段验收、玩法与视觉判断保持单独记录。
## 制作操作入口

Unity / Unreal 的新工程创建、场景与组件编辑、资源导入绑定、动画配置、自动试玩录制和检查点恢复使用 [engine_workflow.py](../../tools/engine_workflow.py)，详见 [会话管理与引擎入口](sessions.md)。本页的 game_workflow run 保持已有运行、测试和构建职责；不要把创建/导入请求塞进 smoke，也不要把 Python/C# 执行称为原生 MCP 连接。
