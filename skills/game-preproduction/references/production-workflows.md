# 制作流程与本地工具

根据当前任务按需读取，不一次加载所有阶段：

| 目的 | 工具包内相对路径 |
| --- | --- |
| 新作/已有工程接入 | workflows/project-intake.md |
| 构建原型并验证 | workflows/prototype-build.md |
| 集成垂直切片并评审 | workflows/vertical-slice.md |
| 新增/修改/修复 | workflows/feature-change.md |
| 资产制作、处理与接入 | workflows/asset-production.md |
| 交付与反馈 | workflows/delivery.md |

上述流程只规定输入、交付、依赖与反馈，不绑定引擎或玩法。依据实际问题选择专业参考：战斗规则由 game-design、表现交接由 game-art-direction、工程实施由 game-technical-design、战斗回归由 game-prototype-validation 负责。原型/切片/修改是一条流程的选择；UE/Godot 与 GAS 是实施方法的选择，不据此新增一套顶层 workflow。

一般策划问题交给 game-design，从其 `references/design-reasoning.md` 理解目标和系统联系，再按需选择共享方法及当前专业参考。战斗、射击、探索、关卡、移动交互与 UI/UX 是可组合的方法，无需用户先选游戏类型，也不要求全部参与；尚无专门参考的新机制仍沿用通用设计与验证方法。跨活动的输入、结果、状态和反馈应按项目真实规则交接，依赖与证据变化见 [变更影响](dependency-and-change-impact.md)。

引擎操作说明在 game-technical-design 的 `references/engine-execution.md` 路由：Godot 使用 `godot-execution.md`；UE 使用 `unreal-project.md`。UE 能力/属性路线未定且即将影响实现时，技术侧用 `ability-system-choice.md` 解释 GAS 与自有实现的取舍；不让用户先懂框架术语，不重复询问已有选择/委托。动作资源与模块通过 `action-animation-integration.md` 对接已需规则及美术方案，GAS 与动作包分别决策。先按宿主提供的位置定位该 Skill；没有可选专业 Skill 时使用项目真实资料与现有工具，不猜路径或宣称依赖已安装。

先定位资源：安装包中使用本 Skill 目录下的 `runtime/` 作为工具包根；开发仓库使用包含 `skills/`、`workflows/`、`tools/` 的仓库根。检查真实路径再调用 `tools/game_workflow.py`，不猜本机固定路径。安装副本没有 runtime、也找不到源工具包时，仍可按专业方法处理文件/工程，说明缺少执行工具；不要宣称已自动接入。

模板位于工具包 `templates/`。CLI 的 document 创建不覆盖的草稿；需要模型填写真实目标与文件关联。不得把模板占位内容当成既定规则。管理入口只维护阶段和链接，任务与里程碑保留各自状态，run manifest 保存机器执行证据。

## 通用模板与文档生成

新项目先 `game_workflow.py scaffold --project <实际根目录> --brief <用户原话>`，生成根目录六个非空入口与专业索引，未知内容标待讨论，随后由模型逐步完善；不依赖引擎。专业总入口留在根，新引擎工程放到 `game/`。`scaffold` 遇已有记录会拒绝，不可拿它覆盖已有游戏。

新项目用 `validate_records.py --project <实际根目录> --layout --markdown` 检查位置；主要实现前增加 `--production` 检查设计、技术及管理所链接的里程碑/任务。已有结构不用该布局检查。运行时携带任务、里程碑和设计输入，保存真实 run，不把零条记录检查成功当成执行验证。

模板固定为项目管理、两类里程碑、任务、功能规格、资产规格、验证报告和重要决定。玩法/美术/技术的差异由各自专业参考展开，不随专题增加平行模板。

| 模板（相对 templates/） | document --kind | CLI 默认输出位置 |
| --- | --- | --- |
| project-management.md | scaffold 建立新作；init 配置工程时按需补建 | Project Management.md |
| milestones/prototype.md | prototype | production/milestones/<id>.md |
| milestones/vertical-slice.md | vertical-slice | production/milestones/<id>.md |
| task.md | task | production/tasks/<id>.md |
| feature-spec.md | feature-spec | design/features/<id>.md |
| asset-spec.md | asset-spec | design/assets/<id>.md（已有 assets/specs 沿用） |
| validation-report.md | validation-report | tests/reports/<id>.md |
| decision.md | decision | production/decisions/<id>.md |

