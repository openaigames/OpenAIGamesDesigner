![OpenAIGamesDesigner：从游戏构思、设计与制作到试玩](.github/assets/openaigamesdesigner-banner.png)

# OpenAIGamesDesigner

面向独立开发者和小团队的 AI 游戏开发工具包。由用户掌握创作方向，AI 根据专业方法协同完成项目管理、游戏策划、美术、技术与验证，围绕同一个可持续编辑的游戏工程推进工作。

通过自然语言描述想法或修改目标，将讨论、设计、制作任务、工程改动和验证证据保存在项目文件中。适用于新游戏立项、已有项目持续开发，以及原型和垂直切片制作。

[开始使用](tools/README.md) · [项目架构](workflows/README.md) · [引擎接入](adapters/README.md) · [验证方法](tests/README.md)

## 项目定位

OpenAIGamesDesigner 采用本地文件工作流，由六个专业 Skill、通用开发流程、文档模板和本地执行工具组成。当前以 Codex 作为使用宿主，无需部署数据库或常驻后台。

目标是帮助独立开发者和小团队持续制作游戏；对于制作要求较高的 UE 项目，可以把代表性垂直切片作为交付目标。具体规模与质量取决于项目范围、可用资产、工程工具和实际验证。

你可以用它：

- 从一个想法开始，逐步澄清体验、玩法、美术和技术方向。
- 接手已有游戏，新增或修改系统、关卡、规则和资产。
- 将设计转成可执行任务，在原生引擎工程中实现并验证。
- 按需生成数值表和计算模型，支持用户或 AI 调参，并通过差异检查与工程导入继续验证。
- 记录阶段、决定、未决事项和执行结果，在后续对话中继续工作。

Skill 提供专业工作方法，编码助手实施具体改动，本地工具负责命令执行与证据记录。实际制作需要配置对应的引擎和资产工具。

## 六个专业方向

| Skill | 负责内容 | 项目文档入口 |
| --- | --- | --- |
| `game-preproduction` | 项目阶段、目标、依赖、变更协调和进度汇总 | `Project Management.md` |
| `game-concept` | 游戏定位、核心体验、目标玩家与设计支柱 | `Game Concept.md` |
| `game-design` | 玩法、系统、关卡、数值及详细功能规格 | `Game Design Document.md` |
| `game-art-direction` | 美术方向、资产规格、表现需求与视觉检查 | `Art Direction.md` |
| `game-technical-design` | 技术选型、接口、工程实现和资产接入 | `Technical Design.md` |
| `game-prototype-validation` | 风险假设、实验、回归和里程碑验收 | `Risk & Assumption List.md` |

`game-preproduction` 保留现有名称以兼容调用，职责覆盖项目全周期。六个 Skill 按任务需要协作，不要求同时启动六个 Agent。

策划参考目前覆盖战斗、射击、探索与冒险、关卡、移动与交互、UI/UX、成长与经济。这些方法可以组合使用，用户无需先把游戏归入固定类型。具体游戏的规则与参数保存在游戏项目中，通用方法保存在 Skill 的 `references/` 中。

## 怎样推进一个项目

六条通用流程对应不同工作目标：

| 工作目标 | 流程 |
| --- | --- |
| 新想法立项或接手已有工程 | [project-intake](workflows/project-intake.md) |
| 设计、实现和原型验证 | [prototype-build](workflows/prototype-build.md) |
| 集成代表性体验与品质 | [vertical-slice](workflows/vertical-slice.md) |
| 新增、修改、移除功能或修复问题 | [feature-change](workflows/feature-change.md) |
| 资产需求、制作、处理与接入 | [asset-production](workflows/asset-production.md) |
| 打包、交付及反馈接续 | [delivery](workflows/delivery.md) |

首次立项，在项目位置明确且允许保存后建立六个非空文档入口：已知内容写入，未确定的内容记录为待讨论，并说明后续补充条件。用户只要求讨论时，先完成讨论。

后续从相关专业原位修改，通过同一条变更记录关联受影响的设计、资产、技术任务和验证证据。能够依据已有决定完成的关联修改直接推进；新的创作取舍再聚焦澄清。设计完成、工程实现和验证通过分别记录。

例如新增经济系统，策划定义资源规则，美术补充适用的界面和表现要求，技术处理数据与存档接口，验证检查循环与边界。项目管理汇总进展；只有定位、核心体验或设计支柱改变时，才更新概览。局部功能处于实验阶段，不会让整个项目重新立项。

详细规则见 [项目文件约定](skills/game-preproduction/references/project-files.md) 和 [跨方向变更联动](skills/game-preproduction/references/dependency-and-change-impact.md)。

## 快速开始

准备 Codex 和 Python 3.10+。涉及实际制作时，还需要项目使用的引擎及相应工具；只整理设计文档无需先安装引擎。

### 1. 获取并打包

使用有仓库访问权限的账号获取源码，然后在仓库根目录执行：

```sh
git clone https://github.com/PeterTXPan/OpenAIGamesDesigner.git
cd OpenAIGamesDesigner
python tools/package_skills.py --output dist/skills-bundle
```

