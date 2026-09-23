# Unreal 制作接口

## 创建与启动

[production.py](production.py) 独立维护 Unreal 的请求规则、工程描述、插件要求和启动命令。当前制作 runner 使用 Windows 的实际 Unreal Editor。

```powershell
python tools/engine_workflow.py create --project "D:/Games/MyUEGame" --engine unreal --editor "D:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --name MyUEGame --version 5.8 --brief "已确认的本轮范围"
```

新建内容工程，明确启用 PythonScriptPlugin 与 EditorScriptingUtilities，再实际加载验证。C++ Target 和模块按项目技术方案添加，不默认引入 GAS 或样例工程。edit/inspect 使用 Python commandlet；playback 使用独立编辑器的 PIE 与异步 Python 保活。

帧序列与采样都有编辑器/截屏开销，不包含同步音频；性能测量请单独关闭 capture_interval。已安装插件不等于原生 MCP 接通，MCP 证据另行记录。

公共入口与恢复：[会话管理](../sessions.md)。实现：[production_worker.py](production_worker.py)，在真正 Unreal Python 环境中执行；不是外部 Python 模拟，也不是原生 MCP 调用。

| 操作 | 必填与用途 |
| --- | --- |
| scene | `/Game/...` 的 `path`；`create: true` 新建，否则打开 |
| blueprint | 新 `path`、`parent_class`（默认 Actor）、components（name/type/properties） |
| actor | `target` 精确且唯一的 Actor Label；新建选 `class` 或 Blueprint/资源的 `source`，显式 `create: true` |
| import | 源文件绝对 `source`、目标 `/Game/...` 的 path；覆盖必须 `replace: true` |
| animation | target、mesh，以及 animation 或 anim_blueprint；component 可进一步指定名称 |

actor 的 position/rotation/scale 分别为世界坐标 XYZ（UE 厘米）、Pitch/Yaw/Roll（度）、缩放。已有组件在 actor.components 中按 type 和可选 name 精确定位。新增持久化组件通过 SubobjectDataSubsystem 写入新的 Blueprint，再实例化；不把临时 new_object 组件当成保存后仍存在的组件。已有蓝图路径拒绝覆盖，避免清除手工图表。

properties 使用实际 `set_editor_property` 名称。值可以是 JSON 标量，以及 `{"asset":"/Game/..."}`、`{"vector":[x,y,z]}`、`{"enum":"ComponentMobility.MOVABLE"}`、`{"class":"/Game/..._C"}`。复杂结构、数组或特殊属性请按项目扩展，不能将未支持类型静默忽略。保存后读回对象、组件、常用网格/材质/动画引用。

导入走 AssetTools / AssetImportTask，检查真实 imported_object_paths；FBX 可显式给 skeletal、animations、skeleton。具体格式与 UE 的已安装导入插件有关，导入成功不代表单位、材质、骨骼和视觉已经验收。资源重新命名和文件依赖要以真实返回路径为准。

角色使用 SkeletalMeshComponent，支持同骨架 AnimSequence 的单节点循环配置，或已有 Animation Blueprint 的绑定。骨架不一致直接报错，不隐式重定向、不自动选动作。Animation Blueprint 的创作、复杂重定向、Montage/Notify、Motion Matching、GAS 技能图属于进一步的项目专项实现，不由本接口伪造。

示例：[关卡与蓝图组件](examples/scene.json)、[PIE 自动操作](examples/playback.json)。自动操作使用实际 PIE 世界副本，不把测试位移保存回编辑场景。actions 支持 `position`，或 `{at,op:"method",target,method,arguments:[]}` 调用项目对象暴露给反射的方法；不发送 OS 键鼠，也不声称覆盖 Enhanced Input 链路。

PIE 使用 EditorPythonScripting 的保活开关和 Slate tick 驱动，明确请求开始/结束，再关闭本次独立编辑器。录制为活动 PIE 视口 PNG；世界 delta 由编辑器观察采样，有编辑器/截屏开销，不是 GPU 或完整 CPU profile。UE API 随版本变化，原始日志和版本是每次会话的依据。正式性能测试仍应使用目标平台构建及 Unreal Insights。
