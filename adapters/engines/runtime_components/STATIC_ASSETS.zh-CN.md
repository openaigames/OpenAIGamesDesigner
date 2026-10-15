# 静态资产接入

[English](STATIC_ASSETS.md) | [简体中文](STATIC_ASSETS.zh-CN.md)

适用于 Godot 和 UE 5.8。项目选择资产、替换对象和碰撞策略，工具提供映射、派生资源、原生替换与回滚入口。

## 输入与边界

支持单个网格、单个节点、已应用变换的静态 GLB 2；最多 8 个不同名称的不透明、单面、无自发光的标量 PBR 材质。颜色、粗糙度、金属度按材质槽名称接入。纹理、透明／双面材质、扩展、骨骼、动画、多节点和非均匀缩放会明确拒绝。此工具不承诺任意现成美术资产都可直接接入。

校准门框是独立制作的本项目资产，源配方见 `templates/runtime_static/make_source.py`，已导出的 GLB 与来源记录在 `templates/runtime_static/assets/`。它用于验证门洞、材质与 LOD，不代表正式美术。默认示例替换三个入口：平地、坡道以及保留原灰盒碰撞的入口。

## 创建并运行示例

```powershell
python tools/runtime_components.py create --engine godot --scenario static --project C:/Trials/StaticGodot
python tools/runtime_components.py create --engine unreal --scenario static --project C:/Trials/StaticUE --ue-root D:/UE_5.8
```

Godot 先导入，再生成资源与保存场景，最后启动：

```powershell
Godot.exe --headless --editor --path C:/Trials/StaticGodot --quit
Godot.exe --headless --path C:/Trials/StaticGodot --script res://build_assets.gd
Godot.exe --path C:/Trials/StaticGodot
```

UE 先编译 `OAGDExamplesEditor Win64 Development`，再执行工程的 `create_map.py`，最后运行 `/Game/Example`。具体编译命令见[公共运行组件](README.zh-CN.md)。生成脚本拒绝覆盖已有地图和派生目录。失败生成的资源留在该次输出目录供检查；重新生成应选择新目录，不覆盖手工修改。

```powershell
python tools/runtime_validation.py --engine godot --project C:/Trials/StaticGodot --executable C:/Tools/Godot.exe --visual
python tools/runtime_validation.py --engine unreal --project C:/Trials/StaticUE --executable D:/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe --visual
```

Godot 验证入口会为尚未准备的新示例导入并生成原生资源。UE 验证入口要求先完成编译与建图。默认各 64 项检查：24 项替换资源检查和原来的 40 项场景通行检查。必须读 `failures`；UE 游戏进程的退出码可能仍为 0。

## 在自己的工程接入

先生成或选定 `scene.json` 基线。编写项目自己的清单，明确源文件哈希、基线哈希和稳定对象 ID。例如：

```json
{
  "schema": "oagd.static-assets/1",
  "scene_sha256": "实际 scene.json 的 SHA256",
  "assets": [{"id":"portal","source":"assets/portal.glb","sha256":"实际 GLB 的 SHA256"}],
  "replacements": [{
    "id":"entry_portal","targets":["entry_wall_left","entry_wall_right","entry_lintel"],
    "asset":"portal","position":[0,0,0],"yaw_degrees":0,"scale":1,"collision":"source_mesh"
  }]
}
```

```powershell
python tools/static_assets.py --project C:/Games/MyGame --scene generated/scene.json --manifest static-assets.json --output C:/Games/MyGame/revisions/static-r01
```

准备器完整检查后才创建新版本目录；拒绝源文件或基线变化、重复／缺失目标、越界路径和不支持的输入。目录保存源文件副本、原清单、基线、目标指纹以及派生配置。`static_assets.read_plan(folder)` 检查固定版本是否被改动；要改配置应准备新版本。

Godot 使用 `OAGDStaticAssets.prepare_asset` 生成 `.res`，`apply(plan, baseline, lookup, parent, asset_root)` 替换，`rollback(receipt)` 恢复本次操作。`lookup` 来自 `OAGDGeometry.load_scene`。UE 编辑器使用 `adapters/engines/unreal/static_replacement.py` 的 `prepare`、`apply`、`rollback`；依赖已有 `static_meshes.py`、`mesh_contract.py` 和项目的 OAGDCore 插件。应用前检查全部目标的原生位置、法线、颜色、索引和变换；Godot 顶点颜色按原生 8 位精度比较。映射须经准备器验证；低层函数不是任意 JSON 的通用解释器。

替换保留原灰盒实体和稳定 ID，隐藏其显示；新实体有自己的替换 ID。`source_mesh` 使用新网格 LOD0 的三角碰撞并停用旧碰撞；`retain_graybox` 只替换显示，保持旧碰撞。原对象没有删除。回滚收据用于当前引擎会话；跨会话恢复应打开保留的基线版本，此工具不自动合并引擎编辑器中的任意手工编辑。

## 原生处理与检查

Godot 通过 [ImporterMesh](https://docs.godotengine.org/en/stable/classes/class_importermesh.html) 生成自动 LOD，保存 ArrayMesh 和 PackedScene；读取原生表面、材质、LOD 索引与碰撞。glTF 颜色为线性值，Godot `albedo_color` 存储为 sRGB，验证时做对应转换。

UE 复用网格工具创建派生副本，关闭该副本的 Nanite，生成 100%／50%／20% 三档常规 LOD，阈值为 1／0.35／0.12。完整网格用作复杂静态碰撞，不能据此承诺动态刚体模拟。UE 5.8 命令行编辑器需显式加载 StaticMeshEditor 模块，等待网格构建后再读取阈值，并调用原生阈值 setter。源导入资源保持不变；其 Nanite fallback 三角数不能当作原始 GLB 三角数。

场景坐标为右手 Y 向上、米；UE 场景使用 `(-Z,X,Y)*100`。UE 原生 GLB 网格局部坐标为 `(X,Z,Y)*100`，替换 Actor 增加 90° yaw 以对齐场景，之后再应用项目 yaw。资源包围盒读回按网格导入坐标转换；场景位置、门洞和门柱碰撞另行核对。

材质、尺寸、LOD、碰撞和路线结果需在保存重开及运行包中重新检查。LOD 数据存在不等于远近切换无视觉瑕疵，也不证明性能改善。正式美术、材质外观跨引擎完全一致、帧率基准、人工试玩、任意平台、独立协作者接手均需另行验证。
