# 运行管线

本适配器已在 Windows、Blender 4.5.14 LTS、Unreal 5.8.2、Manny Simple / SK_Mannequin 上实跑。核心诊断脚本只用 Python 标准库；Blender 脚本在 Blender 内执行，UE 脚本在启用 Python Editor Script Plugin、Editor Scripting Utilities 的 Unreal Editor 内执行。不同骨架、采样率和 UE 版本先做单招试传。

这是已有样例的运行记录，不代表每次技能更新都重跑了 Blender/UE。制作次序和已有资源入口见 [验证分工](production-order.md)。已有 UE 动画可直接在独立地图或实验工程测试；以下 FBX 命令只适用于需要外部制作和回传的分支。

## 当前入口与 /1 兼容范围

v0.2 的 `/2` 支持外部制作、原生复用、局部修改、显式骨名/附件、方向和辅助手握持区间，见 [模式和绑定](modes-and-bindings.md)。下列旧攻击样例限制只适用于 `/1`，不可外推到 `/2`。已有 UE 原生动作使用 `/2 native_reuse`，不再通过省略 gate 绕过验收。

当前工程执行统一调用共享会话：`python ue_editor_stage.py --session --project <项目根> --request <实际请求.json> --runtime <工具包根>`。请求沿用 `engine_workflow.py` 的 inspect/edit/playback，角色读取、派生预览、绑定检查和连续帧都复用同一生命周期与回执。独立安装 Skill 时，可明确指定已有的共享运行时；不要求启动其他职业或新建审批。

下面直接运行旧编辑脚本的命令仅保留为原有 `/1` 样例复现资料，当前任务不另建进程管理器。

方法可以用于其他角色，随包代码仍有样例约束：当前清单/分析器要求攻击的 `contact_s` 和 `test_distance_cm`，握持/跳变检查使用 `hand_r`、`hand_l`。无命中事件的待机/移动、自定义骨名需先适配，不能伪造接触事件只为通过脚本。

辅助手握点按整段测量，尚无握持/松手区间诊断；武器回传比较目前测量位置，不覆盖武器自身旋转误差。双手释放和武器朝向要另行观察/测量并记录未自动覆盖项。`gate` 只核对现有报告和证据完整性，不增加这些测量能力，也不能作为通用动画品质认证。

现有 UE 资源无需为使用测试方法而生成虚假的 `.blend`、FBX 或外部 comparison。该分支用真实 UE 资产版本、测试场/游戏播放和问题报告交接；只有实际走了回传协议才调用对应 `audit/gate`。方法上的适用范围与脚本已实现的协议范围分别判断。

## 建立独立工作区

保留原工程。可在已授权工程增加独立测试地图，或建立实验工程；需要隔离时复制必要的 Source / Config / Content / .uproject，或创建 C++ Third Person 工程后迁移所需资源及依赖。不要复制旧 Binaries/Intermediate；在本机编译。目标 Mesh/Skeleton 必须来自实际选定角色，不能替换成相似代理。

把 `assets/unreal/AnimationLab.h/.cpp` 放入实验工程模块。Build.cs 添加 `Json`、`JsonUtilities`、`ProceduralMeshComponent`、`InputCore`、`Engine` 依赖，uproject 启用 ProceduralMeshComponent。`ANIMLAB_MODULE` 默认为 RiftDuel，换模块时明确设置。测试 Pawn 的 Mesh 朝向为 Manny 的相对 yaw -90°，其他骨架必须校准，不可照抄。

已有程序驱动动作：改写项目采样入口，输出 `animlab.capture/1`。`assets/rift-baseline` 依赖 RiftPlayer/RiftWeapon/RiftRules，仅供本项目。它在骨骼与武器实际求值后采样，关闭角色位移与 Boss AI，保留单招和连段基线；不是通用动作生成器。已有 FBX/艺术源文件：沿用其作者工程，用目标骨架试传，不必先人为合成一份“旧游戏采样”。

## 已测试命令

以下为 PowerShell；`$Lab` 指工作区、`$Skill` 指此 skill 目录，`$UE` 指 UnrealEditor-Cmd.exe，`$Blender` 指 blender.exe，`$Python` 指 Python 可执行文件。引号包裹每个路径。实际交付样例有 `Pipeline.ps1` 包装和本机 `toolchain.local.json`。

