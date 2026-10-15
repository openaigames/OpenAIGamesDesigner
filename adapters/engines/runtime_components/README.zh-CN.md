# 可选运行组件

[English](README.md) | [简体中文](README.zh-CN.md)

适用于已经选择 Godot 或 UE 5.8、需要补充基础移动／镜头／交互查询的新工程。已有角色框架可以只用查询、会话或几何入口。组件随项目复制并锁定哈希，不在多个游戏间共享可写文件；更新工具包不会改变已有游戏。

## 职责和入口

| 公共能力 | Godot | Unreal 5.8 | 项目负责 |
| --- | --- | --- | --- |
| 输入、重绑定、上下文与暂停原因 | OAGDInput / OAGDFocus | UOAGDInputComponent / FOAGDFocusStack | 动作名、消费者、菜单和真正暂停引擎 |
| 原生导航与移动目标 | OAGDNavigation | UOAGDNavigationComponent | NPC 行为、重试、移动适配和性能范围 |
| 静态资产派生与替换 | OAGDStaticAssets | UOAGDStaticAssets | 稳定对象映射、碰撞策略、资源与关卡验收 |
| 地面移动、重力、跳跃、碰撞 | OAGDActor / CharacterBody3D | AOAGDCharacter / CharacterMovement | 输入映射、速度选择、冲刺、战斗限制 |
| 跟随镜头与避障 | OAGDCamera / SpringArm3D | CameraArm / SpringArmComponent | 镜头模式、输入、锁定与取景要求 |
| 有遮挡的近距查询 | OAGDQuery.ray | UOAGDQuery::VisibleHit | 可交互条件、伤害、开门、拾取 |
| 状态通知和重开代数 | OAGDSession | UOAGDSessionComponent | 状态名称、胜负判定、清理与重建内容 |
| 本地设置、命名存档槽 | OAGDSettings / OAGDStore | FOAGDSettings / FOAGDStore | 保存字段、数据版本、目录与恢复提示 |
| 场景准备与提交 | OAGDScene | UOAGDSceneComponent | 被动场景适配器、稳定 ID、检查点规则、暂停所有权 |
| 目标与交互请求 | OAGDInteractable / OAGDInteraction | UOAGDInteractableComponent / UOAGDInteractionComponent | 条件、同步提交规则、查询视点、输入和 UI 展示 |
| 通用音效、特效及镜头反馈 | OAGDFeedback | UOAGDFeedbackComponent | 事件语义、cue 资源、位置／owner、场景作用域与相机合成 |
| 生成几何接入 | OAGDGeometry.load_scene | AOAGDGeometry::LoadScene | 使用哪份已选版本、关卡／美术验收 |

Godot 模块均可单独使用。UE 查询库与会话组件不依赖采用 AOAGDCharacter；这个可选角色基类自带跟随镜头。两套实现均使用原生引擎物理。没有在公共组件中预设伤害数值、任务、背包或角色成长，也没有自建一套引擎无关的全能运行时。

## 安装到已有工程

从工具包共享 runtime 根目录执行，路径换成实际位置：

```powershell
python tools/runtime_components.py install --engine godot --project C:/Games/MyGodotGame
python tools/runtime_components.py install --engine unreal --project C:/Games/MyUEGame --ue-root D:/UE_5.8
python tools/runtime_components.py status --project C:/Games/MyUEGame
```

Godot 写入 `addons/oagd`；UE 写入 `Plugins/OAGDCore`。UE 的使用方 C++ 模块添加 `OAGDCore` 依赖；插件依赖引擎自带 ProceduralMeshComponent。已有工程的主场景、GameMode、输入映射及角色均不自动替换。只放入文件尚不代表已经接入玩法。

`.openaigame/runtime-components.json` 保存组件版本、引擎目标、文件哈希。同版重复安装可读回状态。遇到不归工具所有的文件、手工修改或不同锁定版本，安装器报冲突；先合并项目修改，再在独立副本显式迁移。没有后台升级或强制覆盖选项。

安装器暂存待写入文件，并在可捕获的写入错误后清理，失败后可重新执行安装；不承诺断电或强制结束进程后的自动恢复。UE 项目明确声明其他数字版本时拒绝安装；使用 GUID 的自编译引擎关联仍需调用者确认，`--ue-root` 只证明所选引擎版本。示例游戏在胜负结束后统一禁止移动和新的跳跃，按 R 重开。

两引擎在场景实例化前检查格式、对象 ID、数组、颜色和索引；不合法文档整体拒绝，避免留下部分对象。

## 按任务创建案例

