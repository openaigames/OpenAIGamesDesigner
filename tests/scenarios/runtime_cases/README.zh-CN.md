# 原生运行组件回归用例

[English](README.md) | [简体中文](README.zh-CN.md)

通过[运行组件工具](../../../adapters/engines/runtime_components/README.zh-CN.md)创建隔离的 Godot 或 UE 示例，使用 `runtime_validation.py`，按实际引擎安装位置和输出目录执行生成的场景。

覆盖已有项目安装、重复安装、本地修改保留、输入焦点与暂停、交互取消、保存和载入、场景切换及清理。按照[安装说明](../../../docs/INSTALLATION.zh-CN.md)，在可丢弃的副本中测试更新和回滚。

保留命令、原生报告、日志、源修订和实际失败记录，同时检查报告与进程退出码。物理设备和人工试玩需要独立于程序化输入验证，证据要求与完成条件见[验证说明](../../README.zh-CN.md)。