```powershell
$env:ANIMLAB_WORKSPACE=$Lab
$env:ANIMLAB_STAGE='export-reference'
& $UE "$Lab/unreal/RiftDuel.uproject" -run=pythonscript "-script=$Skill/scripts/ue_editor_stage.py" -RenderOffscreen -AllowCommandletRendering -unattended
# 参考 SkeletalMesh 导出需要渲染资源；此版本不能使用 -NullRHI。

# 已获取 capture/baseline.json 后初始化，拒绝覆盖已有 manifest。
& $Python "$Skill/scripts/anim_pipeline.py" init --workspace $Lab --capture "$Lab/capture/baseline.json"
& $Blender --background --factory-startup --python-exit-code 1 --python "$Skill/scripts/blender_stage.py" -- --workspace $Lab --mode prepare
& $Blender "$Lab/source/AnimationLab.blend" --python "$Skill/scripts/blender_stage.py" -- --workspace $Lab --mode ui

# 编辑完成先保存源文件，再导出新版本。
& $Blender --background "$Lab/source/AnimationLab.blend" --python-exit-code 1 --python "$Skill/scripts/blender_stage.py" -- --workspace $Lab --mode export
$env:ANIMLAB_STAGE='import'
& $UE "$Lab/unreal/RiftDuel.uproject" -run=pythonscript "-script=$Skill/scripts/ue_editor_stage.py" -NullRHI -unattended
$env:ANIMLAB_STAGE='build-stage'
& $UE "$Lab/unreal/RiftDuel.uproject" -run=pythonscript "-script=$Skill/scripts/ue_editor_stage.py" -NullRHI -unattended

& $UE "$Lab/unreal/RiftDuel.uproject" '/Game/AnimationLab/Maps/AnimationLab?game=/Script/RiftDuel.AnimationLabMode' -game "-AnimationLabManifest=$Lab/manifest.json" "-AnimationLabAudit=$Lab/capture/unreal-roundtrip.json" -NullRHI -unattended
& $Python "$Skill/scripts/anim_pipeline.py" audit --manifest "$Lab/manifest.json" --capture "$Lab/capture/unreal-roundtrip.json" --compare "$Lab/capture/blender-source.json" --out "$Lab/reports/roundtrip-audit.json"
```

每阶段检查退出码、日志及实际资源。UE 工程、模块名、DDC 路径依机器配置；本次环境另需 `-DDC=InstalledNoZenLocalFallback`。不要把启动成功等同于动画导入成功。

## 修改下一版

保留 baseline-r1 目录与证据。新工作区复制参考 FBX、真实 baseline capture 和 `.blend`；实验 UE 工程可复制或复用同一个专用工程，但必须给候选新的 `/Game/AnimationLab/Clips/<revision>/...` 资源路径。不要改原战斗工程的引用。

新 manifest 更新 revision、选定 clips 的 role=candidate、fbx 路径、ue_asset、事件与时长；未选招式可从本轮清单移出，但保留原始 baseline 数据。`evidence_dependencies` 指向本轮真实 `.blend`、参考与 `.uasset` 文件，不能继续写旧版本。此基础适配器使用 60 Hz；其他速率要同时修改导出、导入和原生采样器。

打开源文件编辑 Action。当前样例是密集 FK 骨骼烘焙，保留真实蒙皮和可编辑关键帧，尚无便捷的美术 IK 控制器。可在源端添加非变形控制骨/约束，但输出时只保留验证过的目标骨架；新增控制骨不能无意进入目标层级。先修身体重心和肩肘姿态，再校准辅助手约束与武器握点。

`export` 对仍标为 baseline 的动作检查是否被意外改动；candidate 允许作者修改。随后它实际求值新 Action（包含约束），生成 `capture/blender-source.json`，再导出各招 FBX。候选回传必须与这份新源采样比较，不能要求新动作仍等于旧坏动作。单独 `--mode sample` 可以复采已有源场景；采样前保存源文件。

导出与导入均拒绝覆盖已存在目标。路径换新版本后重跑；不要为了省事删除艺术源。绑定草稿用 `apply-binding --manifest ... --draft ... --out 新文件` 应用；新清单作为下一轮工作区的 manifest.json 后，同步 Blender 武器对象绑定并重新采样。

## 测试与交接

正常和 0.25×，正/侧/游戏视角，检查完整起招—接触—收招与链路接缝。Blender `--mode render --clip hammer_heavy --view side --speed .25 --out 绝对路径.mp4` 输出慢放；PNG 为 contact 事件单帧，不能替代播放检查。

原生测试场：Q/E 切动作，空格暂停，左右逐帧，逗号/句号变速，C 换视角，V 接触标记；J/L、K/I、U/O 调整绑定 XYZ，Shift 配合相同键旋转，B 写 Saved/AnimationLab 草稿，R 恢复清单值。只改测试场内存和草稿。

`-AnimationLabSelfTest=绝对路径.json` 实测原生控制函数和导入资源；不代表操作者完成键盘/手感评价。`-AnimationLabShowcase` 输出数张真实运行帧用于画面检查，不是动画品质通过。

完成当前版本人工/播放评审后，review 填 reviewer、report_sha256、各招 decision、evidence 相对路径、evidence_sha256 路径→哈希、逐项问题豁免理由。`gate` 返回 0 才产生交接计划；返回 2 表示未满足条件。门禁检查证据版本完整性，不能代替视觉判断，也不是防篡改系统。

## 已知坐标经验与来源

此 Manny 参考经 Blender FBX 导入时，UE root 被表示成 Armature 对象。脚本只在已知拓扑匹配时显式恢复 root 骨，使用参考骨位置拟合轴向/单位，再对每帧按同一采样的父骨变换计算局部姿态。不要自动“修复”任意缺骨。

Epic 的 [FBX Animation Pipeline](https://dev.epicgames.com/documentation/unreal-engine/fbx-animation-pipeline-in-unreal-engine) 说明 UE 使用 FBX 2020.2；Blender 的 [FBX 文档](https://docs.blender.org/manual/en/4.4/addons/import_export/scene_fbx.html) 说明约束结果需要烘焙，约束本身不会原样成为导出控制系统。实际选项以本机 Blender 4.5.14 和回传结果为准。不存在仅凭某组导出勾选项就能保证所有骨架正确的结论。
