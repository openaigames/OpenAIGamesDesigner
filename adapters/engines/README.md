# 引擎接入

首次配置见 [环境清单与操作位置](../environment-setup.md)，按已选择的引擎进入以下说明。

| 引擎 / 框架 | 入口 | 说明 |
| --- | --- | --- |
| Godot | [godot/cli.py](godot/cli.py) | [Godot](godot/README.md) |
| Unity | [unity/cli.py](unity/cli.py) | [Unity](unity/README.md) |
| Unreal | [unreal/cli.py](unreal/cli.py) | [Unreal](unreal/README.md) |
| Three.js | [threejs/__init__.py](threejs/__init__.py) | [网页 3D](threejs/README.md) |
| Phaser | [phaser/__init__.py](phaser/__init__.py) | [网页 2D](phaser/README.md) |

编辑器操作优先复用宿主已有且适合当前任务的 MCP；命令执行由本目录适配器负责。两条路线共享项目设计、任务与验证依据，但 MCP 调用不是 `game_workflow.py run` 的隐式功能。当前 CLI 不发现、安装或代理 MCP 服务。接入方法和证据约定见 [MCP 接入](mcp.md)。

各引擎的公共导入继续使用 `from adapters.engines import unreal` 等形式。运行、测试与交付由各自 `cli.py` 负责；Unity / Unreal 的创建和编辑由各自 `production.py` 负责，两种入口并存。

## 共享文件

| 文件 | 职责 |
| --- | --- |
| `common.py` | 可执行文件检查、自定义命令参数展开 |
| `native_support.py` | 配置检查、证据登记、统一测试结果写入；具体报告解析在 `unity/reports.py` 和 `unreal/reports.py` |
| `registry.py` | 明确选择 Unity / Unreal 制作驱动；不是全部引擎能力注册表 |
| `sessions.py` / `sessions.md` | 执行、检查点、进程归属、中断恢复与说明 |
| `request_contract.py` | 通用请求结构、数值和执行结果检查 |
| `web_common.py` | Three.js / Phaser 共用的初始化、依赖、服务与构建逻辑 |
| `browser_smoke.cjs` | 网页构建的浏览器加载、截图与错误检查 |
| `execution.md` | 通用运行协议和各引擎配置导航 |
| `mcp.md` | 宿主 MCP 接入及证据约定，不是 MCP 服务实现 |
| `web.md` | 网页游戏共同使用方式与浏览器检查配置 |

制作接口按引擎读取 `unity/production.py` 或 `unreal/production.py`，公共执行和恢复读取 `sessions.py`。Godot 从 `adapters.engines.godot` 导入；网页框架分别从 `adapters.engines.threejs` 和 `adapters.engines.phaser` 导入。

只为实际落地且能测试的能力新增模块，例如 `assets.py`、`animation.py`、`playtest.py`；不建立没有实现的分类目录。不内置第三方 MCP 源码，也不预设每个提供方都有同名工具。

各引擎的默认动作、明确配置和证据要求统一见 [引擎执行配置](execution.md)。

Unity / Unreal 的工程创建、场景与组件、资源导入、角色动画、自动操作录制和会话恢复见 [会话管理与引擎入口](sessions.md)。它与现有 run/build/export 和 MCP 入口并存，运行证据分开记录。