在工具包根运行：`python tools/game_workflow.py document --project "MyGame" --kind feature-spec --id F001 --title "新增交互"`。文档生成不依赖引擎初始化、不安装工具、不创建游戏工程。init 用于选定引擎的已有工程配置或 Godot/网页空工程初始化；新的 Unity/Unreal 工程创建与制作从 `adapters/engines/sessions.md` 进入，使用 `tools/engine_workflow.py`；仅建立管理文件时可直接按模板填写，不必调用 init。已有项目格式或位置不同就原位维护，不为 CLI 默认位置迁移文件。原型和切片共用里程碑目录，使用不同 id；现有目标文件始终拒绝覆盖。

工具能力从共享包 `adapters/engines/README.md` 查询：运行、测试、构建与交付使用 `game_workflow.py`，工程创建和编辑使用 `engine_workflow.py` 的引擎专属制作接口。网页路线读取技术 Skill 的 `references/web-execution.md` 和工具包 `adapters/engines/web.md`。先保存六个入口和本轮交接，再按目标选择适用动作；具体依赖、字段和验证限制只在实现旁维护。执行工具不是游戏生成器；代码助手根据设计和任务修改真实工程，再调用工具记录证据。

资产生成/处理使用工具包 `adapters/assets/README.md` 和 `tools/asset_workflow.py`；仅本地配置命令和 Blender 处理，不预设云服务。任务保存输入快照、日志和产物，生成成功、登记、导入和质量验收分开。`tools/validate_records.py --project <实际路径> --markdown` 检查 schema 定义的结构化记录及本地引用；它不核实专业结论。分项真实验证顺序见工具包 `tests/README.md`。

数值表雏形、用户调参或表格回传从 game-design 的 `references/numeric-authoring.md` 进入，工程写回使用 game-technical-design 的 `references/numeric-exchange.md`。工具包的 `tools/numeric_workflow.py` 提供绑定 JSON 的 CSV 导出、CSV/XLSX 纯数值读取、差异检查与可恢复写回，命令见 `tools/README.md`；原生引擎数据继续使用项目导入器。具体字段与表格在游戏项目保存，不放进 Skill 或通用执行 schema。该能力按需嵌入原型、切片或功能修改，不新增一条数值专属顶层 workflow。

主流程：目标/阶段 → 相关专业输入 → 可执行任务 → 工程实现 → 实际运行/观察 → 回写结果与下一步。用户要可运行原型时，不能仅填文档结束；关键规则未定时先完成独立准备，澄清真正阻塞实验的问题。新作调用 init 或直接开始引擎专用制作前，先解析具体引擎或有效选型委托；“Unity / Unreal 工程”仍需细问，本机可用项与 CLI 默认参数不能代替选择。具体规则见技术 Skill 的 `references/engine-execution.md`。工具缺失或运行失败时保留日志和未验证状态。

代码/资源哈希不是可恢复版本；沿用实际版本控制或备份。命令通过不是玩法、美术或里程碑通过。已有授权不重复请求，评审记录不能伪造用户决定。

引擎编辑器操作可通过宿主 MCP 完成，具体核实和调用交给技术 Skill 的 `references/mcp-engine-integration.md`；共享约定在工具包 `adapters/engines/mcp.md`，各引擎有独立目录说明。项目管理只汇总实际连接、已验证能力和阻塞，不把接入文档写完当作引擎已接通；MCP 输出与命令运行记录分别保存并链接同一任务。

## 项目看板

用户要浏览资产、配置当前项目服务或确认制作时，使用 [项目看板与美术清单](project-workbench.md)。随包 `tools/project_workbench.py` 绑定游戏根；`tools/asset_audit.py` 扫描文件并对照美术记录，模型补齐有依据的归属。
