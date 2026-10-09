# 开始使用

项目工作台提供资产库、生成服务和生成任务三个页面：`python tools/project_workbench.py --project "MyGame" --view assets`。资产库先按候补／游戏应用范围筛选，再按资产分类、用途标签和文件类型查找；每个文件显示主分类标签，分类与对象共享标签分别维护。模型详情可切换实际绑定的角色动作并使用播放控件；看板不提供动作取舍或动作检查界面。“素材方案”展示组合能力、缺口与来源。项目阶段和运行观察仍使用既有 CLI、记录及报告，不依赖独立看板页面。预览与角色清单接口见 [看板说明](workbench/README.md)，操作流程见 game-preproduction Skill 的 `references/project-workbench.md`。

不确定需要安装哪些软件、在哪配置时，先看 [按功能配置环境](../adapters/environment-setup.md)。

不同 Agent 可共用这些 Python 命令；Skill 安装与工具连接方式见 [Agent 接入步骤](../adapters/environment-setup.md#agent-接入步骤)。游戏项目通过 `--project` 指定，安装目录与游戏输出目录分别维护。

准备 Python 3.10+。下面命令在工具包根运行；安装的 Skill 使用 `game-preproduction/runtime/` 作为工具包根。示例 `MyGame` 请替换为实际游戏项目的绝对路径。文件工具无需引擎；引擎操作需要真实可执行文件和项目配置。

场景材质与参数来源、实际布景净空、固定机位对照及跨引擎打包使用 `environment_workflow.py`；Blender 表面测量、烘焙和静态导出使用专门配方。按当前任务需要选择，入口与数据说明见 [场景制作工具](../skills/game-environment-art/references/environment-tools.md)。

## 从自然需求开始

在游戏项目目录打开 Agent，直接描述目标，例如“我想做一个探索解谜游戏”，或“在这个 UE 工程里增加蓄力攻击”。Agent 根据当前资料澄清关键未知、选择专业方法并维护项目文件；已有工程从当前目标继续，无需重新立项或指定文档流程；项目看板按需启动。

仅需文档时可直接使用模板，或生成一个具体任务：

新作的默认布局见 [架构](../workflows/README.md)：专业总入口在游戏根，原生工程在 `game/`，其余目录按需建立。先建立六个非空入口并链接，内容按已知/待定逐步完善，不等主要代码写完才补记录；用户明确只讨论不保存时例外。

以下是 Agent 使用的入口，普通用户无需输入命令或指定 Skill：

```sh
python tools/game_workflow.py scaffold --project "MyGame" --brief "用户的实际游戏需求"
python tools/validate_records.py --project "MyGame" --layout --markdown
```

`scaffold` 创建六个非空入口及管理索引，不选引擎、不生成玩法；未知内容留待讨论，拒绝覆盖任何已有入口。主要实现前保存 GDD/局部规格、技术入口、原型里程碑及任务，从管理文件链接；使用 `--layout --production --markdown` 检查。已有项目保留等价文件与结构，省略 `--layout`。位置和链接检查不证明设计质量或用户确认。

```sh
python tools/game_workflow.py document --project "MyGame" --kind task --id T001 --title "验证核心交互"
python tools/game_workflow.py document --project "MyGame" --kind feature-spec --id F001 --title "蓄力攻击"
```

支持 prototype、vertical-slice、content-production、task、feature-spec、asset-spec、validation-report、decision 八种 document 类型；content-production 用于内容制作里程碑。管理由 scaffold、init 或人工建立。新资产规格在 `design/assets/`，已有 `assets/specs/` 沿用。目标文件已存在时拒绝覆盖，已有文档由 Agent 原位修改。

## 阶段任务与证据

`document --kind task` 创建 Markdown 专业说明。需要按五阶段连续区间记录计划、状态、依赖和评审时，使用 `task` 子命令；两者用途不同，生成 Markdown 不会自动建立阶段状态记录。

```sh
python tools/game_workflow.py task --project "MyGame" create --spec production/task-request.json
python tools/game_workflow.py task --project "MyGame" show --id T001
python tools/record_evidence.py --project "MyGame" --register production/evidence-request.json
```

请求文件需先按实际目标填写，结构分别见 [任务约定](../schemas/task.schema.json) 和 [证据约定](../schemas/evidence.schema.json)。阶段范围、推进和恢复见 [阶段区间执行](../workflows/stage-execution.md)，实际事件/空间记录见 [运行观察](../adapters/engines/observations.md)。专业小修可沿用已有任务，无需强制创建完整阶段档案。

## 在已有项目上修改

直接描述目标，例如“给这个项目增加经济系统”。Agent 读取当前设计和工程，按需要澄清；在现有 GDD 章节或 design/features 下保存规则，在同一变更/任务记录关联美术表现、技术接口与验证。已有格式优先，各方向只改受影响部分；设计、实现和验证分别记录，尚未确定的标待决。

管理入口链接当前任务变更并汇总进展；概览只在定位或核心体验变化时更新。只讨论设计时不执行工程制作，已授权实现则继续修改与验证。工具可检查链接和记录结构，不能自动保证跨专业含义一致。

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

模型与表格由 `game-numerical-design` 维护方法，规则仍归系统/战斗等对应专业，技术负责实际写回；旧 `game-design` 数值表路径保留导航。

自然语言即可进入，例如“把武器参数整理成我能编辑的表”“把重击伤害改成 60，比较影响”“我改好了这个 Excel，把差异应用到工程并验证”。Agent 按任务读取策划/技术参考，完成对应操作；以下 CLI 是可重复执行的文件工具，不要求用户手动调用。

`numeric_workflow.py` 支持已存在、已明确绑定的 JSON 记录数组，导出 CSV 工作副本，读取 CSV 或 XLSX 的纯数值页，生成差异后更新已有记录的指定字段。没有引擎工程时由 Agent 先生成候选表与规格；此工具不会从玩法描述自动生成合理数值，也不会自动建立引擎加载器。已有 UE/Unity/Godot 原生数据和项目导入器优先，不为本工具强制改成 JSON。

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

export 创建 parameters.csv 和 baseline.json，不覆盖已有会话。用户或 Agent 修改 CSV 后运行 plan，输出 ID、字段、旧值、新值、单位，不写工程。检查差异与项目规则后，在用户已授权应用的范围执行 apply；plan 不是新增人工审批要求。表格再次编辑时用新的 --out 生成计划。

读取用户回传的 Excel，将 --table 指向项目内 `.xlsx`，并使用 `--sheet Parameters` 或实际页名。该页第一行为与 CSV 一致的字段名，只包含 ID 和绑定字段，不含标题装饰、说明列或汇总行；其他页可以保留公式、曲线和说明。XLSX 读取可选依赖 openpyxl，不需要该依赖即可使用 CSV。工具不制作 XLSX；由 Agent 使用 Agent 可用的表格能力制作。外部文件先以新文件名复制到游戏项目保留原件，不导入聊天里转述的值。

工具拒绝空数值、非法数字、重复/未知 ID、漏行、越界值、字段变化、公式/错误单元格，以及导出后被改动的绑定/配置。不会以 0 填补空白，也不删除或添加记录。用户换行顺序不影响 ID 匹配。公式结果要在可信计算工具中重算并检查后导出纯数值页或 CSV，不能读取旧缓存后直接应用。项目特有的跨字段约束和引用检查需另行执行。

apply 重新比对表格、基线与计划，保存原文件备份和 `.openaigame/numeric-imports/<id>/receipt.json`，再原子替换目标。执行期间暂停竞争写同一文件的其他任务/编辑器导出。检测到工程变化时先重新导出并合并用户修改；工具没有自动三方合并、文件监视或并发锁。状态 configuration_written 仅表示文件已写入，engine_validation 仍是 not_run；之后使用真实工程的导入/重载、配置检查和玩法测试，单独记录证据。

中断时检查 receipt 的 prepared/failed 状态、目标与前后哈希，确认是否已写入。恢复前确认目标没有后续改动，再从 before.json 恢复并另存恢复记录；有后续变更时合并，不能整份覆盖。详细方法在技术 Skill 的数值交换参考。数值导入执行记录是专项记录，不冒充通用运行或引擎会话记录；通过运行工具执行引擎验证时再生成对应记录。当前结构约定见 [schemas](../schemas/)。


## 实施后的记录更新

交付回复前同步已发生的事实：技术记录实际引擎、架构、工程与运行入口；美术记录已用占位素材、来源及限制；验证记录实际结果、未验证项与中断原因；任务/里程碑更新当前任务状态和证据；管理入口更新阶段、目标、工程入口、索引和下一步。阶段可以未完成，不能仍保留“尚未建立”而实际已有工程/里程碑。未来选型待用户决定，已发生事实不等待批准。

新作实施结束（包括失败或被中断）后运行 `validate_records.py --project <项目根> --layout --production --closeout --markdown`；检查报告必须读取并处理，结构不合格不能称项目管理已完成。未能修复时如实保留失败项与下一步，不为了通过修改状态成成功。已有/自定义项目不强套目录，人工核对同等内容。

收尾检查验证六个入口、真实索引、初始占位状态是否残留及证据关联。管理、风险验证、本次任务和里程碑应链接实际的 `runs/<id>/manifest.json`、`runs/engine-*/session.json`、`runs/create-*/session.json`，或 `tests/reports/`、`production/validation/` 中的报告；自定义报告目录通过 `--report-root <项目内相对目录>` 指定。直接引擎调用的报告应记录输入版本、命令、退出码、日志/产物路径和观察边界。工具只查结构与引用，不能证明文档事实已完整或模型确实遵循了交互。

## 引擎辅助脚本

`python tools/engine_setup.py --project "MyGame"` 明确安装 Unity Editor 执行辅助脚本。它不会覆盖已修改的同名文件。Unity/UE 原生测试、构建，以及网页浏览器 smoke 配置见 [引擎执行配置](../adapters/engines/execution.md)。


## 安装一致性与维护测试

每个新分发包在 `game-preproduction/runtime/bundle-manifest.json` 保存内容版本及文件哈希。安装后运行 `python <runtime>/tools/check_installation.py --skills-root <已安装Skill的父目录>`，检查缺失、修改及工具包 Skill 目录内额外的文件（`missing`、`changed`、`extra`）。其他 Skill 和根目录个人文件不参与检查。检查只报告差异，不覆盖本地定制，也不删除用户额外文件；更新前比较、备份并合并实际差异。旧安装没有 manifest 时重新打包并同步，不把缺清单当作安装正确。

维护仓库运行 `python tools/run_tests.py` 执行根测试和 Skill 内脚本测试，包括 `game-animation-pipeline` 的协议检查；`--group game-animation-pipeline` 可单独运行该组。此入口及 CI 属于源码维护工具，不随游戏运行包分发。

发布时从源码仓库重新运行 `tools/package_skills.py`，不要把个人安装目录整体上传。打包器独立排除本地密钥、环境配置、运行日志、项目记录、缓存和工作输出；`.gitignore` 同时防止这些文件被常规 Git 添加操作选中。`.env.example` 与 `.env.template` 仅用于不含真实凭据的配置示例。维护者自己的发布草稿和验证执行记录留在仓库外或已忽略的本地目录。

协议／Schema 版本用于数据兼容，依赖版本与许可证用于追溯，`bundle_id` 标识包的实际内容，均应保留。当前文件排除规则不会移除已经提交的 Git 历史；发布前须另行检查准备推送的历史。

### 素材来源与资产登记

`asset_library.py` 的 `sources` 支持类型、收费（`--pricing free|mixed|paid|unknown`）、登录要求和获取方式分别筛选；收费分类按来源范围精确匹配，混合网站仍需核对所选版本的价格。另提供 Poly Haven 实时 search/files、下载或本地复制 acquire、生成任务 from-job、list/verify/index。使用 [素材获取指南](../adapters/assets/asset-sources.md)；API 任务的 doctor/resume 与凭据配置见 [生成接入](../adapters/assets/generation-api.md)。

### 本机密钥设置页

运行 `python tools/settings_server.py` 打开独立页面，保存 Tripo / 腾讯混元兼容接口 / ElevenLabs / 火山方舟 API Key（Seedream 与 Seedance 共用）；无需游戏项目。`--status` 只查看配置是否存在，`--no-open` 供 Agent 运行环境自行打开返回的启动链接。详见 [本机设置](../adapters/assets/local-settings.md)。

## 项目看板与资产核查

```sh
python tools/project_workbench.py --project "MyGame"
python tools/project_workbench.py --project "MyGame" --view services
python tools/project_workbench.py --project "MyGame" --approve-job A实际任务编号
python tools/asset_audit.py --project "MyGame"
```

`MyGame` 换成游戏根目录的绝对路径。看板使用同一套界面，绑定当前项目，在自动分配的本机端口启动；`--no-open --ready-file <新临时文件>` 可交给 Agent 运行环境打开返回地址。同一台电脑的不同浏览器可以直接使用相同地址，页面自动建立连接，无需一次性链接；服务仍只监听 `127.0.0.1`，写入保留 Origin 与 CSRF 校验。默认闲置 120 分钟退出，关闭页面不立即停止服务。用户游戏资产留在游戏项目，网页和 Three.js 在共享 runtime。分发包包含可再分发的自制验证夹具，位于 runtime 的 `tests/fixtures/`；用户真实工程与素材不随包分发。完整维护测试和打包脚本只在源码仓库。

支持本地 3D、图片、音频、视频、粒子演示和引擎文件索引。实时 3D 支持 GLB/glTF、OBJ（含项目内 MTL/贴图）和 FBX 模型/骨架/动作。缺贴图和不兼容骨架会显示具体限制；浏览器不执行 Niagara、AnimBP、碰撞或引擎最终材质。动作预览可跟随角色或查看完整位移轨迹，不修改源资产。标签来自现有美术记录，未登记资产仍可浏览。

引擎角色使用实际使用方导出及 `engine_characters.py` 同步到现有 `.asset-browser/characters.json` / `previews.json`。选择角色即可选择工程关联动作，并区分组件直接绑定、AnimBP 静态引用和工程声明可用集合。导出预览支持 FBX 和 GLB；原文件、派生文件及所列依赖均冻结 SHA256，变更后旧预览失效。项目配置的内容根决定候补/游戏应用归属，运行备份和派生预览不再作为候补重新扫描。浏览器动作与游戏最终表现分开，原生导出接口的限制见 [Unreal 原生动画](../adapters/engines/unreal/native-animation.md)。

资产归属的内容根、排除目录和配置示例见 [游戏内容根](workbench/README.md#游戏内容根)。模型预览保留动画播放控件。旧片段判断的查询、保存与导出协议见 [历史动作取舍接口](workbench/motion-review.md)，当前看板不提供该表单。历史判断不移动文件，也不替代引擎验证。

数值预测调用 `numeric_workflow.py --project <项目> model --request <相对请求.json> --out production/numeric-models/<版本>.json`。支持明确算式树、分段线性曲线和阶梯阈值；参数与实测引用实际 JSON pointer、权威文件和执行记录。输出 JSON 数据和可独立打开的 HTML 比较报告；`model-check --report <相对报告>` 检查依赖新鲜度。模型不覆盖游戏权威参数，不把预测当实测或最优手感。

旧项目初次建立记录区使用 `asset_audit.py --project "MyGame" --init-art`，保留原文；`--register-missing` 只登记文件事实。模型再依据原清单补齐对象和标签，沿用稳定 ID，未知用途保留待补齐。自定义美术入口用项目 `.openaigame/workbench.json` 的 `art_document` 相对路径。固定标记区格式与旧记录映射由专业 Skill 的项目看板参考说明。

服务页复用本机加密存储，保存不发起生成；制作页读取实际 asset-jobs，可建立 API 文本请求并核对已有请求。用户确认后由 Agent 运行现有 asset_workflow，界面不模拟进度、不自行调用生成平台。独立设置页仍适用于无游戏项目的配置。

## 图像与视频生成

`asset_workflow.py --provider seedream` 支持文生单图及单参考图改绘；`--provider seedance` 支持文生视频及首帧生视频，查询任务 ID 后下载到本地。看板支持相应参数、参考图选择及逐次授权。Seedance 可恢复原任务；Seedream 不自动重发同步请求。配置、模型范围及示例见 [方舟图像与视频接入](../adapters/assets/ark-generation.md)。

## 音频生成与时序校准

`asset_workflow.py --provider elevenlabs` 使用同一密钥设置、任务授权与资产登记流程；看板新建任务支持音效、配乐及角色台词。`audio_workflow.py` 提供本地 WAV 测量、MP3 解码与游戏窗口裁剪，保留原件并输出新修订及配方。具体输入与命令见 [ElevenLabs 游戏音频](../adapters/assets/elevenlabs-audio.md)。解码依赖 FFmpeg；不把文件时长匹配当作听感或引擎验证通过。


### 按用途浏览资产

资产库以“全部资产”为入口，按人物角色、武器装备、道具模型、地图场景、动画资源、特效美术、材质贴图、音乐音效、二维美术与 UI、插件代码、蓝图与玩法模板分类，并保留未分类资产。音乐音效可筛选配乐、音效、配音。侧栏先选资产范围，再按资产分类与用途标签筛选，目录、搜索和收藏继续独立使用。旧专题仅保留历史数据兼容。

分类优先采用与当前文件版本匹配的已保存记录，其次使用已有角色绑定、已登记引擎类型、文件内容／格式和目录建议。普通 FBX 或 `.uasset` 不会仅凭扩展名被认作角色或蓝图模板；信息不足时保留未分类。含动作片段的模型也可从动画资源中找到，分类统计可能有交叉，不复制文件、不推断动作适配或品质通过。

卡片与详情显示独立分类标签。在详情中展开“修改分类”，可以保存主分类和音频细分；“恢复自动”清除手动覆盖。顶部“批量分类”作用于当前筛选结果，包含其他分页，保存前显示数量，每次最多 500 项。手动分类保存在项目 `.openaigame/asset-taxonomy.json`，刷新保留，并记录当前文件 SHA-256；替换或移动需要核对，并发修改或损坏记录不会被静默覆盖。此记录只保存分类，共享用途标签和对象归属继续由 Art Direction 管理，使用范围仍由实际内容目录决定。

插件描述文件、常用代码和着色器文件可以列出并分类，不执行或自动安装代码。浏览预览能力仍取决于原文件格式；分类不会让原本不能浏览的引擎资产自动获得预览。


## 资产版本与内置工具结果

`asset_versions.py --project <项目> list` 读取历史；`apply --request request.json` 执行显式版本操作。请求路径相对项目，文件必须在项目内。通用操作为 create（title、kind、files）、add（group、files）、select（group、version、reason）、archive（group、version、archived）。文件数组接受路径或 `{ "path": "...", "sha256": "...", "role": "正面" }`；父版本 parent、参考 references 和说明 note 可选。相同交付物不同方案各保存一版，多视图／贴图依赖放入同版 files。revision 可用于乐观并发校验。

`record-native --request native-result.json` 登记 Agent 内置工具已经实际完成并保存的文件；不会调用模型或云服务。例如：

```json
{
  "prompt": "保持盔甲结构，调整配色",
  "tool": "builtin:imagegen",
  "inputs": ["concepts/hero-base.png"],
  "outputs": ["concepts/hero-front.png", "concepts/hero-side.png", "concepts/hero-alternative.png"],
  "output_sets": [["concepts/hero-front.png", "concepts/hero-side.png"], ["concepts/hero-alternative.png"]]
}
```

`tool` 填实际使用工具，示例名不能代替执行证据。已有看板内置任务时传 `job`，沿用其输入快照与参数；执行前读取快照并使用实际工具，完成后再登记输出。图像多个输出默认各自成版；同方案多文件明确用 output_sets 分组，每个输出恰好出现一次。不同方案共用原底稿，不会自动串成修改链。

修改或参考已登记版本时加入 `lineage: { "group": "实际组ID或null", "parent": "实际版本ID或null", "note": "修改说明", "references": [{ "group": "参考组ID", "version": "参考版本ID", "role": "配色参考" }] }`。ID 从 list 返回读取，不自行编造。图像任务自动把关联的主图加入真实输入快照；使用手动输入时也必须与真正传给工具的文件一致。当前内置任务最多准备五张图；超限或不支持的格式返回错误。非图像生成的参考关联只提供生产依据，不宣称自动上传图像。

API／本地命令任务 succeeded 或外部注册 registered 后自动保存版本，结果从 job 的 asset_version 查看。登记失败保留实际输出并写 version_registration_error；`link-job --job <任务ID>` 可恢复登记，不重新生成。相同任务输出的重复登记不产生重复版本。

版本记录与不可覆盖的副本保存在 `.openaigame/asset-versions`；已有 Art Direction 的摘要区链接当前选用和最新结果。重新选用只修改记录，游戏文件不改变；保存快照、可打开、选用、工程接入和品质验收分别判断。额外副本会占用磁盘，归档只折叠显示，不删除原件。

## 动作时间检查

`action_workflow.py` 安装当前引擎的记录器、导入实际事件、列出和比较历史记录。工作台不提供动作检查页面，旧 `--view actions` 参数转到资产库。输入路径须位于当前游戏项目内；动作设定可选，缺少时只显示实测。详细方法见 [跨引擎动作记录](../adapters/engines/action_timing/README.md)。
