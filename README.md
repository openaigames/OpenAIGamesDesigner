![OpenAIGamesDesigner：从构思、设计与制作到试玩](.github/assets/openaigamesdesigner-banner.png)

<div align="center">

# OpenAIGamesDesigner

面向独立开发者与小团队，围绕同一个可持续编辑的游戏工程，
从新想法走向原型、垂直切片与持续迭代。

[快速开始](#快速开始) · [开发流程](#开发流程) · [免费游戏素材库](#免费游戏素材库) · [引擎与工具](#引擎与工具) · [项目文件](#项目文件)

</div>

## 从你正在做的事开始

<table>
<tr>
<td width="50%" valign="top">
<h3>💡 把想法变成开发方向</h3>
<p>从一句描述开始，澄清核心体验、玩法、美术与制作条件，把已知、待定和下一步保存在项目里。</p>
</td>
<td width="50%" valign="top">
<h3>🎮 制作原型与垂直切片</h3>
<p>把设计拆成任务，在选定的引擎里实现；通过实际运行与试玩，检验机制和代表性体验。</p>
</td>
</tr>
<tr>
<td width="50%" valign="top">
<h3>🔧 接着已有项目继续做</h3>
<p>新增系统、调整规则、修改关卡。沿用现有工程，让受影响的策划、美术与技术记录一起更新。</p>
</td>
<td width="50%" valign="top">
<h3>🎨 协作制作资产与数值</h3>
<p>明确资产需求，按需制作可编辑的美术图板、检索素材并接入制作工具；整理数值表，比较修改、回写工程并检查实际效果。</p>
</td>
</tr>
</table>

## 开发流程

![开发流程：确定方向、机制原型、打磨垂直切片、持续制作与交付；相邻阶段均可退回前一步修改](.github/assets/workflow-overview.svg)

可以从新想法开始，也可以直接进入已有项目的一次修改。项目管理串联**概览、策划、美术、技术与验证**，按当前任务调用专业方法。

重要创作取舍由你决定，AI 在已确定的范围内推进。设计、工程改动和实际验证分别记录，后续对话可以沿着项目文件继续工作。

<details>
<summary>查看六条工作流与专业入口</summary>

| 这次想完成什么 | 工作流 |
| --- | --- |
| 立项 / 接手已有项目 | [项目接入](workflows/project-intake.md) |
| 验证核心机制 | [原型构建](workflows/prototype-build.md) |
| 集成代表性体验与品质 | [垂直切片](workflows/vertical-slice.md) |
| 新增、修改或移除功能 | [功能变更](workflows/feature-change.md) |
| 制作、处理与导入资产 | [资产制作](workflows/asset-production.md) |
| 打包交付与反馈接续 | [交付](workflows/delivery.md) |

相关skills：[项目管理](skills/game-preproduction/SKILL.md) · [概览与定位](skills/game-concept/SKILL.md) · [游戏策划](skills/game-design/SKILL.md) · [美术方向](skills/game-art-direction/SKILL.md) · [技术设计](skills/game-technical-design/SKILL.md) · [原型验证](skills/game-prototype-validation/SKILL.md)

</details>

## 快速开始

本指南提供 **Codex** 的安装与使用方法。准备 Python 3.10+ 运行工具；实际制作时，再接入项目需要的引擎和资产工具。

先查 [按功能配置环境](adapters/environment-setup.md)：列出需要安装什么、在电脑 / 引擎 / AI 助手的哪里配置，以及怎样确认可用。只讨论和维护设计文档时无需先安装引擎。

### 1 · 获取并安装

使用有仓库访问权限的账号获取本仓库，在 Codex 中打开，然后输入：

```text
把这个仓库的六个 Skill 和必要运行资源安装到本机。
如果已有同名版本，先比较差异并保留我的修改。
```

<details>
<summary>手动获取、打包与安装</summary>

```sh
git clone https://github.com/openaigames/OpenAIGamesDesigner.git
cd OpenAIGamesDesigner
python tools/package_skills.py --output dist/skills-bundle
```

Codex 个人安装：将生成包中的六个完整 Skill 目录放入 `~/.agents/skills/`（Windows 默认是 `C:/Users/<用户名>/.agents/skills/`）。仅供某个游戏项目使用时，可放入该项目的 `.agents/skills/`；通常选择一种范围，避免同名副本混淆。保留 `game-preproduction/runtime/` 等全部子文件，已有同名目录时先比较并备份本地修改。

打包目标需为新目录；更新后重新打包并同步安装副本。包内 `game-preproduction/runtime/bundle-manifest.json` 记录内容版本，使用该 runtime 下的 `tools/check_installation.py --skills-root <六个Skill的父目录>` 检查缺失或修改的文件；差异需比较并保留本地定制。分发包不包含引擎、生成模型或游戏资产。

</details>

### 2 · 打开你的游戏项目

安装后在 Codex 新开一个任务，以游戏项目目录为工作目录，或提供已有工程的实际路径。已有项目沿用自己的结构。Skill 安装位置、MCP 配置与游戏项目文件是不同位置，见 [Codex 路径速查](adapters/environment-setup.md#codex-路径速查)。

### 3 · 用自然语言描述目标

**开始一个新游戏**

```text
我想做一个网页 2D 探索游戏，使用 Phaser。
玩家可以收集零件、修复设施，逐步进入新的区域。
先帮我确定核心体验和第一版原型的范围。
```

**继续一个已有项目**

```text
给这个游戏增加装备升级系统，使用探索获得的资源。
先讨论规则和对现有系统的影响，再推进实现。
```

直接描述目标即可。助手根据资料澄清关键未知，选择适用的 Skill，在项目文件中保存决定并继续工作。

[完整使用说明 →](tools/README.md)

## 免费游戏素材库

**按类型查找素材，按下载条件选择来源。** 素材库覆盖 2D、3D、动作、VFX、音频、字体与引擎模块，提供作者来源、免费范围、许可依据、账号要求及文件下载入口，帮助助手选材、获取并登记到游戏项目。Moodboard 参考图另按图板规则筛选。

| 模型可直接下载 · 无需登录 | 需要登录或额外操作 |
| --- | --- |
| [Kenney](https://kenney.nl/assets) — 2D、3D、UI、材质、VFX、音频<br>[Poly Haven](https://polyhaven.com/) — 3D、材质、HDRI | [Quaternius](https://quaternius.com/) — 按条目判断登录；有额外流程<br>[itch.io free game assets](https://itch.io/game-assets/free) — 按条目判断登录；有额外流程 |
| [ambientCG](https://ambientcg.com/) — 3D、材质、HDRI<br>[OpenGameArt](https://opengameart.org/) — 2D、3D、UI、材质、VFX、动画、音频、字体 | [Mixamo](https://www.mixamo.com/) — 需登录<br>[Fab](https://www.fab.com/) — 按条目判断登录；有额外流程 |
| [Godot Asset Library](https://godotengine.org/asset-library/asset) — 模块、VFX、UI<br>[KayKit](https://kaylousberg.com/game-assets) — 3D、动画 | [Unity Asset Store](https://assetstore.unity.com/) — 需登录<br>[Freesound](https://freesound.org/) — 需登录 |
| [Game-icons.net](https://game-icons.net/) — 2D、UI<br>[Google Fonts](https://fonts.google.com/) — 字体 | [CraftPix Freebies](https://craftpix.net/freebies/) — 需登录<br>[Blendkit（原 BlenderKit）](https://www.blendkit.com/) — 按条目判断登录；有额外流程 |
| [Lucide](https://lucide.dev/icons/) — UI<br>[Effekseer Sample Effects](https://effekseer.github.io/en/contribute.html) — VFX | — |
| [TextureCan](https://www.texturecan.com/) — 材质、3D<br>[Incompetech](https://incompetech.com/music/royalty-free/music.html) — 音频 | — |

下载方式按具体素材和文件格式区分。例如 Fab 部分免费文件可匿名下载，但需要接受 EULA 并选择格式；加入个人库则需要登录。免登录栏提供可直接获取的文件示例，使用其他素材或版本时仍需核对其下载条件、许可和引擎兼容性。

[查看完整合集、文件下载地址与登录步骤 →](adapters/assets/asset-sources.md) · [机器可读素材目录](adapters/assets/sources.json)

```sh
# 查找可免登录下载的特效来源
python tools/asset_library.py sources --kind vfx --access direct --query "magic impact"
# 查看确实需要账号的动画来源
python tools/asset_library.py sources --kind animation --login required
```

目录查询只准备检索路线；选定素材后，助手继续核实当前文件和许可，再使用统一下载与登记工具保存到游戏项目。合集不限制从其他来源找素材，也不限制自制、修改或已授权生成。

## 引擎与工具

按项目目标选择制作路线，已有工程优先沿用。

| 制作路线 | 接入文件 |
| --- | --- |
| **Three.js · 网页 3D** | [adapters/engines/threejs/README.md](adapters/engines/threejs/README.md) |
| **Phaser · 网页 2D** | [adapters/engines/phaser/README.md](adapters/engines/phaser/README.md) |
| **Godot** | [adapters/engines/godot/README.md](adapters/engines/godot/README.md) |
| **Unity** | [adapters/engines/unity/README.md](adapters/engines/unity/README.md) |
| **Unreal Engine** | [adapters/engines/unreal/README.md](adapters/engines/unreal/README.md) |

资产制作支持 [Tripo / Hunyuan3D API](adapters/assets/generation-api.md)（[本机密钥设置页](adapters/assets/local-settings.md)）、[免费素材检索与登记](adapters/assets/asset-sources.md)，以及图像、音频与 Blender 的本地命令；数值协作支持已绑定 JSON 配置与 CSV / Excel 数值页之间的交换。

Unity 与 Unreal 分别提供工程创建、场景与组件编辑、资源导入、角色动画配置及自动操作入口，通过会话记录关联检查点和中断恢复。编辑器操作也可使用宿主已有的 MCP，具体支持范围与依赖见各引擎说明。

[引擎接入说明](adapters/README.md) · [资产工具接入](adapters/assets/README.md) · [数值表往返](tools/README.md#数值表往返) · [验证方法](tests/README.md)

## 项目文件

### 工具包目录

```text
OpenAIGamesDesigner/
├── skills/                         # AI 专业工作方法与按需参考
│   ├── game-preproduction/         # 项目管理、阶段推进与变更协调
│   ├── game-concept/               # 游戏定位、核心体验与设计支柱
│   ├── game-design/                # 玩法、系统、关卡与数值策划
│   ├── game-art-direction/         # 美术方向、图板、素材选用与视觉验收
│   ├── game-technical-design/      # 技术设计、工程实施与引擎参考
│   └── game-prototype-validation/  # 原型、切片与变更验证
├── workflows/                      # 立项、原型、切片、变更、资产与交付流程
├── templates/                      # 项目管理、里程碑、任务和规格等交付模板
├── tools/                          # 项目执行、资产任务、数值交换、检查与打包
├── adapters/                       # 具体引擎及外部工具的接入实现
│   ├── engines/                    # 引擎运行、制作、会话恢复与 MCP 接入约定
│   │   ├── godot/                  # Godot 命令与接入说明
│   │   ├── unity/                  # Unity 运行、制作驱动与 C# 辅助工具
│   │   ├── unreal/                 # UE 运行、制作驱动与 Python 辅助工具
│   │   ├── threejs/                # 网页 3D
│   │   └── phaser/                 # 网页 2D
│   ├── assets/                     # 生成 API、素材检索下载与本地处理
│   └── processing/                 # Blender 等资产处理接入
├── schemas/                        # 项目、运行、引擎会话、资产任务与产物记录约定
├── tests/                          # 自动检查、行为场景与联调样例
└── dist/                           # 本地打包生成的 Skill 分发包
```

### 新游戏项目目录

**讨论、设计与工程留在你的游戏项目里。** 六份方向文档作为入口，详细规格、任务、资产和运行证据按需建立，通过链接关联。

```text
MyGame/
├── Project Management.md       # 阶段、索引、变更汇总与下一步
├── Game Concept.md             # 定位、核心体验与设计支柱
├── Game Design Document.md     # 玩法、系统与数值设计入口
├── Art Direction.md            # 美术方向、表现与资产记录
├── Technical Design.md         # 技术方案、接口与工程入口
├── Risk & Assumption List.md   # 风险、验证计划与实际结果
├── design/                     # 详细功能、资产规格与数值设计
├── production/                 # 任务、里程碑与重要决定
├── assets-source/              # 源素材或外部资产引用
├── game/                       # 可持续编辑的游戏工程
├── tests/                      # 测试与试玩报告
├── .openaigame/                # 工具配置与任务记录
├── runs/                       # 执行日志、输入快照与证据
└── builds/                     # 构建产物
```

初次立项保存已知信息，未确定的记录为待讨论。后续只修改当前任务涉及的专业内容，关联变更汇总到项目管理；定位发生变化时再更新概览。

具体资产、来源、许可与交付进度由美术记录或现有资产清单统一维护，概览只保留影响定位的制作策略摘要。

已有项目保留自己的目录和等价文档。游戏资料保存在项目中，Skill 安装目录保存通用方法与工具。

## 扩展与参与

[专业 Skills](skills/) · [工作流与架构](workflows/README.md) · [交付模板](templates/) · [适配器](adapters/README.md) · [测试与验证](tests/README.md)

专业方法放在对应 Skill，具体工具接入放在适配器，通用流程负责串联。欢迎通过实际项目中的需求与验证结果，逐步完善这套工具。
