# 灰盒到多节点静态资产

[English](REPLACEMENT.md) | [简体中文](REPLACEMENT.zh-CN.md)

先用[静态场景导入](README.zh-CN.md)冻结并检查资源，再执行灰盒映射与替换。UE 新指纹规范化符号零，旧记录兼容语义见 [接收说明](RECEPTION.zh-CN.md)。两个引擎消费同一映射语义，各自捕获原生基线；原生基线不能跨引擎复用。项目坐标为右手 Y 向上、米，位置和偏航作用于资源外层根节点；资源自己的根变换仍然保留。

## 支持的对象

- Godot 4：场景根节点的直接 `MeshInstance3D` 子节点，用 `stable_id` 元数据标识；允许其无脚本碰撞子树。自定义脚本节点不进入本次灰盒事务。
- UE 5.8：未附着到其他 Actor 的原生 `StaticMeshActor`，恰好一个 `StaticMeshComponent`；用 `OAGD_ID_<ID>` Actor Tag 标识。蓝图、自定义组件和 ProceduralMeshActor 使用原有工程接口，不会自动转成受管灰盒。
- 资源是 已检查的静态 GLB/glTF 修订。服装、骨架/动画导入、运行时碎裂、任意着色器和整张地图迁移不属于此工具范围。

## 映射与碰撞

参考 [门替换配置](../../../templates/static_scene/replacement.example.json)。模板的 node 数字对应 `make_fixtures.py` 的门；项目资源需要使用自己的源节点索引，填入实际 `plan_id`。`targets` 可列多个灰盒，同一目标只允许属于一个组；目标不删除，只改变显示和碰撞状态。

| policy | 行为 | 用途 |
|---|---|---|
| `retain_graybox` | 隐藏原灰盒，保留其碰撞；新增资产无碰撞 | 已调好可玩尺度的装饰替换 |
| `source_mesh` + `nodes` | 显式选择固定网格三角形碰撞；禁用对应旧灰盒碰撞 | 固定建筑、地图片段、固定箱子 |
| `boxes` + `boxes` | 每个盒体以源节点局部坐标给出中心/完整尺寸，跟随该节点 | 门轴、门扇、规则部件 |

Godot 的 `source_mesh` 为静态凹面形状，UE 为独立复制网格的 ComplexAsSimple；不用于动态刚体或活动门扇。门扇使用 `boxes`，尺寸是米。原网格资产的碰撞配置不修改。保留旧灰盒碰撞时，视觉模型与旧碰撞尺寸可以不同，应由项目明确选择并做通行检查。

## 冻结事务

先用适配器的 `capture` 保存原生 baseline JSON，再执行：

```sh
python tools/scene_replacement.py prepare --project <project> --baseline baseline.json --manifest mapping.json --output <new-transaction-directory>
python tools/scene_replacement.py check <new-transaction-directory>
```

输入路径相对 project。输出必须是新目录，里面冻结 `plan.json` 和实际资源依赖；`check` 会核对计划指纹、节点表、资源计划和文件字节。原资源无需覆盖。

## Godot 使用

`godot/scene_replacement.gd` 与 `static_scene.gd` 放在同一目录。每个资源先按 `Importer.prepare` 生成原生 PackedScene。Python `check` 成功后才将计划交给原生适配器。

```gdscript
var baseline = Replacement.capture(scene_root, ["GrayDoor"])
# 保存 baseline，冻结计划并检查后加载 plan。
var result = Replacement.apply(scene_root, plan, {"door": load("res://native/door.scn")})
if result.ok:
    var packed = PackedScene.new()
    packed.pack(scene_root)
    ResourceSaver.save(packed, "res://revisions/applied.scn")
# 新进程加载 applied.scn 后仍可调用：
var rollback_result = Replacement.rollback(scene_root)
```

收据保存在场景根的 `oagd_replacement_receipt` 元数据中。保存时将导入层级转成当前场景拥有的节点，以保证新增碰撞节点按原路径重载。每个场景根同时只允许一个活动事务；成功回退后可再次应用。

## UE 5.8 使用

将 `tools` 和 `adapters/engines/static_scene/unreal` 加入编辑器 Python 路径。先保存灰盒及其网格、材质、纹理，再捕获基线。

```python
baseline = replacement.capture(['GrayDoor'])
# 保存 baseline 并执行上面的 prepare 后：
plan, resources = replacement.prepare_resources(transaction_directory, '/Game/Revisions/NewImport')
receipt = replacement.apply(plan, resources)
# 用 EditorLoadingAndSavingUtils.save_map 保存到新的地图修订；同时保存 receipt JSON。
# 新进程加载该地图，再读收据：
replacement.rollback(receipt)
```

资源目标目录必须全新。收据与地图是配套文件，未承诺跨文件系统崩溃的原子提交。原生资源状态包含物理 `.uasset` 文件及递归依赖指纹，读取前同步资源注册表；未保存资产编辑会拒绝捕获/回退。不要手工重写收据以绕过冲突。

## 通行检查与手工修改

Godot `Replacement.passage(world, start, finish, radius, height)` 在碰撞注册后的物理帧使用。UE 在运行中的世界中包含 `unreal/ScenePassage.h`，调用 `OAGDScene::Passage(World, Start, Finish, Radius, Height)`。两者使用竖直胶囊，检测起点重叠及整段扫掠；不是中心射线，也不自动生成导航网格或规划绕行路线。项目应分别检查关门、开门、门框、净高、建筑入口与外部通路。

应用前核对所有受管灰盒，回退前核对所有隐藏原物和新增层级；位置、层级、可见性、材质、几何或碰撞变化会阻止整笔操作。未受管对象可以继续修改。检查失败时应保留现场，决定保留手工修改、另建修订或恢复被修改的对象；不提供默认强制覆盖。

原生状态指纹对变换按 1e-5 引擎单位归一化，属于状态比较，不是完整工程版本控制。地图、脚本、全局光照或项目设置不在回退对象范围内。原生保存和操作报告仍应进入项目版本记录。
