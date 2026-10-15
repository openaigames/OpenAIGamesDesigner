# 测试与验证

[English](README.md) | [简体中文](README.zh-CN.md)

验证分为代码检查、实际工具联调和游戏验收。每个真实案例分别记录输入版本、执行命令、输出、日志及观察；执行状态与结论保存在对应的验证报告中。

## 模块测试入口

在源码根按受影响模块选择测试；命令示例：

```sh
python -m unittest discover -s tests -p test_runtime_upgrade.py
python -m unittest discover -s tests -p test_runtime_migration.py
python -m unittest discover -s tests -p test_engine_packages.py
python -m unittest discover -s tests -p test_project_contract.py
```

| 范围 | 维护测试或原生入口 |
| --- | --- |
| 资产输入准备 | test_asset_preparation.py；输入路径、约束缺失/冲突、文件变化、请求预览与任务/版本衔接 |
| core 安装、迁移与输入 | test_runtime_upgrade.py、test_runtime_migration.py；原生创建/验证见 [core](../adapters/engines/runtime_components/README.zh-CN.md) |
| 反馈、交互、导航 | test_feedback.py、test_interaction.py、test_navigation.py；各 scenario 使用真实引擎运行器 |
| 生成、旧静态接入与 | test_scene_generation.py、test_static_assets.py、test_static_scene.py、test_scene_replacement.py、test_scene_handoff.py |
| 角色动作 | test_motion_workflow.py、test_motion_profile.py、test_motion_playback.py、test_motion_layers.py、test_motion_root.py、test_motion_constraints.py、test_motion_handoff.py |
| 文档、分发与工具包回退 | test_project_contract.py、test_engine_packages.py、test_bundle_upgrade.py；检查源文件/标题链接、包内链接、异地执行和原件保护 |

维护测试、场景测试脚本、原生测试夹具和 Skill 脚本测试均保留在源码仓库。安装包包含运行工具及 templates/ 和 Skill assets 中的可编辑示例。从源码执行测试；资产 CLI 案例可用 --runtime PATH_TO_GAME_PREPRODUCTION_RUNTIME 指向独立安装目录，无需把测试复制进安装包。生成的日志、报告和本机专用试验脚本留在公开源码之外。测试夹具 README 提供可复现的环境配置。

```sh
python tests/scenarios/asset_iteration_audit.py --runtime "SKILLS_ROOT/game-preproduction/runtime" --output NEW_ITERATION_DIRECTORY
python tests/scenarios/asset_quality_audit.py --runtime "SKILLS_ROOT/game-preproduction/runtime" --output NEW_QUALITY_DIRECTORY
```

## 原生与人工验证

原生验证需要实际引擎与独立工程。按所用模块分别检查导入、运行、保存重开和目标平台出包；程序驱动测试与真实设备、画面、声音及人工体验评估分别记录。

UE 能力选型与动作集成的自然语言评估位于源码 `tests/ability-system-choice-scenarios.md`：检查何时主动介绍 GAS、何时沿用自有实现，以及动画包/控制模块/完整框架的区分。该场景集不随运行包分发，列出场景不代表行为评估已通过。

| 顺序 | 验证对象 | 操作与通过依据 | 需要保存的证据 |
| --- | --- | --- | --- |
| 1 | 工具和分发 | 全部 unittest、源码与包链接、十六个 Skill 格式、异地包 CLI | 源码版本、命令结果、包文件检查与异地执行记录 |
| 2 | Skill 自然语言行为 | 新对话只给想法；再接手旧项目新增/修改功能；检查自动澄清、按需文件、未要求时不启动看板、不重新立项 | 原始输入、澄清过程、交付文件与实际观察 |
| 3 | 一个本地生成工具 | 配置实际 wrapper，提交 → 执行 → 查询 → 打开真实产物；失败一次再重试 | 工具及模型版本、任务记录、产物与质量检查；各提供器分别验证 |
| 4 | Blender | 带贴图的真实模型导入 → 转换 → 再打开，核对比例、材质、动画及依赖 | 输入与输出模型、处理日志、重新打开后的检查 |
| 5 | Godot 完整原型 | 从规格实现小功能 → 测试 → 试玩 → 导出 → 独立运行 | 规格版本、测试、试玩观察、导出包与独立运行结果 |
| 6 | Unity/UE | 接手真实工程 → doctor → 填写原生动作配置或命令覆盖 → 打包运行，保留真实报告 | 引擎和工程版本、原始 XML/JSON、日志与构建运行结果；见 [执行配置](../adapters/engines/execution.zh-CN.md) |
| 6a | Three.js / Phaser | 两条路线分别初始化 → 安装 → 构建导出 → HTTP 打开导出包 → 实际操作验证 | 锁文件、安装/构建日志、浏览器异常与操作结果；空画布不算可玩原型 |
| 6b | 引擎 MCP | 核实工程身份 → 只读查询 → 修改测试对象 → 保存重开 → 运行；断连后先检查现场再重试 | 提供方版本、真实工具清单、原始输出、重开结果；基础联通与项目功能分开验收 |
| 7 | 代表性垂直切片 | 确认体验和品质范围 → 资产/系统集成 → 平台性能及实际试玩 → 交付可编辑工程 | 体验目标、集成版本、性能数据、试玩反馈与验收结论 |

