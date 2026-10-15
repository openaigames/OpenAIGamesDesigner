# 接收案例

[English](RECEIVE.md) | [简体中文](RECEIVE.zh-CN.md)

本包从冻结输入重建，包含两个门、两个箱子和两个 Clockhill 建筑实例。Godot 4.7.2 / UE 5.8.2；UE 需已配置 C++ Win64 编译工具。环境路径由 OAGD_ENGINE_CONFIG 指向 JSON，键为 godot、unreal、godot_template、ddc。不得把引擎缓存视作项目源文件。

Godot：runner.py gd-prepare --script baseline.gd；freeze.py Godot；runner.py gd-prepare；runner.py gd-prepare --script rollback.gd；runner.py godot --view applied / recovered。每个 runner 调用必须附不同 --label。configure_export.py 后 runner.py gd-export，再 gd-package-run。

UE：runner.py build；runner.py ue-script --script baseline.py；freeze.py Unreal；runner.py ue-script；runner.py ue-script --script rollback.py；runner.py unreal --view applied / recovered；runner.py ue-export；runner.py ue-package-run。每步核对 JSON 检查报告，不能只看退出码。

每个生成目的地要求不存在。失败输出保留在 evidence；复制失败请使用全新接收目录。原生导入中断时保留失败目录，重新由快照接收并重建，不能覆盖唯一修改。人工改动冲突要保留现场；新进程 rollback 检查收据与当前对象，拒绝不匹配。

输入哈希核验、实际重建运行和真人认可为三个结论。本案例运行是自动技术检查，不代表真人试玩、整个地图可达性或美术完成。源许可见 provenance。
