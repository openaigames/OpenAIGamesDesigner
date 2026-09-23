# Unity

[命令适配器](cli.py) 接手含 `Assets/` 和 `ProjectSettings/ProjectVersion.txt` 的实际工程。选定编辑器版本后配置 `editor_executable`；工程声明版本与本机编辑器实际版本分别核实。

新工程创建、场景/组件编辑、资源与动画配置、独立运行包自动操作见 [制作接口](production.md)。

## 环境配置

| 组件 | 在哪里操作 | 完成检查 |
| --- | --- | --- |
| 项目对应 Unity Editor | Unity Hub 的 Installs 管理目标版本 | 工程导入完成、脚本编译无错误 |
| 目标平台构建模块 | Unity Hub 中对应编辑器的模块管理入口 | 编辑器能选择目标平台并实际生成构建；额外 SDK 按目标平台要求配置 |
| 工程包依赖 | Unity 的 Package Manager，沿用工程的 Packages 配置 | 所需包恢复成功，进入 Play 验证 |
| MCP 编辑器包（按需） | 按所选提供方说明在 Package Manager 安装匹配版本 | MCP 包加载成功并能识别目标编辑器实例 |
| MCP 服务与助手连接（按需） | 提供方的 Python / uv 环境及 [助手端配置](../../environment-setup.md#mcp-三端配置) | 实际工具可用，并完成测试对象保存重开 |

安装说明：[Unity Hub](https://docs.unity.com/en-us/hub)、[MCP 候选提供方](https://github.com/CoplayDev/unity-mcp)。MCP 包、服务和项目依赖分别安装，不随本工具包分发；菜单名称以实际 Hub / Editor 版本为准。

## 命令能力

| 动作 | 默认能力 | 项目需补充 |
| --- | --- | --- |
| doctor | 文件和声明版本检查 | 编辑器实际版本 / 渲染管线 / 包依赖验证 |
| prepare | batchmode 导入并退出 | 项目特殊导入与包恢复要求 |
| play | 打开编辑器 | 进入 Play、实际操作与退出观察 |
| smoke | 辅助脚本限时 Play Mode | 实际场景、明确安装辅助脚本 |
| test | Unity Test Framework | 测试平台和实际用例，读取原始 XML |
| build / export | BuildPipeline.BuildPlayer | 辅助脚本、场景列表、目标平台和模块 |

初始化使用 `game_workflow.py init --engine unity`，其余参数见 [工具说明](../../../tools/README.md)。命令参数、`executeMethod` 等项目包装和报告格式见 [适配器协议](../../README.md)。默认辅助脚本、安装步骤和各动作配置见 [执行配置](execution.md)；已有工程方法可以继续用 `commands` 覆盖。

编辑器操作遵循 [MCP 接入](../mcp.md)。候选 [CoplayDev/unity-mcp](https://github.com/CoplayDev/unity-mcp) 提供编辑器包与服务，需固定兼容版本并发现实际启用的工具组。多编辑器场景先确认目标会话；包已安装不代表已连接。首先验证读取 → 修改测试对象 → 保存重开，再按需求验证资产导入、Play 和测试报告。工具返回成功不代替 Console、场景持久化和游戏行为检查。

采用现有工程架构与资产方案，不根据“Unity 已安装”推定用户已选 Unity；服务缺失时可沿用项目脚本，不自动安装其他引擎。
