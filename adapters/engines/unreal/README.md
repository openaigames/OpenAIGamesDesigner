# Unreal Engine

[命令适配器](cli.py) 负责工程识别、运行、测试、编译与导出；[制作接口](production.md) 负责工程创建及原生 Python 场景、资源、动画配置和 PIE 操作。根据目标工程选择兼容的编辑器版本。宿主已有适合的 MCP 时，可按 [MCP 接入](../mcp.md) 使用编辑器工具。

## 环境配置

以下以 Windows 为例。已有工程沿用其引擎和依赖，不自动升级。

| 组件 | 适用任务 | 配置位置 | 检查方式 |
| --- | --- | --- | --- |
| Unreal Editor | 打开、制作与运行工程 | Epic Games Launcher 的 Unreal Engine → Library，或已有源码构建 | 用匹配编辑器打开 `.uproject`，核对实际版本 |
| C++ 工具链与 Windows SDK | C++ 工程、源码插件或目标平台编译 | Visual Studio Installer → Modify → Game development with C++，按目标 UE 兼容要求选择组件 | 构建工程实际的 Editor 或游戏目标；VS Code 不提供编译器 |
| PythonScriptPlugin / EditorScriptingUtilities | 使用本工具包的 Python 制作接口 | 工程插件配置；具体启用方式见 [制作接口](production.md) | 脚本能加载工程、执行请求并生成原生结果 |
| 第三方 MCP 及所需引擎插件（可选） | 通过助手直接操作编辑器 | 按提供方说明配置插件、服务及 [助手连接](../../environment-setup.md#mcp-三端配置) | 当前任务发现工具，核对目标工程后执行只读查询 |

纯内容工程是否需要 C++ 工具链取决于使用的插件与构建目标。查询 Visual Studio 安装时可使用 `vswhere -all -products '*' -format json`，以包含独立 Build Tools；最终兼容性依据实际构建日志和目标 UE 的要求核实。

来源：[Epic 的 Visual Studio 环境配置](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine)。

## 工程和命令

在工具包根运行，替换为实际路径；已有工程原位接入：

```sh
python tools/game_workflow.py init --project "MyGame" --engine unreal --engine-root game --editor "D:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --project-file MyGame.uproject
python tools/game_workflow.py run --project "MyGame" --action doctor
```

doctor 检查编辑器文件与工程声明；prepare 加载工程检查，smoke 运行指定地图，test 执行指定 Automation 测试，build 使用 UBT，export 使用 UAT。地图、测试过滤条件、目标和依赖见 [执行配置](execution.md)。

## 制作与保存

| 任务 | 入口 |
| --- | --- |
| 创建内容工程、加载验证 | [创建与启动](production.md#创建与启动) |
| 场景、Blueprint 组件、Actor、资源导入和动画绑定 | [制作请求与支持范围](production.md) |
| PIE 自动操作、帧序列和时间采样 | [自动操作与采样](production.md) |
| 会话状态、检查点与中断恢复 | [会话管理](../sessions.md) |

Python 制作接口、宿主 MCP 和游戏运行逻辑是不同能力。具体操作以接口定义为准；场景保存、引擎运行、游戏行为和性能应分别检查。

## MCP 接入验证

根据所选提供方的版本说明配置插件、服务和助手连接，候选入口见 [MCP 提供方](../mcp.md#候选提供方)。本工具包不内置或自动安装第三方 MCP。

1. 在独立测试工程核对插件编译、加载和服务启动，固定使用的版本与依赖。
2. 发现真实工具清单，核对编辑器工程路径、实例和当前场景；端口监听不等于工程身份正确。
3. 先只读列出对象；验证写入时使用唯一命名的测试对象，修改后重新读取。
4. 保存并重开工程，复查持久化；清理测试对象后再次保存和检查。缺少相应工具时使用实际可用的编辑器方法，不虚构接口。
5. 在测试项目保存调用、日志和检查结果，再将已确认适用的能力用于目标工程。中断后先检查现场，避免重复操作。

第三方提供方的兼容性与工具范围以目标版本的实际结果为准。没有 MCP 时仍可使用工程命令、源码和本工具包的原生制作接口。
