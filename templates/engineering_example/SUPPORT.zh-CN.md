# 组合工程接入说明

[English](SUPPORT.md) | [简体中文](SUPPORT.zh-CN.md)

示例面向 Windows、Godot 与 UE 5.8。各模块可以单独接入；表中列出组合方式和需要在具体游戏中继续验证的边界。

| 模块 | 可复用范围 | 示例接入方式 | 需按项目验证的范围 |
| --- | --- | --- | --- |
| 工程 | 输入路由、重绑定、焦点、暂停原因、设置、场景、项目声明字段的版本化本地存档 | 键鼠/软件手柄路由，嵌套暂停，原生房间切换，存读档，重开，跨进程继续 | 重绑定完整菜单、设置、检查点、坏档双代恢复；真实手柄和人工体验未验收 |
| 反馈 | 项目事件到声音/视觉/镜头，挂点、并发、暂停、取消、对象和场景生命周期 | 拾取一次反馈、持物持续反馈、暂停冻结、取消和场景清理 | UI 域和更多并发/异常组合；人工听感未验收 |
| 交互/NPC | 目标查询、条件、按住提交、取消，地面导航、追踪/返回示例 | 同一角色查询并拿取实际物件；NPC 在同一生成场景巡逻，暂停/取消/加载后重新规划 | 遮挡/多目标/不可达/追踪/动态阻挡边界；不包含完整战斗、对话或群体 AI |
| 场景/静态资产 | 规格生成、稳定 ID、三方合并、原生导航、灰盒替换、材质/碰撞/LOD | 两房间曲线路径；原创门框替换；保存后的原生场景/资源及原生导航 | 坡道、窄口、断路、静态资源更多策略及冲突案例；不支持任意材质或开放世界自动生成 |
| 角色/动作 | 已采用人形骨架/动作的加工、播放、限定根运动、脚 IK、主/辅助手约束 | CesiumMan 原生动画、控制器移动、脚部接触与双手握持，暂停冻结、取消释放、读取后重建 | 根运动、转向、叠加使用各自案例；不据本例宣称任意组合、网络根运动、移动平台、手指或服装支持 |

core 与 playback 是可分别安装的源码包。Godot 是项目内 addons 副本；UE 是项目内插件副本。core 的各职责可分别实例化，UE 源码仍编译为一个 OAGDCore 插件；“选择模块”不表示会自动拆开每个 C++ 文件。playback 插件本身不依赖 core；组合消费者主动使用两者。

共享工具不会存放跨游戏共享可写配置。示例自己的输入映射、房间、存档字段、反馈资源、巡逻规则、角色绑定和物件归项目所有。已做的游戏工程不会随工具包更新自动变化。

## 接入与迁移

新建无角色工程：使用 runtime_components.py create，选择 input/state/feedback/interaction/navigation/scene/static 等案例。它们不安装角色播放包。已有工程可使用 runtime_components.py install 安装 core，或 runtime_migration.py 选择 core/playback；安装插件不等于已配置角色或完成玩法接入。

组合例：使用 engineering_example.py，传入已通过检查的角色 revision 与 bindings。两引擎分别使用新的工程目录；UE 必须指定 --ue-root 的 5.8 安装。命令创建源文件后按工程 README 准备原生资源。已交付工程包含准备好的资源。

```text
python tools/runtime_migration.py plan --project GAME --engine godot --packages core playback --plan review.json
python tools/runtime_migration.py apply --project GAME --plan review.json --receipt BACKUP_OUTSIDE_GAME
python tools/runtime_migration.py rollback --project GAME --receipt BACKUP_OUTSIDE_GAME
```

plan 检查旧锁、当前项目和待安装包。仅上游修改的文件可更新，仅项目修改的文件保留；双方改动同一文件则报告冲突并拒绝整个 apply。不会改动游戏脚本、资产、输入/角色绑定或存档。apply 前重新检查计划是否失效；receipt 保留原字节和前后散列。回退前检查迁移后是否又被改动，拒绝覆盖新编辑。可捕获 I/O 失败会恢复原字节；断电/强杀不承诺磁盘事务，保留 receipt 供恢复。

## 试用反馈

记录工具包版本、引擎版本、所用模块、实际目标、复现步骤、预期/实际结果、日志/截图、人工介入、是否阻塞下一步。可使用同目录 TRIAL_REPORT.md。工程接收者与案例作者是否同一人、软件输入与真实设备、技术结果与人工体验必须分别说明。
