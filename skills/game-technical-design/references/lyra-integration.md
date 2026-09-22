# Lyra 工程接入与扩展

仅在项目实际基于 Lyra 或用户明确选择接入时读取。Lyra 是已有框架与样例，不是全部 UE 工程的强制底座，也不预设当前任务是射击游戏。

先确定 UE 与 Lyra 基线版本、实际 Experience、Game Feature 依赖、Pawn Data、输入配置、Ability Set 和装备路径。以实际源码/资产核对能力如何授予、初始化和移除；不要同时绕过现有输入路径另建一套技能触发。

Lyra 默认玩家与机器人 PlayerState 的 ASC 组织方式需要结合当前项目核对；自定义 Boss 或其他 Actor 不机械复制。检查 Pawn 初始化与重生、装备切换及 Experience 变化是否影响本轮功能。

优先在项目自有内容或适用插件中扩展，是否使用 Game Feature 由实际依赖决定。复用样例时保留必要依赖，不将复制若干资产当作完成框架解耦；确需修改基础类时记录改动与升级影响。

角色替换需核对骨架、动画层、Montage、挂点与输入/技能引用；运行原地图成功不能证明新 Experience 或目标打包版本可用。实现招式还需明确命中、打断与结束清理，不能只接通动画。

交付项目实际入口、依赖关系、扩展位置、回归范围和结果。共享 UE 执行边界见 [UE 工程方法](unreal-project.md)，技能机制见 [GAS 方法](gas-combat.md)。本参考不代表工具包已安装 Lyra 或实现编辑器连接。

官方依据：[Lyra 样例](https://dev.epicgames.com/documentation/en-us/unreal-engine/lyra-sample-game-in-unreal-engine)、[Lyra 技能](https://dev.epicgames.com/documentation/en-us/unreal-engine/abilities-in-lyra-in-unreal-engine)。
