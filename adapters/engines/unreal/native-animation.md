# 原生角色、动作和武器观察

复用 `tools/engine_workflow.py execute`。`inspect` 的 `character_exports` 从实际 SkeletalMeshComponent 读取模型、Skeleton、Single Node 或 AnimBP 静态依赖，也可调用项目明确提供的只读动作集合函数。静态引用、声明可用集合与已经观察到的运行行为分别标注。集合函数需返回 `actions:[{id,label,asset}]` 和非空 `source_assets`，不得按文件名猜绑定。当前 FBX 导出支持项目 `/Game` 的同 Skeleton AnimSequence；插件外部挂载、Montage 混合或自定义资源需要项目适配，不能强制转成“单文件动作已经验证”。

```json
{"engine":"unreal","mode":"inspect","scene":"/Game/Demo/Map","inspect_targets":["name:SkeletalMeshActor_8"],"character_exports":[{"id":"hero","target":"name:SkeletalMeshActor_8","component":"SkeletalMeshComponent0","role":"player","previews":true}]}
```

完成后运行 `tools/engine_characters.py --project PROJECT --session SESSION`。同步校验 session、项目、原件哈希、导出 FBX 哈希，再写现有 `.asset-browser/characters.json` / `previews.json`。每个角色持有独立版本依据；其他角色不会被顺带“刷新通过”。派生预览保存在 `previews/engine/SESSION/`，不增加候补流转或登记门槛。浏览器 FBX 仅用于动作浏览，不能替代引擎混合、附件、材质和输入检验。

运行观察请求可为 actor 设置 `attached_actors:true`，读回 BeginPlay 创建的独立武器 Actor。`observe.animation_capture` 包含 `target`、`component`、`clip`、`start`、`duration`，可选 `weapon:{mesh_asset,attachment,kind,component}`；武器按实际父组件及资源路径查找，歧义会报错，不回退到 `hand_r`。输出同一会话内的 `animation-capture.json`（`animlab.capture/2`），可直接交给动画诊断器。观察时段相对首次 PIE 采样，包含实际世界姿态和可获取的原生动作时间，不能声称从片段零帧重演。

已有镜头用 `camera_target`。需要只读原资源观察时可用 `observation_camera:{position:[x,y,z],rotation:[pitch,yaw,roll],field_of_view:60}`：创建本次编辑器内存中的临时镜头，复制进入 PIE，退出后移除，全程不保存原关卡。`readonly_preview:true` 拒绝资产编辑和游戏动作调用；临时观察镜头在结果中明确记录。完成检查应核对源文件 before/after、PIE 世界、实际姿态变化和画面，不能以进程退出或骨骼数量代替动画在播放。

屏外动画可能受项目的可见性 Tick 策略影响；应先把对象放进观察镜头验证，不能静默更改角色 Tick 规则。截图会增加采样开销。绑定 / 握柄 / 脚部 / 命中接触只测明确声明且实际采到的区间；未制作接触标记的项目不补造“接触通过”。
