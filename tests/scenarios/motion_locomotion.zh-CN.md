# 原生连续移动案例

[English](motion_locomotion.md) | [简体中文](motion_locomotion.zh-CN.md)

使用两种 已校准角色的共同相位窗口 L=[1/6,1/3]、R=[2/3,5/6]；这是该案例契约，不是任意步态检测器。源码里的 `motion_locomotion_audit.py` 只审计此 22 秒原生示例时间线。工具使用标准库，不启动或模拟引擎。

先用 motion_playback 创建工程，在绑定中显式加入 locomotion 配置，经原生 prepare 后激活。Godot 运行参数：`-- --report=<absolute.json> --scenario=locomotion --fps=30`；添加 `--variable-fps` 使物理步长实际交替 30/60 Hz。UE 原生／独立包参数：`-MotionReport=<absolute.json> -MotionScenario=locomotion -UseFixedTimeStep -FPS=30`；添加 `-MotionVariableFps` 使用交替步长。不要把程序输入标记成人类试玩。

`python tests/scenarios/motion_locomotion_audit.py <runtime.json>` 读取真实骨骼、片段时间、朝向、位移和事件，输出同目录 audit.json。检查匀速走／跑、中间速度、起停、改速、转身、跳落、暂停、快速反向、取消、淡出期间重入、重开和独立肩肘前向。没有足够原生样本时失败；同一脚接触中途不能因改速或转向重新归零。

转向 20 cm 为技术样例诊断上限，不是正式滑步品质门槛。超过项目容许范围的转向滑步应使用专用素材或接触约束改善。实际阈值、每窗口残差和失败时刻均在报告中，不能仅引用顶层 ok。
