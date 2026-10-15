# 可选动画播放与接触约束

[English](README.md) | [简体中文](README.zh-CN.md)

| 使用路径 | 说明 |
| --- | --- |
| 准备角色、动作与观测骨 | [离线加工](../../processing/MOTION.zh-CN.md)、[角色配置](../../processing/CHARACTER_PROFILE.zh-CN.md)、[模板](../../../templates/motion_playback/README.zh-CN.md) |
| 基础播放、状态与事件 | 下方创建、替换和已有工程接入步骤 |
| 速度驱动的移动混合 | [LOCOMOTION](LOCOMOTION.zh-CN.md) |
| 平地踏步转向 | [TURNING](TURNING.zh-CN.md) |
| 上半身/全身分层与标记 | [LAYERS](LAYERS.zh-CN.md) |
| 地面根运动与物理消费 | [ROOT_MOTION](ROOT_MOTION.zh-CN.md) |
| 地形脚 IK、骨盆补偿、主/辅助手握持 | [CONSTRAINTS](CONSTRAINTS.zh-CN.md) |

各路径有独立的图、素材和消费者约定。可以按项目选择，不把所有模式默认叠加。Godot 使用原生动画树，UE 目标 5.8；软件运行检查与真实设备、人工观感分别记录。

把已加工的角色动作接入实际游戏时间、骨骼混合和角色移动。Godot 使用原生 AnimationTree；UE 5.8 使用真正可编辑的 Animation Blueprint，其 AnimGraph 包含 Sequence Player 和 Blend Poses by Int。它们按项目复制，已有项目可只取适配器，不强制使用样例状态机。

## 职责和范围

- 共享适配器：绑定检查、选择动作、播放率、每次播放编号、按实际序列时间派发标记、完成/中断/重置通知。
- 项目：输入、状态选择、角色移动、跳跃、交互结果、取消条件和镜头。动画事件只提供时机，不自行决定伤害或游戏胜负。
- 默认接收 **控制器拥有位移的原地动画**。通过显式 `root_motion` 策略支持限定的动画地面位移；CLI 检查加工配置和全部根轨迹，适配器检查绑定与图。不能把保留位移的动作标成原地动画混用。
- 旧基础层事件只用于非循环动作，每个名称每次播放至多一次。取消会使旧编号失效；暂停率 0，正向播放率 0..4，不支持倒放、任意 seek 或网络权威同步。可选分层支持每圈一次的标记；基础移动层脚步事件仍需另外接入。
- `select` 同一动作是幂等操作；完整重开用 `reset`。完成事件可以选择下一动作；中断/重置通知正在派发时，递归选择会被拒绝，以免再次进入同一退出回调。

## 创建和运行

先按 [离线动作加工](../../processing/MOTION.zh-CN.md) 生成并验证 motion revision，再提供 `oagd.playback/1` 绑定。每条绑定声明 `id`、加工 `clip`、`duration_s`、`loop`、`motion_owner=controller`、`in_place=true` 和可选 `markers=[{name,at_s}]`。当前样例要求 idle、walk、run、jump、fall、land、action、action_v2；这是样例的玩法范围，不是通用组件要求所有游戏具备的动作集合。

跨引擎绑定 ID 和标记使用小写字母、数字与下划线，并以字母开头。UE 的 FName 比较不区分大小写，出包后显示拼写可能来自引擎已有名称；样例记录统一为小写。加工片段本身的 `clip` 名仍沿用源资源。

```text
python tools/motion_playback.py create --engine godot --project NEW_PROJECT --revision REVISION --bindings bindings.json
python tools/motion_playback.py create --engine unreal --project NEW_PROJECT --revision REVISION --bindings bindings.json --ue-root UE58
```

Godot：`Godot --headless --path PROJECT --script PROJECT/prepare.gd`，随后打开 `project.godot`。导入生成合并动画库、共享骨架与可编辑动画树的 PackedScene。场景保存后游戏只读取该资源，运行时不重新读取 Blender 或 FBX。

UE：编译 `MotionPlayEditor`，再运行 `UnrealEditor-Cmd PROJECT/MotionPlay.uproject -run=pythonscript -script=PROJECT/prepare.py -nullrhi -unattended`。脚本把所有 AnimSequence 导入同一 Skeleton，保存 Bindings DataAsset、ABP_Player 和 Example 地图。编辑器模块只负责图生成；独立包只包含运行模块。

