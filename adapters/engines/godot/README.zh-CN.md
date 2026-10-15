# Godot 执行路线

[English](README.md) | [简体中文](README.zh-CN.md)

## 选择接入路线

本页说明工程命令、环境与编辑器接入。需要游戏内可复用功能时使用下面的独立模块；它们不会自动替换原项目主场景、角色或规则。

| 任务 | 说明 |
| --- | --- |
| 输入、状态、反馈、交互、导航与基础场景 | [core 运行组件](../runtime_components/README.zh-CN.md) |
| 角色动作加工后的实际导入与采样 | [motion](../motion/README.zh-CN.md) |
| 动画播放、根运动、脚/手约束 | [playback](../motion_playback/README.zh-CN.md) |
| 多节点静态资产、灰盒替换与工程接收 | [静态场景](../static_scene/README.zh-CN.md) |
| 已有组件升级与回退 | [安装与迁移](../../../docs/INSTALLATION.zh-CN.md) |

运行组件、动画播放和静态场景模块使用 Godot 原生资源。导出时需安装与所用引擎匹配的官方导出模板。

## 工程执行路线

[命令实现](cli.py) 保留原有 Godot CLI。编辑器自动化按 [MCP 接入](../mcp.zh-CN.md) 发现并验证 Agent 运行环境工具；候选 [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) 的具体能力以实际工具清单为准。先确认 project.godot 所在路径，再验证场景读写、保存与重新打开；CLI smoke 不能替代这些检查。没有 MCP 时命令路线仍可使用。

需要 Godot 4 的真实可执行文件。工具保留已有 Godot CLI，不会因为新增适配器迁移游戏工程。示例在工具包根执行，`MyGame` 使用实际游戏项目路径。

## 环境配置

| 组件 | 在哪里操作 | 完成检查 |
| --- | --- | --- |
| 项目对应的 Godot 4 | 本机安装 / 解压引擎，项目配置 `godot_executable` 或设置 `GODOT_BIN` | 查询 `--version`，导入项目并运行场景 |
| 导出模板（打包时） | Godot 的 Editor → Manage Export Templates | 安装与引擎匹配的模板 |
| 平台预设和 SDK（打包时） | Godot 导出窗口添加预设；外部 SDK 按目标平台要求安装 | 实际导出，并独立打开产物 |
| MCP（按需） | 候选服务的 Node/npm 环境、Godot 路径及 [Agent 端配置](../../environment-setup.zh-CN.md#mcp-三端配置) | 当前任务能发现工具，确认工程后验证场景读写和保存 |

本候选不要求照搬 UE 的 C++ 插件步骤。具体要求见 [Godot MCP](https://github.com/Coding-Solo/godot-mcp)；导出菜单和模板见 [Godot 官方说明](https://docs.godotengine.org/en/stable/tutorials/export/exporting_projects.html)。Godot .NET 工程另按项目配置 .NET 环境，内置最小样例使用 GDScript。

## 执行示例

```sh
python tools/game_workflow.py init --project "MyGame" --engine-root game --godot "C:/Tools/Godot/Godot.exe" --create-engine
python tools/game_workflow.py run --project "MyGame" --action doctor
python tools/game_workflow.py run --project "MyGame" --action prepare
python tools/game_workflow.py run --project "MyGame" --action smoke --frames 60
python tools/game_workflow.py run --project "MyGame" --action play --timeout 600
```

`--create-engine` 创建最小 Node2D 工程，不生成完整玩法；已有工程省略它。doctor 实际调用 `--version`，prepare 做导入，smoke 做有限帧无画面启动；play 打开交互窗口并等待关闭。关闭窗口前 CLI 会保持运行，超过 timeout 会停止进程。

代码 Agent 根据已确认的范围修改脚本、场景和配置，再运行针对实际规则的测试：

```sh
python tools/game_workflow.py run --project "MyGame" --action test --script tests/test_game.gd --timeout 120
```

测试脚本必须真的执行断言，并在通过时输出 `OAGD_TEST_PASS count=N`（N > 0）。单有该标记不是独立验收依据，需检查脚本的测试含义；退出码或日志错误会影响结果。`tests/fixtures/godot-2d/` 是源码仓库中的自制联调夹具，使用时复制到独立测试项目。维护夹具不进入安装包；安装包的可编辑游戏示例位于 `templates/runtime_examples/`。

导出需要项目已配置的预设和匹配版本 export templates：

```sh
python tools/game_workflow.py run --project "MyGame" --action export --preset "Windows Desktop" --timeout 600
```

build / export 均按已有预设导出并记录关联文件哈希。默认文件名为 game.exe、模式为 debug；其他平台及 release 可在 `godot` 配置段指定，见 [执行配置](execution.zh-CN.md)。真实独立包需要在目标环境打开、检查资源和日志，不能从模拟测试推断成功。

每次 run 保存输入快照、命令、版本、日志和状态。运行中发现工程文件变化会提示复核；工程哈希不是备份。命令通过不证明手感、视觉、性能或里程碑通过。

实际事件、参数、空间与媒体采集见 [共享运行观察](../observations.zh-CN.md#godot-2d)，观察夹具保留在源码仓库的 `tests/fixtures/godot-observation/`。

参数依据：[Godot 官方命令行说明](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)。
