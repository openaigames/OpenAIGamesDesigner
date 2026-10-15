# 角色重定向与动作修复

[English](MOTION.md) | [简体中文](MOTION.zh-CN.md)

这是共享离线加工工具。项目拥有自己的映射、接触窗口、阈值和输出版本；Godot 与 UE 5.8 消费生成的动画。不会自动替换已有角色、控制器、AnimBP、状态机、武器或游戏规则。

使用[角色配置](CHARACTER_PROFILE.zh-CN.md)：显式局部参考姿势、前向与辅助骨诊断、允许平移骨的固定校准、计入控制器速度的支撑修复，以及逐帧修复范围和总预算审计。原有显式映射配置保持兼容。

FBX 导出使用 COPY 路径模式和嵌入图像保存支持的贴图。复杂材质节点、外部缺失图像和不同材质模型须在重新导入后检查。

加工后的控制器位移动画可通过 [可选动画接入与可玩样例](../engines/motion_playback/README.zh-CN.md) 接入 Godot AnimationTree 或 UE 5.8 AnimBP。该模块独立版本化，包含保存、替换和运行取证流程；离线加工通过不会自动升级为游戏运行通过。

## 可执行范围

| 能力 | 实现与边界 |
| --- | --- |
| 骨架检查 | Blender 读取 `.blend`、FBX、GLB，列出实际 Armature、层级、参考位置/旋转、蒙皮对象、Action 范围和导入场景帧率 |
| 映射建议 | 名称及少量别名产生草稿；歧义不自动选。`process` 使用完整明确的「目标骨 → 源骨」映射并检查祖先关系 |
| 重定向 | 在统一角色空间传递相对参考姿态的全局旋转，再转回目标父骨局部空间；保持目标参考骨架的关节间距与骨轴，未映射骨随自己的目标父骨运动 |
| 根与骨盆位移 | 根位移按显式比例保留或归零。`translation_bones` 显式允许骨盆等非根骨位移；其余非根平移会报错，不能静默删除。保留位移的骨会按原动作改变相对位置 |
| 孤立旋转跳帧 | 只在指定骨上寻找「前后两帧接近、中间一帧显著偏离」，用四元数插值修复；不做全片平滑，不处理连续多帧缺失 |
| 支撑脚修复 | 指定三骨链、支撑时间、弯曲方向及预算，两段骨 IK 固定末端骨原点和方向，支撑区间外平滑淡入淡出；不可达、超位移或关节旋转预算直接失败 |
| 循环接缝 | 仅对指定非根骨的局部旋转，在末尾区间平滑补偿到首帧；不归零行进位移，不保证整个身体或两段不同动作的切换自然 |
| 版本证据 | 每次新目录；保存米制可编辑 `.blend`、Godot `.glb`、UE `.fbx`、源/修复前/修复后真实 DCC 求值、修复事件、哈希和日志。失败版本保留，不覆盖原件 |

支撑点是指定末端骨的原点，不是自动推断脚底、地面高度或地形。没有接触窗口就不声称脚滑通过。自动修复的数值预算是项目配置，不是美术质量标准。

输入必须是自包含、已经蒙皮的导出骨架。目标支持标准骨骼继承和正的均匀 Armature 缩放；不支持控制器约束/驱动器、负或非均匀缩放、剪切、动画伸缩。源 Armature 对象本身的运动需先烘焙到真正根骨。目标网格应直接归属于该 Armature。复杂源控制 Rig 先导出/烘焙代表片段。工具不处理自动绑骨、蒙皮穿模、手指握柄、任意风格重写、布料或动态地面 IK。

目标使用线性混合蒙皮；开启 Preserve Volume 的双四元数蒙皮会被拒绝，不能假设它导出到 GLB/FBX 后仍保持相同变形。目标网格对象上的 Action、NLA 或驱动器也会被拒绝，需先在导出副本中整理，不能静默清除。

