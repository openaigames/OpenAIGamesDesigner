# 动作原生导入与采样

[English](README.md) | [简体中文](README.zh-CN.md)

本目录把离线加工结果导入真实 Godot / UE 5.8，读取原生骨骼变换，供单位、轴向、根/骨盆轨迹与映射检查使用。它与 [游戏内动画播放](../motion_playback/README.zh-CN.md) 是不同入口。

| 实现 | 用途 |
| --- | --- |
| godot/import_capture.gd | 原生导入与骨骼捕获 |
| unreal/import_motion.py | UE 导入、保存与准备采样资源 |
| unreal/OAGDMotion/ | UE 实际求值与捕获插件 |

通过 tools/motion_native.py 准备任务，先阅读 [动作加工契约](../../processing/MOTION.zh-CN.md)。必须提供实际已加工 revision 和匹配配置，使用新的工程/报告位置；原生采样不能用手写结果代替。

采样和数值往返不等于蒙皮观感、手感或任意骨架兼容。准备原生资源后若要接入游戏时间、状态选择、根运动或脚/手约束，使用 playback 的对应流程。
