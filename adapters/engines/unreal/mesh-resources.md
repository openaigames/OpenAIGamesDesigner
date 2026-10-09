# 静态网格审计、自动 LOD 与 Nanite

复用 [制作会话](../sessions.md) 的工程身份、检查点、日志及恢复。支持 UE 原生 StaticMesh，编辑功能只生成新 `/Game/` 资产，不替换场景或源模型。实现为 [mesh_contract.py](mesh_contract.py) 和 [static_meshes.py](static_meshes.py)。

## 只读审计

[示例](examples/mesh-audit.json) 用 `mode: inspect` 和 `mesh_audit.paths` 选择最多 512 个资源包路径。路径不带 `.AssetName` 后缀。也可以指定顶层 `scene` 和 `mesh_audit.include_scene: true`，收集当前加载世界的静态网格组件。不会自动加载所有分区或运行游戏。

结果位于会话 `result.json` 的 `mesh_audit`：

- 每个网格各级 render triangles、顶点、sections、屏幕切换值、Nanite 设置、材质槽和碰撞。
- 材质的有效混合模式、双面属性、基础材质纹理及实例覆盖纹理尺寸。纹理依赖可能包含当前着色分支未使用项；不是驻留显存测量。
- 加载场景中的使用方、实例数量，以及相同网格/材质/移动性/阴影/碰撞设置的实例化候选。候选不证明可安全合并；交互与独立状态仍需检查。
- 可选 `warning_limits: {"triangles":50000,"material_slots":8,"texture_dimension":2048}` 仅是项目筛选示例；不传则不套通用数字。单 LOD 提示不把 Nanite 模型误判为缺失 LOD。

Nanite 模型的普通 LOD 三角面明确标为 fallback render data；Nanite source triangles 保留未知。与 DCC 原始数据、每帧可见几何分别报告。可选字段不可读取时返回 `null` 和具体 `unavailable_fields`，不填零。

## 派生配置

[配置示例](examples/mesh-configure.json) 使用 `mode: edit`，每项 `static_mesh_configure` 必须给出 `source`、未存在的 `path`、`asset_role` 与 `strategy`。角色允许 building/prop/foliage/ground。一个请求可放多个明确操作；不是原子事务，批次失败查看 `completed` 及目标目录后继续。

**传统 LOD**：`strategy: lod`，`lods` 列出 2–8 级，包括保留全部几何的 LOD0。各级 `percent_triangles`、`screen_size` 在 0–1 范围严格递减（面数比例必须大于零），LOD0 两者均为 1。用 UE StaticMeshEditorSubsystem 自动减面，关闭派生副本的 Nanite。比例为请求目标，实际三角面读回为准；已有手工 LOD 仅在派生副本上被替换。

**Nanite**：`strategy: nanite`，明确 `platform_supports_nanite: true`。这项声明来自项目平台选择，工具不替用户认证硬件。检查材质为 Opaque/Masked；可选 `nanite`：

- `preserve_area`：默认 foliage 为 true，其余 false；只允许植物启用。
- `keep_percent_triangles`：0–1 且大于零，`trim_relative_error`：非负。
- `fallback_target`：auto / percent_triangles / relative_error。设置对应的 `fallback_percent_triangles` 或 `fallback_relative_error` 时必须指定匹配 target，避免保存了实际不生效的参数。

保留未指定的 Nanite 设置和已有传统 LOD；不会修改 RHI、引擎版本或共享材质。支持的混合模式不证明 WPO、风动、双面过绘制或目标设备性能已通过。其他引擎版本须重新进行原生测试。

若材质尚未声明 Nanite usage，结果给出 `nanite_material_usage_requires_render_check`；实际渲染检查后按项目材质流程处理。工具不会为网格配置请求自动改写共享材质。

可选 `lod_for_collision` 仅选择现有 LOD；不会生成或简化碰撞体。调整 fallback 或 collision LOD 会影响部分碰撞用途，须复测门洞、台阶和射击遮挡。

## 运行与验收

```powershell
python tools/engine_workflow.py execute --project "D:/Games/MyGame" --request "D:/Games/MyGame/requests/mesh-audit.json" --timeout 600
```

请求沿用现有配置。处理返回 `derived_asset_saved` 后，另起 inspect 会话读回派生路径，确认保存后的 LOD 数量、实际面数和设置。源资产在新会话前后应保持一致。再次写同一路径会被拒绝，失败副本保留供检查。技术测试和画面、帧时间验收分开记录。

本模块尚不执行：自动实例化/关卡换引用、贴图烘焙/缩图、HLOD、碰撞体生成或硬件性能采样。使用相应项目工具完成后分别保存证据。

实现依据：[UE 5.4 自动 LOD](https://dev.epicgames.com/documentation/en-us/unreal-engine/static-mesh-automatic-lod-generation-in-unreal-engine?application_version=5.4)、[UE 5.4 Nanite](https://dev.epicgames.com/documentation/en-us/unreal-engine/nanite-virtualized-geometry-in-unreal-engine?application_version=5.4)，以及本机 UE 5.4 StaticMeshEditorSubsystem 头文件。原生测试步骤见 `tests/fixtures/unreal-mesh-resources/README.md`（源码根或安装包 runtime 下）。