每个源片段从同一文件重新加载的初始状态求值，避免稀疏 Action 的未打帧通道继承前一动作。未打帧通道保留源文件保存时的值，不自动推断为参考姿态；需要中性起点时，应先在源副本中明确整理这些值。29.97 等小数帧率的 GLB 使用显式时间轴换算；UE 当前 FbxFactory 入口仍只接受整数采样率。

已知限制：Blender 4.5.9 再导入 29.97 fps FBX 时，虽然文件内时间戳正确，导入器会使回读时长增加约 0.1%。该路径未通过往返验收；需要 FBX 再加工时使用明确的整数帧率导出副本，或先单独处理并验证时间轴。Godot 的 29.97 fps GLB 已通过原生重载检查。

FBX 读取会解除 Blender 导入器推断出的骨骼 `use_connect` 约束，保留父子层级与参考变换，让文件中的子骨平移关键帧实际生效。否则骨盆位移等通道可能有关键帧却不参与求值。此规范化仅作用于 FBX 加载副本，不修改原文件或 `.blend` 作者设置；非根平移仍须在 `translation_bones` 中显式声明。直接用 Blender 默认导入器打开同一 FBX 仍可能遇到此限制。

## 使用

在源码仓库运行以下命令；安装后入口位于 `game-preproduction/runtime/tools`，配套文件位于同一 runtime 的 `adapters` 与 `templates`。Blender 4.5.9 已实际运行；其它 Blender 版本需本机复验。

```text
python tools/motion_workflow.py inspect --blender BLENDER_EXE --input source.blend --output inspect-source
python tools/motion_workflow.py inspect --blender BLENDER_EXE --input target.glb --output inspect-target
python tools/motion_workflow.py suggest --source-inventory inspect-source/report.json --target-inventory inspect-target/report.json --source-armature SourceRig --target-armature TargetRig --output mapping-draft.json
python tools/motion_workflow.py process --blender BLENDER_EXE --spec motion.json --output revisions/r01
python tools/motion_workflow.py verify --output revisions/r01
```

从 [配置模板](../../templates/motion/retarget-repair.json) 填实际文件、检查得到的 SHA-256、骨名和 Action 名。模板不是可以直接套给任意角色的映射。`alignment_xyzw` 是从源 Blender 世界方向到目标方向的单位四元数；不含镜像、缩放或平移。两侧以 Blender 世界米制、Z 向上计算，对象变换参与测量；场景 `scale_length=1`。片段 `fps` 明确解释所选源帧的时间，检查导入帧率后再设定，尤其 GLB 可能按导入场景的 24 fps 重建关键帧。

配置没有开启的修复不会执行。`root_motion.owner=controller` 要搭配 `translation=in_place`；动画驱动保留位移用 `owner=animation, translation=scaled`。这只规范输出，游戏侧如何提取并驱动角色仍由当前消费者明确接入。

脚接触 `start_s/end_s` 均相对于所选片段开始；完整支撑区间前后各保留至少 `blend_s` 的过渡时间。`max_correction_m` 限制末端位移；`max_joint_rotation_deg` 默认为 60°，限制每个关节相对未修复姿态的改变量。不可达时不伸长腿、不移动整个角色蒙混通过，改配置或人工返修后另建版本。

## Godot 原生导入与检查

```text
python tools/motion_native.py prepare --revision revisions/r01 --clip walk --engine godot --output native/godot-r01
GODOT_EXE --headless --path GODOT_PROJECT --script ABSOLUTE_RUNTIME/adapters/engines/motion/godot/import_capture.gd -- ABSOLUTE_PATH/native/godot-r01/job.json
python tools/motion_native.py audit --revision revisions/r01 --clip walk --capture native/godot-r01/capture.json --output native/godot-r01/audit.json
```

