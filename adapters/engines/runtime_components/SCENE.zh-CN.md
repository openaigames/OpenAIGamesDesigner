# 场景生成与通行

[English](SCENE.md) | [简体中文](SCENE.zh-CN.md)

使用 `procedural_assets.py` 生成 `scene.json`／GLB，再接入原生导航组件。各游戏持有独立规格、生成文件、规则和组件副本。

## 创建与运行

```text
python tools/runtime_components.py create --engine godot --scenario scene --project NEW_PROJECT
python tools/runtime_components.py create --engine unreal --scenario scene --project NEW_PROJECT --ue-root UE_5.8_ROOT
python tools/runtime_validation.py --engine godot --project NEW_PROJECT --executable GODOT_EXE --visual
```

Godot 直接导入并运行。UE 5.8 先编译 OAGDExamplesEditor，再用编辑器 Python 执行工程的 `create_map.py`，保存生成网格、碰撞、材质和导航边界；之后运行 `/Game/Example`。`runtime_validation.py --engine unreal` 的 executable 使用 UnrealEditor-Cmd.exe。建图拒绝覆盖已有地图；编辑过的地图须显式迁移，或在新工程比较新规格。

案例按钮选择弯路、坡道、窄门、低门楣、断桥、陡坡和孤立房间，Run route 发起移动请求。它是通行检查灰盒，不是完整关卡或游戏菜单。项目脚本位于 `templates/runtime_scene/`。Godot 从 `generated/scene/scene.json` 构建原生三角网格碰撞；UE 从 `Content/generated/scene/scene.json` 保存 ProceduralMeshComponent，并在测试中逐顶点读回比较。两边复用同一个源文件，UE 坐标转换为 `(-Z,X,Y)*100`。

## 规格

可在 `runtime_components.py create` 追加 `--scene-spec YOUR_SPEC.json`，将该规格独立复制、生成并把角色尺寸写入该工程的 UE 导航配置。创建前完整检查规格，通行示例至少需要一个 query。直接制作无 query 的静态场景仍可使用 `procedural_assets.py build`。

`templates/procedural/scene.json` 是完整可编辑例子。用 `kind: scene`，schema_version 为 1。单位为米，Y 向上，源三角形逆时针。

| 字段 | 语义与约束 |
| --- | --- |
| agent | radius_m、height_m 为实际胶囊半径和总高；clearance_m、headroom_m 为导航余量；max_slope_degrees、max_step_m 为坡度和步高。角色高度须不小于直径 |
| rooms | 1–64 个开放顶、轴对齐房间；id 全局唯一；position 为室内地板中心；size 为室内宽、高、深。房间 XZ 占地不得重叠 |
| ports | 房间的门洞；全局唯一 id，side 为 east/west/north/south，width、height、offset 为净宽、高度及沿墙轴偏移；拒绝门洞重叠或跨墙角 |
| paths | 至多 128 条连接，from/to 指向两个不同房间的端口；一个端口最多接一条路径。width 为路面净宽，segments 为 4–128 段 |
| controls | 两个三次贝塞尔控制点；省略时用直线。两端的水平切线必须沿门洞向外法线；拒绝尖点、退化或宽度造成的局部折叠 |
| gap_segments | 可选缺失段编号，供断桥／未完成连接灰盒；它们不会生成碰撞面，也不会计为结构可达 |
| queries | 起终房间列表，生成房间中心测试点和结构连接预期。原生报告给出实际结果；预期不等于已经验证可达 |

路径采样成有厚度的三角网格，可随高度形成坡道。报告坡度以生成三角面为准。房间地板与路径端点在室内边界精确衔接，避免坡道被地板外伸截出小台阶。门楣与侧墙是真实碰撞，不靠标签阻止通行。

## 报告与修改

`procedural_assets.py build --spec SPEC --output NEW_DIRECTORY` 输出四个已有格式文件；资产任务入口仍可使用 `procedural` provider 和 `parameters.spec`，无需另建资产登记。`validation.json`／`scene.json.navigation` 包括角色参数、端口位置、路径长度、采样坡度、净宽／净高、失败原因和结构连通分组，native_status 为 not_run。

原生检查使用同一角色尺寸，Godot NavigationMesh 和 UE Recast 各自烘焙，再通过 组件查询。正例必须由碰撞移动器走到目标；反例检查起终房间都有导航表面，但没有完整路径。运行报告包含 spec_sha256、角色参数、查询路径、计时和实际轨迹。工程源文件另由交付驱动记录哈希；不能把规格哈希单独视为二进制或几何身份。

对象 ID 不依赖列表顺序；调整一条路径保持其他对象不变。同一规格重复生成保持文件内容一致。现有三方合并按稳定对象边界保留不冲突的本地修改，双方修改同一对象或删除冲突时拒绝。合并结果移除规格哈希和旧 navigation：几何变了就须重做通行验证。引擎／DCC 中尚未写回 scene.json 的修改不在 JSON 合并的观察范围内。

## 边界

结构报告只检查声明的端口、路径及其尺寸，不求解所有路径互相相交、穿过第三个房间或额外障碍产生的空间关系；原生烘焙与移动检查负责暴露这些差异。没有任意建筑设计、多层自动楼梯、开放世界流送、跳跃链接、动态地形重烘焙或导航避让。台阶字段约束烘焙，不代表 Godot 基础移动器具备任意台阶自动抬升能力；通行示例使用连续坡面。正式资产替换、材质和 LOD 见[静态资产](STATIC_ASSETS.zh-CN.md)。

示例默认胶囊半径 0.35m、高 1.8m，导航半径 0.5m、高 1.9m，坡度 35 度、步高 0.25m。可达性仅对应当次规格、引擎几何和移动参数。技术通过不能代替人工关卡体验或完整美术验收。
