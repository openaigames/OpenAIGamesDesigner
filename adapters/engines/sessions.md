# 引擎制作入口与会话管理

[engine_workflow.py](../../tools/engine_workflow.py) 是统一 CLI：按项目明确选择的引擎分发请求，并衔接项目文件初始化。具体操作、依赖、参数和启动方式由各引擎维护。

| 位置 | 职责 |
| --- | --- |
| [Unity production.py](unity/production.py) / [说明](unity/production.md) | Unity 创建、请求规则、C# 辅助文件、Editor 与独立 Player 启动 |
| [Unreal production.py](unreal/production.py) / [说明](unreal/production.md) | UE 创建、请求规则、Python worker、commandlet 与 PIE 启动 |
| [registry.py](registry.py) | 明确的引擎注册与选择，不根据已安装软件猜选型 |
| [sessions.py](sessions.py) | 通用运行锁、进程归属、检查点、日志证据、状态和恢复 |
| [request_contract.py](request_contract.py) | JSON 结构、数值、时序及录制证据的通用检查；操作名称与字段由引擎传入 |

共享层不定义 Actor、GameObject、动画或导入字段，不拼原生命令。制作请求通过 `registry.production_driver(engine)` 选择明确的引擎实现，公共检查点和恢复操作从 `sessions` 导入。

## 使用方式

用户通过自然语言说明目标，Agent 按设计和目标引擎生成请求。创建命令和原生操作示例分别见上述引擎说明。原型、切片或功能修改的专业决定仍由相关 Skill 与项目文件维护。

```powershell
python tools/engine_workflow.py execute --project "D:/Games/MyGame" --request "D:/Games/MyGame/production/request.json" --task production/tasks/T001.md --timeout 600
python tools/engine_workflow.py status --project "D:/Games/MyGame" --session engine-实际会话编号
```

`create` 建立新原生工程之前先生成六份方向文档，已有记录不覆盖。接手已有工程沿用 `game_workflow.py init`，不重建工程。`--task` / `--milestone` 关联实际项目内文档。现有 CLI 参数、JSON 请求的 mode（edit/inspect/playback）、输出目录和会话格式保持兼容；对不属于所选引擎的字段明确报错。

## 状态和证据

每次执行保存在 `runs/engine-*/`，包括 `session.json`、确切 `request.json`、`before/` 检查点、原生 `result.json`、进程与引擎日志。自动操作时再保存 `playback.json`、`actions.jsonl`、帧时间 CSV 和启用的录制文件。检查点保留源文件和 Unity .meta，排除 Library、Saved、Binaries 等可再生目录，大型工程需预留空间。

请求文件、导入来源和原生 worker 留存哈希；`validate_records.py --project ...` 检查会话格式、检查点和输出证据。写入后保存与重开读回由各引擎原生实现负责。批次失败时可能已保存部分成果，不能假称原子事务。

CLI 返回 0 表示执行完成，1 表示失败，2 表示 needs_review。原生操作有结果但引擎日志含错误时仍需复核；超时、非零引擎退出、错误身份或缺报告不算完成。接口执行、游戏规则测试、玩法与视觉验收分别记录。

## 并发、中断与恢复

运行前检查目标工程的编辑器进程，目标已打开时拒绝另起批量写入，不关闭用户的编辑器。具体进程名称由引擎提供。运行锁保护本工具同一项目的并发操作，不锁住外部编辑器或手工文件修改。

```powershell
python tools/engine_workflow.py recover --project "D:/Games/MyGame" --session engine-中断编号
python tools/engine_workflow.py restore --project "D:/Games/MyGame" --session engine-需回退编号
```

`recover` 确认会话进程已结束，登记现场并解除对应旧锁，保留 needs_review 状态和返回码 2；不重放未知是否完成的操作。先重新 inspect，判断已完成工作，再发出剩余请求。

`restore` 先验证工程身份、检查点及结束后文件哈希；有后续修改时拒绝覆盖。改后文件和新增文件移到 `displaced-*` 留存，再恢复基线。恢复本身若被打断，需要核对现场与备份。创建在配置写入前失败时保留目录与日志，核实后按已有项目接入继续。

已有合适的原生 MCP 时可以走 [MCP 接入](mcp.md)；原生 Python/C# 操作不冒充 MCP 连接。性能采样方式、录制限制、动画支持范围与环境依赖分别在 Unity / Unreal 说明中定义。


## 创建记录和恢复检查

创建也使用 engine-session 记录：`runs/create-*/session.json` 含 schema_version、operation=create 和创建状态，完成后链接本次原生身份验证的执行 session。默认记录检查同时扫描 create 与 engine 会话；旧记录缺少字段时会报告格式问题，不自动补写或伪造历史证据。

恢复从配置与会话核对工程路径、引擎身份、进程和检查点，不要求损坏工程先通过正常结构检查；文件恢复后再检查引擎入口。后续用户修改、损坏备份、其他会话或存活进程仍会阻止恢复。若恢复了文件但入口仍无效，保留 restored 状态及检查错误供人工复核，不宣称可运行。

管理/任务可以链接真实的 session.json 作为执行证据。收尾检查同时接受 manifest.json、engine-session，以及 tests/reports 或 production/validation 中的报告；自定义报告目录用 `--report-root <项目内相对目录>` 明确指定。记录结构检查与游戏验收始终分开。
