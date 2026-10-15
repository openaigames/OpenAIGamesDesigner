# 组合工程示例

[English](README.md) | [简体中文](README.zh-CN.md)

组合示例将角色移动、交互、反馈、存档、导航和场景资源接入同一游戏工程。使用方式与模块职责见[接入说明](SUPPORT.zh-CN.md)。

这是可编辑的工程案例。移动、交互、持物和反馈由同一角色消费；NPC 使用原生导航；场景含生成灰盒和派生门框。游戏规则在 main.gd / CombinedGame.cpp，配置和资产属于本项目。

WASD 移动，靠近金色物件后按住 E 拿取，Q 取消/放下，Esc 暂停，K 保存，L 读取，Tab 换场景，R 重开。保存只记录稳定房间 ID、玩家位置和是否持物；读档恢复稳定状态，取消进行中的交互、导航请求和反馈，NPC 重新开始巡逻。暂停保留持物姿态；暂停前未完成的交互取消，恢复后必须重新按键。

Godot：导入项目，依次运行 prepare.gd、build_assets.gd、prepare_combined.gd，然后打开 main.tscn。

已经准备好的交付工程可直接导入运行 main.tscn；只有重新生成资产时才需要上述准备步骤。再次导出 Windows 包需安装匹配 Godot 4.7.2 的官方导出模板。

UE 5.8：编译 MotionPlayEditor，依次运行 prepare.py、prepare_combined.py，打开 /Game/Playback/Example。已交付工程含准备好的原生资源，无需重新生成。

自动验证：Godot `-- --report=绝对路径 --save-dir=新目录 --mode=exercise`；UE `-CombinedReport=绝对路径 -CombinedSaveDir=新目录 -CombinedMode=exercise`。随后以相同存档目录、不同报告名运行 resume 模式，检查跨进程继续。报告与程序退出码都需要检查。

项目组件是复制并锁定的版本。先用 runtime_migration.py plan 检查，再 apply；回退使用 receipt。不会迁移游戏规则、资产、绑定或存档。文件同时被工具包与项目修改时报告冲突，保留现场。

本组合案例采用控制器移动 + 原生动画 + 脚/手约束。根运动、叠加和转向保留独立验证案例，不宣称它们的任意组合均已通过。请分别检查目标平台运行、实体设备输入、画面和声音。

请一并阅读 SUPPORT.md、KNOWN_ISSUES.md 和随包许可证；使用 TRIAL_REPORT.md 记录试用问题。
