# Godot 执行路线

[命令实现](cli.py) 保留原有 Godot CLI。编辑器自动化按 [MCP 接入](../mcp.md) 发现并验证宿主工具；候选 [Coding-Solo/godot-mcp](https://github.com/Coding-Solo/godot-mcp) 的具体能力以实际工具清单为准。先确认 project.godot 所在路径，再验证场景读写、保存与重新打开；CLI smoke 不能替代这些检查。没有 MCP 时命令路线仍可使用。

需要 Godot 4 的真实可执行文件。工具保留已有 Godot CLI，不会因为新增适配器迁移游戏工程。示例在工具包根执行，`MyGame` 使用实际游戏项目路径。

## 环境配置

| 组件 | 在哪里操作 | 完成检查 |
| --- | --- | --- |
| 项目对应的 Godot 4 | 本机安装 / 解压引擎，项目配置 `godot_executable` 或设置 `GODOT_BIN` | 查询 `--version`，导入项目并运行场景 |
| 导出模板（打包时） | Godot 的 Editor → Manage Export Templates | 安装与引擎匹配的模板 |
| 平台预设和 SDK（打包时） | Godot 导出窗口添加预设；外部 SDK 按目标平台要求安装 | 实际导出，并独立打开产物 |
| MCP（按需） | 候选服务的 Node/npm 环境、Godot 路径及 [助手端配置](../../environment-setup.md#mcp-三端配置) | 当前任务能发现工具，确认工程后验证场景读写和保存 |

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

代码助手根据已确认的范围修改脚本、场景和配置，再运行针对实际规则的测试：

```sh
python tools/game_workflow.py run --project "MyGame" --action test --script tests/test_game.gd --timeout 120
```

测试脚本必须真的执行断言，并在通过时输出 `OAGD_TEST_PASS count=N`（N > 0）。单有该标记不是独立验收依据，需检查脚本的测试含义；退出码或日志错误会影响结果。`tests/fixtures/godot-2d/` 是源码仓库中的联调样例，不属于正式设计，也不包含在个人 Skill 运行包里。

导出需要项目已配置的预设和匹配版本 export templates：

```sh
python tools/game_workflow.py run --project "MyGame" --action export --preset "Windows Desktop" --timeout 600
```

build / export 均按已有预设导出并记录关联文件哈希。默认文件名为 game.exe、模式为 debug；其他平台及 release 可在 `godot` 配置段指定，见 [执行配置](execution.md)。真实独立包需要在目标环境打开、检查资源和日志，不能从模拟测试推断成功。

每次 run 保存输入快照、命令、版本、日志和状态。运行中发现工程文件变化会提示复核；工程哈希不是备份。命令通过不证明手感、视觉、性能或里程碑通过。

参数依据：[Godot 官方命令行说明](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)。
