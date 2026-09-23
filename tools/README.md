# 开始使用

不确定需要安装哪些软件、在哪配置时，先看 [按功能配置环境](../adapters/environment-setup.md)。

当前宿主说明以 Codex 为准，安装目录和配置范围见 [Codex 路径速查](../adapters/environment-setup.md#codex-路径速查)。下文 CLI 通过本地 Python 执行，游戏项目通过 `--project` 指定，不把安装目录当作游戏输出目录。

准备 Python 3.10+。下面命令在工具包根运行；安装的 Skill 使用 `game-preproduction/runtime/` 作为工具包根。示例 `MyGame` 请替换为实际游戏项目的绝对路径。文件工具无需引擎；引擎操作需要真实可执行文件和项目配置。

## 从自然需求开始

在游戏项目目录打开 AI 助手，直接描述目标，例如“我想做一个探索解谜游戏”，或“在这个 UE 工程里增加蓄力攻击”。助手根据当前资料澄清关键未知、选择专业方法并维护项目文件；已有工程从当前目标继续，无需重新立项或指定文档流程，也不会自动生成看板。

仅需文档时可直接使用模板，或生成一个具体任务：

新作的默认布局见 [架构](../workflows/README.md)：专业总入口在游戏根，原生工程在 `game/`，其余目录按需建立。先建立六个非空入口并链接，内容按已知/待定逐步完善，不等主要代码写完才补记录；用户明确只讨论不保存时例外。

以下是助手使用的入口，普通用户无需输入命令或指定 Skill：

```sh
python tools/game_workflow.py scaffold --project "MyGame" --brief "用户的实际游戏需求"
python tools/validate_records.py --project "MyGame" --layout --markdown
```

`scaffold` 创建六个非空入口及管理索引，不选引擎、不生成玩法；未知内容留待讨论，拒绝覆盖任何已有入口。主要实现前保存 GDD/局部规格、技术入口、原型里程碑及任务，从管理文件链接；使用 `--layout --production --markdown` 检查。已有项目保留等价文件与结构，省略 `--layout`。位置和链接检查不证明设计质量或用户确认。

```sh
python tools/game_workflow.py document --project "MyGame" --kind task --id T001 --title "验证核心交互"
python tools/game_workflow.py document --project "MyGame" --kind feature-spec --id F001 --title "蓄力攻击"
```

支持 prototype、vertical-slice、task、feature-spec、asset-spec、validation-report、decision 七种 document 类型；管理由 scaffold、init 或人工建立。新资产规格在 `design/assets/`，已有 `assets/specs/` 沿用。目标文件已存在时拒绝覆盖，已有文档由助手原位修改。

## 在已有项目上修改

直接描述目标，例如“给这个项目增加经济系统”。助手读取当前设计和工程，按需要澄清；在现有 GDD 章节或 design/features 下保存规则，在同一变更/任务记录关联美术表现、技术接口与验证。已有格式优先，各方向只改受影响部分；设计、实现和验证分别记录，尚未确定的标待决。

管理入口链接本轮变更并汇总进展；概览只在定位或核心体验变化时更新。只讨论设计时不执行工程制作，已授权实现则继续修改与验证。工具可检查链接和记录结构，不能自动保证跨专业含义一致。

## 配置引擎执行

Unity / Unreal 新工程与制作操作使用 [engine_workflow.py](engine_workflow.py)：支持原生工程创建、场景/组件、导入与绑定、角色动画、定时试玩录制及会话恢复。请求格式、环境要求和证据范围见 [引擎制作入口与会话](../adapters/engines/sessions.md)。下方 `game_workflow.py init/run` 继续用于已有工程配置和运行、测试、构建。

Godot 新工程及运行见 [Godot 流程](../adapters/engines/godot/README.md)。Unity、Unreal 接手已有工程：

```sh
python tools/game_workflow.py init --project "MyGame" --engine unity --engine-root game --editor "C:/Tools/Unity/Editor/Unity.exe"
python tools/game_workflow.py init --project "MyGame" --engine unreal --engine-root game --editor "C:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --project-file MyGame.uproject
```

两条命令是不同项目的替代示例。init 不覆盖既有 `.openaigame/project.json`；Unity/UE 必须已有原生工程。`--create-engine` 支持 Godot、Three.js 和 Phaser；网页初始化及构建见 [网页游戏](../adapters/engines/web.md)。现有配置要调整时直接编辑并保留项目自己的命令。

```sh
python tools/game_workflow.py run --project "MyGame" --action doctor
python tools/game_workflow.py run --project "MyGame" --action test --task production/tasks/T001.md --timeout 600
python tools/game_workflow.py status --project "MyGame"
```

先确认 task 的真实路径。Unity/UE doctor 只检查可执行文件路径和工程版本声明；不声称验证了编辑器二进制的版本。Unity prepare 批处理导入，play 打开编辑器；Unreal prepare 加载并记录实际工程与版本，play 使用 `-game` 启动。原生 smoke / test / build / export 所需场景、目标、辅助脚本与依赖见 [引擎执行配置](../adapters/engines/execution.md)，已有命令可继续覆盖默认实现。

## 资产任务与记录检查

先按 [资产工具接入](../adapters/assets/README.md) 设置生成 API 或本地命令及请求文件：

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider image --request production/asset-request.json
python tools/asset_workflow.py --project "MyGame" run --job A实际任务编号 --timeout 600
python tools/asset_workflow.py --project "MyGame" status --job A实际任务编号
python tools/validate_records.py --project "MyGame" --markdown
```

提交和执行分开；提交不会启动生成工具。模型可在用户授权的任务内顺序执行，无需用户重复操作。检查命令会报告实际检查的记录数量，零条记录不代表验证过一次运行。Markdown 检查用于本地链接；专业内容、视觉、玩法和资产许可仍需实际检查。

完整试用顺序和每步完成依据见 [分项验证计划](../tests/README.md)。

## 数值表往返

自然语言即可进入，例如“把武器参数整理成我能编辑的表”“把重击伤害改成 60，比较影响”“我改好了这个 Excel，把差异应用到工程并验证”。助手按任务读取策划/技术参考，完成对应操作；以下 CLI 是可重复执行的文件工具，不要求用户手动调用。

`numeric_workflow.py` 支持已存在、已明确绑定的 JSON 记录数组，导出 CSV 工作副本，读取 CSV 或 XLSX 的纯数值页，生成差异后更新已有记录的指定字段。没有引擎工程时由助手先生成候选表与规格；此工具不会从玩法描述自动生成合理数值，也不会自动建立引擎加载器。已有 UE/Unity/Godot 原生数据和项目导入器优先，不为本工具强制改成 JSON。

绑定保存于游戏项目，例如 `design/numerics/combat-binding.json`：

```json
{
  "version": 1,
  "target": "game/data/combat.json",
  "records_key": "attacks",
  "id_field": "id",
  "fields": {
    "damage": { "type": "integer", "unit": "HP/hit", "min": 0, "max": 1000 },
    "cooldown": { "type": "number", "unit": "seconds", "min": 0.01, "max": 10 }
  }
}
```

这里的字段和范围仅为格式示例，需从实际工程与规格确定。目标形如 `{"attacks":[{"id":"LIGHT","damage":30,"cooldown":0.5,"animation":"LightAttack"}]}`；目标为根数组时省略 records_key。支持顶层数组键，不支持任意 JSONPath。ID 必须为稳定字符串，可编辑字段为数字；不修改 animation 等未绑定字段。

```sh
python tools/numeric_workflow.py --project "MyGame" export --binding design/numerics/combat-binding.json --session design/numerics/exchange-01
python tools/numeric_workflow.py --project "MyGame" plan --session design/numerics/exchange-01 --table design/numerics/exchange-01/parameters.csv --out design/numerics/exchange-01/plan.json
python tools/numeric_workflow.py --project "MyGame" apply --plan design/numerics/exchange-01/plan.json
```

export 创建 parameters.csv 和 baseline.json，不覆盖已有会话。用户或助手修改 CSV 后运行 plan，输出 ID、字段、旧值、新值、单位，不写工程。检查差异与项目规则后，在用户已授权应用的范围执行 apply；plan 不是新增人工审批要求。表格再次编辑时用新的 --out 生成计划。

读取用户回传的 Excel，将 --table 指向项目内 `.xlsx`，并使用 `--sheet Parameters` 或实际页名。该页第一行为与 CSV 一致的字段名，只包含 ID 和绑定字段，不含标题装饰、说明列或汇总行；其他页可以保留公式、曲线和说明。XLSX 读取可选依赖 openpyxl，不需要该依赖即可使用 CSV。工具不制作 XLSX；由助手使用宿主可用的表格能力制作。外部文件先以新文件名复制到游戏项目保留原件，不导入聊天里转述的值。

工具拒绝空数值、非法数字、重复/未知 ID、漏行、越界值、字段变化、公式/错误单元格，以及导出后被改动的绑定/配置。不会以 0 填补空白，也不删除或添加记录。用户换行顺序不影响 ID 匹配。公式结果要在可信计算工具中重算并检查后导出纯数值页或 CSV，不能读取旧缓存后直接应用。项目特有的跨字段约束和引用检查需另行执行。

apply 重新比对表格、基线与计划，保存原文件备份和 `.openaigame/numeric-imports/<id>/receipt.json`，再原子替换目标。执行期间暂停竞争写同一文件的其他任务/编辑器导出。检测到工程变化时先重新导出并合并用户修改；工具没有自动三方合并、文件监视或并发锁。状态 configuration_written 仅表示文件已写入，engine_validation 仍是 not_run；之后使用真实工程的导入/重载、配置检查和玩法测试，单独记录证据。

中断时检查 receipt 的 prepared/failed 状态、目标与前后哈希，确认是否已写入。恢复前确认目标没有后续改动，再从 before.json 恢复并另存恢复记录；有后续变更时合并，不能整份覆盖。详细方法在技术 Skill 的数值交换参考。数值导入回执是专项记录，不冒充通用运行或引擎会话记录；通过运行工具执行引擎验证时再生成对应记录。当前结构约定见 [schemas](../schemas/)。


## 实施后的记录回写

交付回复前同步已发生的事实：技术记录实际引擎、架构、工程与运行入口；美术记录已用占位素材、来源及限制；验证记录实际结果、未验证项与中断原因；任务/里程碑更新本轮状态和证据；管理入口更新阶段、目标、工程入口、索引和下一步。阶段可以未完成，不能仍保留“尚未建立”而实际已有工程/里程碑。未来选型待用户决定，已发生事实不等待批准。

新作实施结束（包括失败或被中断）后运行 `validate_records.py --project <项目根> --layout --production --closeout --markdown`；检查报告必须读取并处理，结构不合格不能称项目管理已完成。未能修复时如实保留失败项与下一步，不为了通过修改状态成成功。已有/自定义项目不强套目录，人工核对同等内容。

收尾检查验证六个入口、真实索引、初始占位状态是否残留及证据关联。管理、风险验证、本次任务和里程碑应链接实际的 `runs/<id>/manifest.json`、`runs/engine-*/session.json`、`runs/create-*/session.json`，或 `tests/reports/`、`production/validation/` 中的报告；自定义报告目录通过 `--report-root <项目内相对目录>` 指定。直接引擎调用的报告应记录输入版本、命令、退出码、日志/产物路径和观察边界。工具只查结构与引用，不能证明文档事实已完整或模型确实遵循了交互。

## 引擎辅助脚本

`python tools/engine_setup.py --project "MyGame"` 明确安装 Unity Editor 执行辅助脚本。它不会覆盖已修改的同名文件。Unity/UE 原生测试、构建，以及网页浏览器 smoke 配置见 [引擎执行配置](../adapters/engines/execution.md)。


## 安装一致性与维护测试

每个新分发包在 `game-preproduction/runtime/bundle-manifest.json` 保存内容版本及文件哈希。安装后运行 `python <runtime>/tools/check_installation.py --skills-root <六个Skill的父目录>`，检查缺失或修改的文件。检查只报告差异，不覆盖本地定制，也不删除用户额外文件；更新前比较、备份并合并实际差异。旧安装没有 manifest 时重新打包并同步，不把缺清单当作安装正确。

维护仓库运行 `python tools/run_tests.py` 执行根测试和 Skill 内脚本测试。此入口及 CI 属于源码维护工具，不随游戏运行包分发。

### 素材来源与资产登记

`asset_library.py` 提供分类 sources、Poly Haven 实时 search/files、下载或本地复制 acquire、生成任务 from-job、list/verify/index。使用 [素材获取指南](../adapters/assets/asset-sources.md)；API 任务的 doctor/resume 与凭据配置见 [生成接入](../adapters/assets/generation-api.md)。

### 本机密钥设置页

运行 `python tools/settings_server.py` 打开独立页面，保存 Tripo / 腾讯混元兼容接口 API Key；无需游戏项目。`--status` 只查看配置是否存在，`--no-open` 供宿主自行打开返回的启动链接。详见 [本机设置](../adapters/assets/local-settings.md)。
