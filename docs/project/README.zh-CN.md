# 项目说明

[English](README.md) | [简体中文](README.zh-CN.md)

OpenAIGamesDesigner 是一个面向 AI Agent 与游戏开发者的开源游戏开发工具包。项目将专业工作方法、制作流程、命令工具和引擎适配放在同一仓库中，用于新建原型、接手已有工程、制作资产、修改功能与验证交付。

## 项目结构

| 目录 | 用途 |
| --- | --- |
| [skills](../../skills/README.zh-CN.md) | 策划、美术、动画、音频、程序与测试等专业工作方法 |
| [workflows](../../workflows/README.zh-CN.md) | 从立项到交付的流程，可从任一适用阶段开始 |
| [tools](../../tools/README.zh-CN.md) | 项目执行、看板、资产任务、数值交换及检查命令 |
| [adapters](../../adapters/README.zh-CN.md) | 引擎、资产生成服务与本地处理工具的接入 |
| [templates](../../templates/README.zh-CN.md) | 项目文档、资产规格、运行组件和示例工程模板 |
| [schemas](../../schemas/README.zh-CN.md) | 配置、任务、资产和执行记录的数据格式 |
| [tests](../../tests/README.zh-CN.md) | 自动检查、场景评估和原生工具验证入口 |

## 如何使用

可以从一个想法、已有设计、现成素材或正在开发的游戏工程开始。Agent 按任务调用相关 Skill 和工具，将设计、源文件、工程改动和验证结果保存到游戏自己的项目目录。

专业 Skill 可以单独使用。运行组件按需复制到游戏工程；Godot 使用项目内脚本，UE 使用项目内插件。项目自行定义输入动作、玩法规则、保存字段、资源与角色绑定，工具包更新不会自动改动已有游戏。

引擎适配覆盖 Godot、Unity、Unreal Engine、Three.js 与 Phaser；各自的接入方式见[引擎索引](../../adapters/engines/README.zh-CN.md)。通用运行组件与动画播放提供 Godot 和 UE 5.8 实现，其他引擎按其适配器说明使用。

## 工作成果

项目保留可继续编辑的设计资料、资产源文件和游戏工程。自动检查用于确认文件、接口与运行行为；画面、声音、操作体验和目标平台表现需要在具体游戏中验证。示例工程展示模块接入方法，玩法与美术可由项目替换。

从[安装指南](../INSTALLATION.zh-CN.md)开始，或通过[文档导航](../README.zh-CN.md)直接查找需要的模块。