打包目标目录必须尚不存在。再次打包时使用新的目录名；输出应位于 `dist/` 下或仓库外。

### 2. 安装六个 Skill

将生成包中的六个完整 Skill 目录放入当前用户的 `~/.agents/skills/`。保留所有子文件，尤其是 `game-preproduction/runtime/`，其中包含共享工作流、模板和执行工具。已有同名技能时，先比较差异并备份，保留本地修改。

也可以在 Codex 中打开本仓库，让助手完成安装：

```text
请将这个仓库的六个 Skill 和必要运行资源打包安装到本机。
如果已有同名版本，先比较差异并保留我的修改。
```

更新源码后，需要重新打包并同步安装副本。默认包不包含引擎、生成模型或游戏资产。安装后新开一个任务，确认六个 Skill 可用。

### 3. 在游戏项目中描述目标

在目标游戏目录打开任务，或提供已有工程的实际路径，然后用自然语言提出需求。通常无需点名 Skill、要求反问或指定内部文档流程；助手应根据已知信息判断下一步。需要显式调用时，可使用 `$game-preproduction` 或对应专业 Skill 名称。

**新游戏：**

```text
我想做一款末日机甲题材的 2D 横版射击肉鸽游戏，
希望战斗节奏快，机甲改装能带来不同打法。
```

**已有项目增加系统：**

```text
给这个游戏增加一个经济系统，让探索获得的资源可以用于装备升级。
这轮先讨论设计方案。
```

**修改资产：**

```text
把现有 Boss 的蓄力特效改得更容易辨认，沿用当前美术风格。
```

**进入实际制作：**

```text
在这个 Unreal 工程里实现已经确定的格挡反击规则。
```

助手应读取现有资料、澄清会影响本轮推进的未知、保存相关记录，并在用户要求实施时继续完成工程工作。信息足够时直接推进，已回答的选择不重复询问。技术方案以实际工程和本轮决定为依据，候选方案与已采用方案分别记录。

更多命令和工程配置见 [开始使用](tools/README.md)。

**协作调参：**

```text
把这个项目的武器参数整理成可编辑表，保留单位和计算依据。
我修改表格后，读取差异并应用到工程，再检查实际生效值。
```

简单参数可直接保留在规格中，批量配置和曲线按需生成附件。已有工程沿用自己的数值主源与导入器；文件更新、引擎生效和体验验证分别记录。具体用法见 [数值表往返](tools/README.md#数值表往返)。

## 游戏项目保存什么

新项目采用以下组织方式。六个总入口持续保留，详细内容按需拆分并通过链接关联；其余目录随着工作产生。

```text
MyGame/
├─ Project Management.md          阶段、索引、变更汇总与下一步
├─ Game Concept.md                定位、核心体验与设计支柱
├─ Game Design Document.md        玩法与系统设计入口
├─ Art Direction.md               美术与表现入口
├─ Technical Design.md            技术与工程入口
├─ Risk & Assumption List.md      风险、验证计划与结果入口
├─ design/                       详细功能、资产规格与变更记录
├─ production/                   任务、里程碑与重要决定
├─ assets-source/                源素材或外部资产引用
├─ game/                         原生引擎工程
├─ tests/                        测试、试玩和验证报告
├─ .openaigame/                  工具配置及资产任务记录
├─ runs/                         执行日志、输入快照与证据
└─ builds/                       构建产物
```

已有项目保留自己的目录、命名和等价文档，不为使用工具包强制迁移。游戏资料与工程保存在游戏项目中，Skill 安装目录只保存通用方法和工具。

## 仓库结构

```text
OpenAIGamesDesigner/
├─ skills/       六个专业入口及按需参考
├─ workflows/    六条通用开发流程及架构说明
├─ templates/    八份通用交付模板
├─ tools/        项目、资产、数值交换、记录检查与打包工具，以及使用说明
├─ adapters/     引擎、资产命令及 Blender 接入与配置说明
├─ schemas/      项目、执行、资产任务和产物记录约定
├─ tests/        自动检查、行为场景、联调样例与验证方法
└─ dist/         生成的技能分发包
```

工作流保持通用，具体引擎、框架和玩法方法放在专业参考与适配器中。八份模板分别用于项目管理、原型里程碑、切片里程碑、任务、功能规格、资产规格、验证报告和重要决定。

## 验证与继续开发

在仓库根目录运行自动检查：

```sh
python -B -m unittest discover -s tests -p "test_*.py" -v
```

这些检查覆盖工具行为、文件保护、记录协议、分发结构和本地引用。真实引擎与自然语言工作流需要分别验证：

- [分项验证计划](tests/README.md)：工具与引擎能力的验收范围。
- [新项目行为评估](tests/project-intake-behavior.md)：自然语言输入、六入口建立与制作交接。
- [变更联动评估](tests/change-impact-behavior.md)：已有项目修改、跨方向同步与接续。

扩展专业方法时放入对应 Skill 的参考目录；新增执行能力时明确适配器的输入、输出、失败记录和真实验证范围。具体接入方式见 [扩展适配器](adapters/README.md) 与 [资产提供器](adapters/assets/README.md)。