工作台页面回归覆盖资产库、生成任务与服务设置三个入口，旧页面启动参数兼容、旧静态页面移除和底层记录接口保留。浏览器另行检查旧链接跳转、素材方案与缺口、绑定角色动作切换及生成／服务页；不会执行真实收费生成。

工具自动检查入口：

数值协作需要另外完成一次真实往返：从已有配置导出 → 用户编辑 CSV/Excel → 比较/校验 → 应用 → 引擎重载 → 确认实际生效。自动检查覆盖文件冲突、范围/类型、未绑定字段保护、备份、失败和可选 XLSX 读取；不代表 UE DataTable/GAS 或其他原生资源已联调。自然语言测试场景保存在源码的 `tests/production-method-scenarios.md`“数值表协作与回传”一节，分发包不含完整场景集。

```sh
python tools/run_tests.py
python tools/package_skills.py --output dist/新的验证包目录
python tools/validate_records.py --project "实际游戏项目路径" --markdown
```

完整自动测试、评估场景集、统一测试入口和打包脚本在源码维护仓库内；分发包带运行工具、本说明、明确选入的组件测试/场景脚本及可再分发的 tests/fixtures 原生配方。包内测试是子集，不提供完整维护测试承诺。原生夹具的 README 标明实际用途和运行方式。命令行示例使用 [入门](../tools/README.zh-CN.md)。

每个真实案例使用 `templates/validation-report.md` 或项目现有报告记录：验证范围、证据文件/版本、实际执行、观察、未通过项与下一步。管理文件只链接该报告，并依据该测试范围更新任务；代码检查、产物生成、引擎导入、质量通过和用户认可分别记录。引擎与框架的具体能力按使用它们的项目需求验收，不作为所有游戏的前置条件。

统一测试入口仅在源码维护仓库运行：`python tools/run_tests.py` 包含根 tests 和各 Skill 的 scripts/tests，分进程执行并汇总失败。`--list` 查看组，`--group core`、`--group game-art-direction` 或 `--group game-animation-pipeline` 只跑指定组；分组结果不等于全部测试通过。

维护测试需要 Python 3.10+ 和 Node.js（CI 使用 Node 22）；Node 不在 PATH 时向 `run_tests.py` 传入 `--node <可执行文件>`。Blender 实机检查另需配置 `OAGD_BLENDER`。开发环境可用 `python -m pip install -r tests/requirements.txt` 安装 YAML/Excel 检查依赖。GitHub Actions 在 Windows、Python 3.10/3.12 上执行同一入口，运行状态与日志可在仓库的 Actions 页面查看。引擎实机、外部服务和自然语言行为评估按上表单独执行并记录结果。

资产 API 自动测试使用受控响应和子进程，覆盖认证格式、任务 ID 恢复、文件/ZIP 边界、来源与许可登记，不调用收费服务。真实验证按提供器分别进行：doctor → 小任务生成 → 查询 → 下载 → 打开模型 → 中断后恢复同一 ID。免费来源另验搜索/下载；目录搜索计划不能计为网站 API 已接通。

