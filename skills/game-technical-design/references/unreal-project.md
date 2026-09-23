# UE 工程接入与实施方法

用于实际 UE 工程；通用工作阶段沿用项目接入、原型、切片或功能变更流程。这里记录技术核查方法，不另设一条 UE 开发流程。

## 接入依据

- 定位真实 `.uproject`、引擎安装/源码版本、Target、模块与插件依赖。以工程和匹配版本官方资料核实编译工具链，不凭“UE5”猜具体 SDK 或编译器版本。
- 检查现有 C++、Blueprint、配置、资源引用、地图入口与已有构建/测试方式。新能力/属性系统需要选型时读取 [能力系统选型](ability-system-choice.md)，已采用 GAS 时读取 [GAS 实现](gas-combat.md)；角色动作按 [动作与动画接入](action-animation-integration.md)。已有系统原位接入，不默认以样例工程重建。用户的另一款游戏不是此项目的默认规则来源。
- 先区分可查看代码、可编译、可启动、可操作编辑器资产、可测试、可打包等能力；发现引擎目录不等于全部接通。修改前核对用户工作和实际可恢复版本。

## 实现与资产边界

C++ 承担项目需要的逻辑与接口；Blueprint、Data Asset 和配置提供可调整的组合与参数。沿用现有分工，不把全部逻辑强制改成某种形式。实际数值保留一个权威来源，设计文档引用它并解释意图。

`.uasset` / `.umap` 通过真实编辑器 API、项目已有脚本/插件或受支持的编辑器操作修改与保存，不作为普通文本打补丁。编辑器 Python 可用于资产导入、检查和配置，但不作为游戏运行时逻辑。任意 Blueprint 图编辑并不因有 Python 就自动可用；先核查具体能力，必要时采用 C++ 接口或可复用资产模板。

编译、资源检查、编辑器运行、自动测试、目标平台打包分别留证。按实际版本与项目配置使用引擎构建/自动化工具，记录命令、日志、地图/测试过滤条件和产物；测试进程退出不能替代测试报告中的用例结果。运行中编辑器未保存的资产不应冒充磁盘输入基线。

## 当前工具包能力

这是方法参考。已有工程运行、测试、编译与交付从工具包 `adapters/engines/unreal/execution.md` 进入；创建工程、场景/对象、资源导入、动画配置与自动运行从 `adapters/engines/unreal/production.md` 进入，对应 `tools/engine_workflow.py`。请求字段、依赖与实际验证范围以这些实现旁的说明为准。原生 Python 执行、宿主 MCP 连接和 GAS 专项是不同能力，分别核实；通用制作入口不代表已实现项目的 GAS 战斗逻辑。不要对 UE 调用 Godot 参数或创建 `project.godot`；使用实际可用的 UE/项目工具，并把缺失能力记录到任务。未安装引擎或缺少工程时仍可完成有依据的设计与准备，但不得伪称可运行。

官方资料：[编辑器脚本](https://dev.epicgames.com/documentation/unreal-engine/scripting-and-automating-the-unreal-editor)、[Python 适用边界](https://dev.epicgames.com/documentation/unreal-engine/scripting-the-unreal-editor-using-python)、[构建与打包](https://dev.epicgames.com/documentation/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine)。实施时核对项目对应版本。
