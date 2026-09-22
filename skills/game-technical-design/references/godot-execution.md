# Godot 本地执行与证据

仅实际工程采用 Godot 且需要执行时读取；这是引擎操作说明，不是独立制作工作流。原型、切片和功能修改仍复用通用 workflow。

需要 Python 3.10+（仅标准库）和 Godot 4。工具包根目录运行以下命令；安装版工具路径见管理 Skill 的 production-workflows 参考。项目路径可有空格，命令参数应单独传递。首轮 `doctor` 返回真实引擎版本后可将完整版本字符串写入 `.openaigame/project.json` 的 `expected_version` 以检测漂移。

```sh
python tools/game_workflow.py init --project "MyGame" --godot "C:/Tools/Godot.exe" --create-engine
python tools/game_workflow.py document --project "MyGame" --kind prototype --id M001 --title "首个机制验证"
python tools/game_workflow.py document --project "MyGame" --kind task --id T001 --title "实验场景实现"
```

已有工程用 `--engine-root` 指定相对位置，不带 `--create-engine`。已有配置拒绝重复初始化；要改变配置先核实工程和版本再编辑。模板需要按真实需求填写并关联管理文件，程序不会替用户决定规则。

```sh
python tools/game_workflow.py run --project "MyGame" --action doctor
python tools/game_workflow.py run --project "MyGame" --action prepare --task production/tasks/T001.md --milestone production/milestones/M001.md
python tools/game_workflow.py run --project "MyGame" --action smoke --frames 180
python tools/game_workflow.py run --project "MyGame" --action test --script tests/test_game.gd --task production/tasks/T001.md
python tools/game_workflow.py run --project "MyGame" --action play --timeout 600
python tools/game_workflow.py run --project "MyGame" --action export --preset "Windows Desktop"
python tools/game_workflow.py status --project "MyGame"
```

`prepare` 导入/检查工程；`smoke` 无画面启动若干帧；`test` 执行工程相对路径的 SceneTree 测试脚本；`play` 打开游戏窗口，关闭后记录结果，超时会终止该次进程；`export` 生成 Windows debug 包，需要预设和匹配导出模板。引擎程序路径可以通过配置或 `GODOT_BIN` 指定。

测试脚本遇到失败必须输出错误并 `quit(1)`，只有所有真实断言完成后才输出 `OAGD_TEST_PASS count=N`（N 为正整数），然后 `quit(0)`。执行器同时检查退出码、Godot 错误日志和成功标记；标记不是测试框架，断言内容仍由任务决定。不要为了通过工具伪造标记。

每次 run 保存命令、退出码、日志、工具版本/哈希、源文件哈希、指定输入文件快照和产物哈希。`--input` 可多次追加；任务/里程碑会自动作为输入快照。并发编辑导致源文件变化时，除导入外成功状态变为 `needs_review`。导入可能创建 `.uid` 等资源标识，后续运行以新源文件为基线。

状态：passed / failed / blocked / timeout / cancelled / needs_review。`command_status` 单独记录命令退出，`gameplay_validation` 和 `visual_validation` 保持 not_run，由实际评审文件补充证据。命令不会自动修改任务状态或批准阶段。

局限：不自动生成玩法、安装插件/导出模板、采集性能或判断画面；不从 Markdown 执行任意 shell；源哈希不是备份，外部依赖需另记录，外部链接的工程资源需先明确来源。`runs` / `builds` 为保留的生成目录，不存放手写游戏源文件。

官方依据：[命令行文档](https://docs.godotengine.org/en/stable/tutorials/editor/command_line_tutorial.html)。
