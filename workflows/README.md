# OpenAIGamesDesigner 架构

项目文档遵循“首次六入口、后续专业原位修订、依赖联动、管理汇总”。专业入口链接详细规格，各规则与配置保持唯一负责位置；一次跨方向修改通过同一变更记录关联美术、技术、验证及真实任务，分别记录设计、实现和验证成熟度。概览只在定位、核心体验、目标玩家或支柱变化时更新，管理每轮摘要结果和下一步。联动由助手读取依据后执行，当前没有后台文档监听或自动依赖传播服务。

这是可由 AI 助手使用的本地游戏开发工具包。真实项目保留可编辑设计文件、原生引擎工程和实际证据；不需要数据库、常驻服务或看板。六个 Skill 分别承担管理、定位、策划、美术、技术和验证。专业方法按需组合，不用游戏类型限制用户创作。

## 工具包的职责

| 层 | 维护内容 | 不代表什么 |
| --- | --- | --- |
| skills | 专业判断、澄清与交接方法 | 文档不等于已实现的游戏 |
| workflows | 接入、原型、切片、功能变更、资产制作、交付六条通用流程 | 不为每个引擎或玩法复制流程 |
| templates | 八份通用管理、里程碑、任务、规格、验证与决定骨架 | 不要求已有项目迁移或填满 |
| tools | 文档生成、引擎运行、资产任务、记录检查、技能打包 | 不自动批准任务或阶段 |
| adapters | 引擎命令、本地生成包装命令、Blender 处理 | 不内置全部引擎编辑器能力或生成模型 |
| schemas | project、run、asset-job、artifact 四类记录格式 | 不是独立的任务管理数据库 |
| tests | 工具、协议、文件保护与模拟适配器检查 | 不代替真实引擎联调或游戏验收 |

`adapters/engines/` 包含 Godot、Unity、Unreal；`adapters/assets/` 包含 Hunyuan3D、图像和音频；`adapters/processing/` 包含 Blender。公共协议辅助文件也保存在所属目录。

## 实际游戏项目

```text
MyGame/
├── Project Management.md           阶段、目标、入口、阻塞与下一个动作
├── Game Concept.md                 按需形成的专业正文
├── Game Design Document.md
├── Art Direction.md
├── Technical Design.md
├── Risk & Assumption List.md
├── production/                     里程碑、任务、决定、资产请求
├── design/                         详细功能和资产规格
├── tests/                          项目测试和验证报告
├── game/                           一个持续编辑的原生工程
├── assets-source/                  原始资产及来源资料
├── .openaigame/
│   ├── project.json                引擎位置和执行配置
│   ├── asset-providers.json        项目选定的本地工具命令
│   └── asset-jobs/<id>/            输入快照、任务状态、日志、产物
├── runs/<id>/                      引擎执行记录、输入快照与日志
└── builds/<id>/                    导出结果
```

这是新游戏的默认组织约定；用户明确指定的位置与已有结构优先，不自动迁移。先用 scaffold 或按相同约定建立根目录六个非空入口及索引；正文按已知、待定和补充条件逐步完善，其他目录按工作产生。入口存在不代表设计已完成。宿主 outputs 可容纳整个游戏根，但不能用引擎内 Docs 和宿主 work/logs 替代项目管理和运行结构。已有工程根可配置为 `.`；新工程默认在 `game/`。Markdown 管理需求、判断和阶段；JSON 记录命令与文件。管理入口链接任务、里程碑和实际证据。

主要玩法实施前需要当前规则、技术入口、任务与原型目标。新作位置检查用 `validate_records.py --layout --markdown`，实施交接增加 `--production`；已有/自定义结构省略布局检查，保留等价记录。检查不会判断专业内容或用户是否认可。

一次变更连接：需求/决定 → 功能或资产规格 → 具体任务 → 原生工程改动 → 命令记录 → 实际检查/试玩报告 → 更新当前阶段与下一步。命令成功只能证明本次命令达到其技术条件，玩法、视觉和用户认可需要各自证据。

资产任务 `succeeded` 表示本地命令结束且输出文件已登记；`registered` 表示登记了外部制作的文件。两者都保持 `quality_validation: not_checked`。输入快照、哈希与重试关联用于追溯，不能替代 Git/LFS 或工程备份。

## 分发与边界

源码是维护来源，`dist/` 是构建产物，个人 Skill 目录是安装副本，游戏目录是工作结果。打包时公共运行资源放入 `game-preproduction/runtime/`，包含 workflows、templates、tools、adapters、schemas 和可移植使用文档；六个 Skill 的专业参考各自随包分发。默认打包只包含 skills 和规定的 runtime 资源。个人开发记录、旧工具与历史分发包保存在仓库外，不参与当前流程。

Unity/Unreal 当前提供工程识别和可配置命令执行。Blueprint、GAS/Lyra 资产编辑、自动导入和具体项目构建逻辑仍依赖项目自己的工具或助手实施。图像、音频、Hunyuan3D 接入是本地包装协议，未绑定云 API 或下载模型。

使用见 [入门](../tools/README.md)，实际验收顺序见 [分项验证计划](../tests/README.md)。