生成独立 PackedScene，使用实际 AnimationPlayer 求值和 Skeleton3D 全局骨骼姿态；比对帧数、时刻、持续时间、根骨、逐骨位置、相对首帧的旋转变化及声明的脚部窗口。GLB 的时间零点显式归零。资源含原目标蒙皮，按自己的项目结构选用；不会自动接到现有玩家。

## UE 5.8 原生导入与检查

先生成导入任务：

```text
python tools/motion_native.py prepare --revision revisions/r01 --clip walk --engine unreal --destination /Game/Motion/WalkR01 --output native/ue-r01
```

在子进程环境设置 `OAGD_MOTION_JOB` 为 `job.json` 的绝对路径，执行：

```text
UnrealEditor-Cmd.exe PROJECT.uproject -run=pythonscript -script=ABSOLUTE_RUNTIME/adapters/engines/motion/unreal/import_motion.py -nullrhi -unattended
```

项目需启用 PythonScriptPlugin、EditorScriptingUtilities。脚本仅接受新的 `/Game/` 目录，导入 SkeletalMesh、Skeleton、AnimSequence 并保存全部依赖。参考往返使用 UE 内置 `DefaultRecorderBoneCompression`，实际记录压缩器；切换到游戏压缩配置后需重新采样。为了保持根运动拓扑，FBX 使用 `Armature` 包装节点供 UE 导入器移除；临时厘米制导出副本同时变换骨架、蒙皮和位移关键帧，避免包装节点尺度被动画导入器抵消。米制可编辑源与 GLB 不变。默认中性材质，不宣称完成材质接入。

独立采样可把 [OAGDMotion](../engines/motion/unreal/OAGDMotion) 复制到授权实验工程的 `Plugins/OAGDMotion`、启用并编译 UE 5.8。这个插件是可选的测试消费者，不是所有游戏强制依赖。

```text
python tools/motion_native.py capture-job --revision revisions/r01 --clip walk --import-record native/ue-r01/import.json --output native/ue-r01/capture-job.json
UnrealEditor-Cmd.exe PROJECT.uproject /Engine/Maps/Entry?game=/Script/OAGDMotion.OAGDMotionCapture -game -MotionJob=ABSOLUTE_PATH/native/ue-r01/capture-job.json -nullrhi -unattended
python tools/motion_native.py audit --revision revisions/r01 --clip walk --capture native/ue-r01/capture.json --import-record native/ue-r01/import.json --output native/ue-r01/audit.json
```

采样在真实游戏世界中的 SkeletalMeshComponent 上显式跳到各时间，执行 TickAnimation 与 RefreshBoneTransforms 后读回。它验证原生动画求值与往返精度，不等于真人操作、自然时间播放、AnimBP 混合、Root Motion 提取、游戏取消规则或最终出包测试。已有项目消费者继续使用原有 `engine_workflow.py` Playback 与 animlab /2，不能用此独立场景代替其验收。

## 结果与交接

`report.json.ok` 只表示加工和配置范围内的数值检查通过；`verify` 只检查输入/输出版本未变。`motion_native audit` 另外核对真实引擎读回及原生资产哈希，默认位置残差 2 mm、旋转变化残差 0.2°。这些是工具往返误差阈值，不能代替脚接触阈值或项目美术评审。

源或导入资产变化会使旧证据失效。生产角色接入前，沿用已有资产版本/交付记录，登记源、目标、配置、输出、引擎消费者和播放证据。`oagd.motion-capture/1` 是离线修复对照，不冒充 animlab /2 的游戏运行采样；需要旧管线 gate 时，从当前实际消费者重新生成 /2 证据。

API/实现依据：[Blender 骨骼空间](https://docs.blender.org/api/4.5/bpy.types.Bone.html)、[Godot GLTFDocument](https://docs.godotengine.org/en/stable/classes/class_gltfdocument.html)。UE 行为以实际 5.8 本地 `FbxMainImport.cpp`、`SkeletalMeshEdit.cpp` 和 `SkeletalMeshComponent.h` 及原生实测为准。