新增职业行为评估输入位于源码 tests/ 下：`character-animation-scenarios.md` 的 C1–C6、`combat-design-scenarios.md` 的时序/受击/Boss 情境、`production-method-scenarios.md` 的六个战斗表现情境。这些维护用场景集不进入安装包。场景数量不计入自动测试通过数，实际评估结果单独记录。

Blender 实机回归：设置 `OAGD_BLENDER` 为实际可执行文件，再运行统一入口；未设置的 skipped 不代表实机通过。动作取舍的后端、迁移和浏览器控件测试包含于同一入口。

数值策划的独立任务、边界与交接场景位于源码 `tests/numerical-design-scenarios.md`。场景是评估输入，不代表已经执行；运行结果与限制另存证据。阶段任务回归应覆盖数值职业保存/读回及未知职业拒绝，分发检查包含新 Skill 和旧引用兼容。

## ElevenLabs 音频回归

`test_elevenlabs_audio.py` 覆盖接口参数、单次授权、来源快照变更、密钥重定向保护、同步响应中断、真实 MP3 解码与 PCM 窗口裁剪；云端响应由本地测试音频替代，不消耗生成额度。真实编解码用 FFmpeg，测试依赖包含 `imageio-ffmpeg`。`test_audio_brief.mjs` 与看板 HTTP 测试覆盖表单参数、窗口预览与过期来源提示。自动检查不代表 ElevenLabs 账户权限、生成听感或引擎效果已验收。

## 主机代理回归

`test_host_proxy.py` 覆盖环境变量优先级、NO_PROXY、系统手动代理、Windows PAC 的代理/直连结果及解析失败、每次跳转重新选路，以及代理传输的二进制请求、响应头、流式读取、中断清理和密钥保护。自动测试模拟 Windows 配置与网络进程，不使用真实密钥；实机另用官方只读接口验证主机代理与账户认证，不以连通结果代替实际生成验收。

## 资产用途分类回归

`test_rig_compatibility.mjs` 检查 FBX 预览模型的有效蒙皮、骨架层级、重名冲突和实际网格变形。浏览器另用真实 FBX 验证配套模型选择、无匹配模型提示及不同时间点的姿态；纯枪身与附件挂点动作不能代替完整换弹预览。

`test_asset_taxonomy.py` 验证用途与格式分离、目录建议、角色动作关联、音频细分、旧专题数据兼容、未知引擎资源、手动覆盖与恢复、文件替换/唯一移动/重复副本、共享用途标签保护、批量原子保存、修订冲突、损坏记录及看板会话边界。`test_asset_categories.mjs` 验证分类／格式／音频筛选、含动画标签与总数去重，并保留旧专题筛选函数兼容性。浏览器另验证实际分类编辑、刷新保留、分页及原有角色动画预览入口。

## 火山方舟图像与视频回归

`test_ark_generation.py` 使用合成密钥和受控 HTTP 响应，覆盖共用密钥的加密保存／移除、默认参数与模型限制、参考图快照、一次授权、图像响应丢失、视频轮询与原 ID 恢复、下载格式检查及不重复提交。`test_project_workbench.py` 覆盖两个服务的新建任务、参数读回、逐次授权及共用密钥接口。测试不消耗云端额度，不等于真实账户生成或视觉验收。

资产迭代回归：`python -m unittest discover -s tests -p test_asset_versions.py` 检查旧版选用、分支、不可变快照、来源引用、并发保护、配套文件、多方案登记、内置任务无云端执行和认证接口；`node tests/test_asset_versions.mjs` 检查分组筛选与制作依据表单。均使用独立测试文件，不调用付费模型。

资产质量行为由 `test_asset_quality.py` 覆盖。运行 `python tests/scenarios/asset_quality_audit.py --output NEW_DIRECTORY` 可复现禁止网络的隔离 CLI 案例。案例声明为合成判断，不是正式美术验收，详见[质量评审](../adapters/assets/quality-review.zh-CN.md)。

`test_asset_iteration.py` 检查针对性调整、要求保留、实际发送内容变化、参考快照、来源链、退步识别和有限重试。运行 `python tests/scenarios/asset_iteration_audit.py --output NEW_DIRECTORY` 可复现禁止 socket 连接的 CLI 案例，生成任务只排队。合成判断验证流程，不代表云端生成质量，详见[结果驱动迭代](../adapters/assets/result-iteration.zh-CN.md)。
