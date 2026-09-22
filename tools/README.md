# 开始使用

准备 Python 3.10+。下面命令在工具包根运行；安装的 Skill 使用 `game-preproduction/runtime/` 作为工具包根。示例 `MyGame` 请替换为实际游戏项目的绝对路径。文件工具无需引擎；引擎操作需要真实可执行文件和项目配置。

## 从自然需求开始

在游戏项目目录打开 AI 助手，直接描述目标，例如“我想做一个探索解谜游戏”，或“在这个 UE 工程里增加蓄力攻击”。Skill 应根据当前资料澄清关键未知、选择专业方法、维护需要的文件；已有工程从本轮目标继续，不重新立项。不需要让用户输入内部流程，也不自动生成看板。

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

Godot 新工程及运行见 [Godot 流程](../adapters/engines/godot.md)。Unity、Unreal 接手已有工程：

```sh
python tools/game_workflow.py init --project "MyGame" --engine unity --engine-root game --editor "C:/Tools/Unity/Editor/Unity.exe"
python tools/game_workflow.py init --project "MyGame" --engine unreal --engine-root game --editor "C:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --project-file MyGame.uproject
```

两条命令是不同项目的替代示例。init 不覆盖既有 `.openaigame/project.json`；Unity/UE 必须已有原生工程。`--create-engine` 仅支持 Godot。现有配置要调整时直接编辑并保留项目自己的命令。

```sh
python tools/game_workflow.py run --project "MyGame" --action doctor
python tools/game_workflow.py run --project "MyGame" --action test --task production/tasks/T001.md --timeout 600
python tools/game_workflow.py status --project "MyGame"
```

先确认 task 的真实路径。Unity/UE doctor 只检查可执行文件路径和工程版本声明；不声称验证了编辑器二进制的版本。默认 Unity prepare 启动批处理导入，play 打开编辑器（不自动进入 Play Mode）；Unreal play 使用 `-game` 启动游戏。其余能力要配置项目命令，方法见 [扩展适配器](../adapters/README.md)。

## 资产任务与记录检查

先按 [资产工具接入](../adapters/assets/README.md) 设置本地命令及请求文件：

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider image --request production/asset-request.json
python tools/asset_workflow.py --project "MyGame" run --job A实际任务编号 --timeout 600
python tools/asset_workflow.py --project "MyGame" status --job A实际任务编号
python tools/validate_records.py --project "MyGame" --markdown
```

提交和执行分开；提交不会启动生成工具。模型可在用户授权的任务内顺序执行，无需用户重复操作。检查命令会报告实际检查的记录数量，零条记录不代表验证过一次运行。Markdown 检查用于本地链接；专业内容、视觉、玩法和资产许可仍需实际检查。

完整试用顺序和每步完成依据见 [分项验证计划](../tests/README.md)。


## 实施后的记录回写

交付回复前同步已发生的事实：技术记录实际引擎、架构、工程与运行入口；美术记录已用占位素材、来源及限制；验证记录实际结果、未验证项与中断原因；任务/里程碑更新本轮状态和证据；管理入口更新阶段、目标、工程入口、索引和下一步。阶段可以未完成，不能仍保留“尚未建立”而实际已有工程/里程碑。未来选型待用户决定，已发生事实不等待批准。

新作实施结束（包括失败或被中断）后运行 `validate_records.py --project <项目根> --layout --production --closeout --markdown`；检查报告必须读取并处理，结构不合格不能称项目管理已完成。未能修复时如实保留失败项与下一步，不为了通过修改状态成成功。已有/自定义项目不强套目录，人工核对同等内容。

收尾检查验证六个入口、真实索引、初始占位状态是否残留及证据关联。管理、风险验证、本次任务和里程碑应链接 `runs/<id>/manifest.json` 或 `tests/reports/<id>.md`。直接引擎调用的报告应记录输入版本、命令、退出码、日志/产物路径和观察边界。工具只查结构与引用，不能证明文档事实已完整或模型确实遵循了交互。