| scenario | 说明 |
| --- | --- |
| training / puzzle | 下方基础训练场与钥匙门案例 |
| input | [输入、焦点与暂停](INPUT.zh-CN.md)，包含常用修饰键与滚轮 |
| state | [设置、场景与本地状态](STATE.zh-CN.md) |
| feedback | [声音、特效与镜头反馈](FEEDBACK.zh-CN.md) |
| interaction | [查询、提示、即时/按住交互](INTERACTION.zh-CN.md) |
| navigation | [原生导航与项目 NPC](NAVIGATION.zh-CN.md) |
| scene | [规格生成与通行](SCENE.zh-CN.md)，可传 --scene-spec |
| static | [单网格静态替换](STATIC_ASSETS.zh-CN.md)；多节点流程使用[静态场景模块](../static_scene/README.zh-CN.md) |

下面命令中的 scenario 可替换为需要的案例。每次使用新目录，UE 额外指定 5.8 引擎。已有组件升级使用 [runtime_migration](../../../docs/INSTALLATION.zh-CN.md)，不把 install 当成强制覆盖器。

## 基础训练场与解谜工程

```powershell
python tools/runtime_components.py create --engine godot --scenario training --project C:/Trials/GodotTraining
python tools/runtime_components.py create --engine godot --scenario puzzle --project C:/Trials/GodotPuzzle
python tools/runtime_components.py create --engine unreal --scenario training --project C:/Trials/UETraining --ue-root D:/UE_5.8
python tools/runtime_components.py create --engine unreal --scenario puzzle --project C:/Trials/UEPuzzle --ue-root D:/UE_5.8
```

每次必须使用新目录。训练场负责三次命中和胜利规则；解谜场负责钥匙、门和出口规则。两者都能失败后重开。WASD 移动、Space 跳跃、E 攻击／交互、R 重开，按住右键转动镜头。这些是工程验证灰盒，不代表角色动画、美术、音频或游戏手感已经完成。

Godot 打开 `project.godot`。UE 先编译 `OAGDExamplesEditor Win64 Development`，再执行该工程的 `create_map.py`：

```powershell
& D:/UE_5.8/Engine/Build/BatchFiles/Build.bat OAGDExamplesEditor Win64 Development -Project=C:/Trials/UETraining/OAGDExamples.uproject -WaitMutex -NoHotReloadFromIDE
& D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe C:/Trials/UETraining/OAGDExamples.uproject -run=pythonscript -script=C:/Trials/UETraining/create_map.py -unattended -nullrhi
```

地图脚本仅负责编辑器建图，实际玩法在项目 C++ 模块。直接打开或在编辑器中 Play 即可运行。案例源文件可自由修改；公共库不会根据案例规则反向改变。

## 可重复验证

```powershell
python tools/runtime_validation.py --engine godot --project C:/Trials/GodotTraining --executable C:/Tools/Godot.exe
python tools/runtime_validation.py --engine unreal --project C:/Trials/UETraining --executable D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe
```

加 `--visual` 运行渲染并保存截图。Godot 报告在工程 `validation.json`；UE 在 `Saved/validation.json`。运行器归档旧结果，以此次运行的新报告、退出码和逐项断言判定，不凭日志中的成功字符串判定。执行命令、输出和报告保存在 `.openaigame/runtime-validation/<run>`。

验证覆盖真实移动、生成几何碰撞、墙体阻挡、遮挡查询、交互距离、项目胜负、重开与地形单位。Godot 通过 Input action 驱动移动，UE 调用项目原生输入处理函数；不宣称人工键鼠试玩。发布包、网络同步、任意地形可达性及所有 Godot 4.x 版本都不在这组检查的结论中。

## 规格和内容替换

几何规格、GLB、`scene.json` 和检查报告见[程序化生成](../../processing/PROCEDURAL.zh-CN.md)。两套引擎消费相同场景结构：源为右手系、Y 向上、米；Godot 原尺度，UE 转为 X 前／Y 右／Z 上、厘米。面朝向随引擎惯例转换。源对象 ID 映射为 Godot 节点名和 UE Actor Tag。

提供固定基线的静态资产映射、派生网格／材质／LOD、原生替换和回滚，见 [STATIC_ASSETS.md](STATIC_ASSETS.zh-CN.md)。支持的输入与限制以该说明为准。当前加载器创建运行时原生对象；没有承诺把已编辑的引擎场景自动反向转换成生成规格。JSON 对象级三方合并只保护该 JSON 中的手工修改。

## 实现与许可

组件使用引擎原生的 CharacterBody3D、CharacterMovement、SpringArm 等机制，随仓库 LICENSE 分发。Godot 与 UE 的接入方式见上方入口。
