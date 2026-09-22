# Godot 执行路线

需要 Godot 4 的真实可执行文件。工具保留已有 Godot CLI，不会因为新增适配器迁移游戏工程。示例在工具包根执行，`MyGame` 使用实际游戏项目路径。

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
python tools/game_workflow.py run --project "MyGame" --action test --script res://tests/test_game.gd --timeout 120
```

测试脚本必须真的执行断言，并在通过时输出 `OAGD_TEST_PASS count=N`（N > 0）。单有该标记不是独立验收依据，需检查脚本的测试含义；退出码或日志错误会影响结果。`tests/fixtures/godot-2d/` 是源码仓库中的联调样例，不属于正式设计，也不包含在个人 Skill 运行包里。

导出需要项目已配置的预设和匹配版本 export templates：

```sh
python tools/game_workflow.py run --project "MyGame" --action export --preset "Windows Desktop" --timeout 600
```

当前默认路线生成 Windows debug 包并记录关联文件哈希。Godot 使用 export 执行构建，不支持独立 build 动作。真实独立包需要在目标环境打开、检查资源和日志，不能从模拟测试推断成功。

每次 run 保存输入快照、命令、版本、日志和状态。运行中发现工程文件变化会提示复核；工程哈希不是备份。命令通过不证明手感、视觉、性能或里程碑通过。

参数依据：[Godot 官方命令行说明](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)。
