# 静态场景接入

[English](README.md) | [简体中文](README.zh-CN.md)

## 完整流程导航

| 阶段 | 工具与入口 |
| --- | --- |
| 冻结多节点 GLB/glTF 并原生导入 | static_scene；本页 |
| 灰盒映射、碰撞、通行与持久化回退 | scene_replacement；[替换](REPLACEMENT.zh-CN.md) |
| 组合案例、依赖打包与新目录接收 | scene_handoff；[接收](RECEPTION.zh-CN.md) |

导入层负责冻结依赖与生成原生资源；替换层负责显式碰撞、灰盒映射和回退；工程接收负责输入完整性与入口声明。

在原生场景上继续做灰盒替换、显式碰撞、通行检查和回退，见 [使用说明](REPLACEMENT.zh-CN.md)。本页说明资源冻结与原生导入。

将现有静态 glTF 2 场景冻结为可追溯的新版本，接入 Godot 与 UE 5.8 原生资源。游戏持有自己的场景、模型与材质；生成结果运行时不要求安装 OAGDCore、角色或动作组件。

## 输入与边界

| 项目 | 范围 |
| --- | --- |
| 文件 | GLB 2 或 glTF 2 + 同目录树内的外部 buffer/PNG/JPEG；冻结为自包含 GLB，复制几何、UV、图片字节 |
| 场景 | 活动场景中的多个网格、空节点、父子关系、网格实例、重名节点；稳定编号取源 node index，显示名保留在元数据中 |
| 变换 | 平移、归一化四元数、正均匀缩放；等价无剪切矩阵也支持；非均匀/镜像/剪切须另行明确烘焙 |
| 几何 | 有索引的三角面，浮点 POSITION/NORMAL，可选 UV0/TANGENT；有贴图必须有 UV0；单 mesh 最多 200 万三角形 |
| 材质 | 不透明标准 metallic-roughness PBR、颜色/法线/MR/发光贴图、双面、KHR_materials_emissive_strength；线性 repeat 采样 |
| 色彩 | 颜色/发光按 sRGB；法线和 MR 按线性；glTF 法线 +Y，UE 原生导入翻转绿色通道；MR 的 G 为粗糙度、B 为金属度 |
| 明确拒绝 | 骨架、动画、morph、相机、顶点色、UV1、透明/AO、未知扩展/压缩纹理、远程/data URI、缺失/越界依赖、循环层级、坏索引 |
| 导入层不处理 | 自动灰盒替换、碰撞策略、导航、LOD、Nanite、自定义 HLSL/Shader/GI 迁移。新导入实例无碰撞；这些用途不能由导入成功推导 |

不修改 [静态替换](../runtime_components/STATIC_ASSETS.zh-CN.md) 的单网格标量材质契约。单网格与多节点资源使用不同的输入格式，不能直接互换。源文件不得被输出覆盖，目标资源目录须为新目录；已有游戏不会自动升级。

## 冻结与检查

在源码根或安装后的 `game-preproduction/runtime` 执行。路径参数填写项目绝对路径。

```sh
python tools/static_scene.py prepare --source SOURCE.glb --output NEW_REVISION
python tools/static_scene.py prepare --source SOURCE.gltf --nodes 3 25 --output NEW_SUBSET
python tools/static_scene.py check NEW_REVISION
```

`--nodes` 使用活动场景的源节点索引，保留其子树及必要父节点；不按名字猜测。冻结包包含 `plan.json`、完整 `scene.glb` 和按唯一 mesh 拆分的 `meshes/*.glb`。计划保留源依赖哈希、选取范围、局部/世界矩阵、实测顶点范围和三角数。读取实际顶点/索引检查范围，不仅信任源 accessor 的 min/max。

先执行 `check`，再把整个新版本复制进目标工程。检查既不要求原始素材仍在原位置，也不会向原工程写入。改变文件或计划后应准备新版本。哈希用于识别改动，不是来源授权或数字签名。

## Godot

将本目录的 `godot/static_scene.gd` 按项目复制，冻结目录例如放到 `res://assets/revision01/`。在原生 Godot 导入脚本中：

```gdscript
var result = preload("res://static_scene.gd").prepare(
    "res://assets/revision01", "res://assets/native01.scn")
assert(result.ok, str(result))
```

适配器再核对冻结文件哈希，调用 GLTFDocument 生成真实场景，检查源节点、局部变换和父子关系，保存原生 PackedScene。使用 `.scn` 可压缩嵌入资源；之后正常 `load(...).instantiate()`。项目可以通过 `source_node_index` 元数据找到门轴，按自己的开门规则旋转；工具不提供固定的门玩法。Python 入口负责计划整体校验，不能略过前面的 `check`。

## Unreal 5.8

在启用 PythonScriptPlugin / EditorScriptingUtilities 的 UE 5.8 编辑器中，将当前 runtime 的 `tools` 和本目录 `unreal` 加入 Python 搜索路径：

```python
from static_scene_import import prepare, assemble
plan, meshes, readback = prepare(revision_path, "/Game/MyNewImport01")
root, nodes = assemble(plan, meshes, "MyImport01")
# 保存到调用方新建的关卡，不覆盖已有游戏地图。
unreal.get_editor_subsystem(unreal.LevelEditorSubsystem).save_current_level()
```

`prepare` 在新内容目录使用原生 glTF 导入器创建网格和材质，返回实际尺寸、材质参数、贴图绑定/色彩空间读回。每个源 mesh 只导入一次，其实例共享原生网格。`assemble` 用可编辑 Actor 附着关系保留空门轴和子节点，全部设为 Movable / NoCollision；项目后续自行选择静态优化和碰撞策略。异常组装只清理本次新建 Actor；导入中断的资源保留在新输出目录用于诊断，下次选新目录，不覆盖半成品。

glTF 为米制 Y-up。原生 UE 网格局部为 `(X,Z,Y)*100`，节点也以同一基变换；包装根额外 yaw +90，使场景对应 `(-Z,X,Y)*100`。不能再次手动对网格乘 100 或重复应用源 node transform。

## 验证和来源

导入后检查节点层级、门轴、材质和贴图，并在保存重开及目标运行包中复核。

原创数值夹具生成器在 `templates/static_scene/make_fixtures.py`；可调用 `create(new_directory, color_path, normal_path)` 生成几何并复制已有贴图。未提供贴图时使用单像素数值夹具，仅用于技术测试。测试代码为 `tests/test_static_scene.py`。工具包不附带 Clockhill / FPS 原始美术资源；项目资产继续通过现有 `asset_handoff` 登记，保留来源、依赖和真正使用方。

技术验证说明资源被正确消费，不表示已还原源引擎自定义材质、完成整张地图迁移或获得人工美术验收。