新建 UE 示例显式使用 D3D12 / Shader Model 6，以固定本案例的渲染配置。首次启动可能需要较长的着色器编译。自动取证可使用 UE 原生 `-RenderOffScreen`，仍执行实际 GPU 渲染；`-nullrhi` 只用于骨骼/规则检查，不能作为画面验收。自动测试可使用独立缓存目录。项目日常打开不需要离屏参数。

WASD 移动、Shift 跑、Space 跳、E 播放手势、Q 取消、R 重开。角色和手势是原创建模/动作技术样例，不是最终角色美术。`templates/motion_playback/author_sample.py` 在 Blender 中生成可编辑源、明确映射、加工配置和绑定；用 motion_workflow 的 process 加工后再创建工程。源里故意加入的 action 单帧异常会走真实自动修复路径。

## 替换动作

```text
python tools/motion_playback.py stage --project PROJECT --revision NEW_REVISION --bindings NEW_BINDINGS
# 再执行当前引擎 prepare 脚本，保存新的原生资源。
python tools/motion_playback.py activate --project PROJECT
```

stage 验证加工证据，复制到新版本输入目录，并写 `bindings.pending.json`；当前游戏继续使用旧绑定。prepare 只创建新的原生资源目录/场景。activate 核对绑定、源文件及原生输出哈希后切换当前选择，并保存旧绑定和 UE 配置到 `.openaigame/playback-history`。没有成功导入证据时不能激活；激活不代表运行验收通过。重新启动游戏后继续记录状态、实际姿态和事件。

`status` 展示创建时固定副本与当前项目的差异；项目规则、配置和资产替换产生的差异需按项目记录解释，不自动覆盖本地修改。原始 `.blend` 与所有加工 revision 留在制作记录中，stage 不复制整个制作历史到运行包。

## 接入已有工程

Godot 可只复制 `godot/oagd_playback.gd`，调用 configure 绑定项目自有 AnimationTree 状态机，select 选择项目节点。示例图采用 0.12 秒转换；configure 不创建、覆盖原项目图。树使用手动处理模式，由项目每帧以真实 delta 调用 advance；这会执行正常动画求值和混合，不是逐帧 seek。项目负责固定且唯一的更新顺序。

UE 可只复制 OAGDPlayback 插件，使用 UOAGDPlaybackComponent、UOAGDPlaybackSet 和派生 UOAGDPlaybackAnimInstance。图索引顺序必须与 Bindings.Clips 一致，PlayRate 接 PlaybackRate，切换时重置新激活的 Sequence Player。示例 builder 创建新图时执行引擎节点初始化，注册属性输入绑定。采样在 NativePostEvaluateAnimation 后读取实际节点时钟，同时检查请求代次和有效混合权重，防止未激活节点保留的旧结束时间重发事件。现有 Montage、复杂多层图或异步/并行更新需要单独适配，不宣称直接兼容。

## 取证与限制

样例支持通过命令行运行固定输入处理器日程，记录实际引擎状态、角色/骨骼轨迹、播放时间和事件。这是可复现的程序驱动测试，不能冒充真人试玩。记录路径需是可写的新文件。

```text
Godot --path PROJECT -- --report=REPORT_JSON --fps=60
UnrealEditor-Cmd PROJECT/MotionPlay.uproject MAP -game -MotionReport=REPORT_JSON -UseFixedTimeStep -FPS=60 -unattended
```

固定步长用于可重复检查，不是性能基准。独立 Windows 包还必须实际启动验证；编译或导出成功不能代替出包后运行。本段描述基础原地播放样例的验证边界：平地、已匹配速度和指定支撑窗口。根运动与脚/手约束另按各专页采用；基础样例不证明这些模式、网络或最终美术品质已通过。

示例的解剖前方为 Blender -Y，由脚尖、鼻子和白色胸前面板标明。Godot 命令行加入 `--view=side` 或 `--view=front`，UE 加入 `-MotionView=side` 或 `-MotionView=front`，以近距离侧面/正面观察。记录包含实际肩、肘、手和前向向量。示例方向回归应同时检查上臂抬起、肘弯曲的意图和原有事件/位移，不以手骨在运动替代方向判断。方向检查应对照项目预期的姿态与动作意图。

UE 示例在世界 `OnWorldPostActorTick` 后记录骨骼、动画时钟和角色位置，避免输入 Tick 读取上一轮姿态时与本帧移动混在一起；该观察回调不驱动或修正姿态。侧面/正面复核使用柔和补光，让空场景中的身体前向可见。

实现依据：[Godot AnimationTree](https://docs.godotengine.org/en/stable/tutorials/animation/animation_tree.html)、[UE 5.8 混合节点](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-blueprint-blend-nodes-in-unreal-engine)。
