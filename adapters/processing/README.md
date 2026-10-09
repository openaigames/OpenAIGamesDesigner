# Blender 转换、静态资产拼合与减面

沿用 [资产任务](../assets/README.md) 的 submit/run/retry、输入快照和产物登记。配置本机 Blender 的绝对可执行路径；本处理器在 `--factory-startup --background --disable-autoexec` 的独立进程运行，不连接或清空用户打开的 Blender 场景。

## 操作边界

| operation | 输入与用途 | 输出 |
| --- | --- | --- |
| `convert`（默认） | 首个 GLB/glTF/FBX/OBJ 与其 sidecar；沿用原有导入/导出 | `processed.glb`、`processed.blend` 或两者 |
| `assemble` | 明确实例清单；每项以 inputs 索引引用主模型 | 独立可移动的父节点与导入层级，按指定布局拼合 |
| `optimize` | 首个静态主模型；显式 `decimate_ratio` | 应用 Decimate 后的副本及前后统计 |

拼合可选同一个全局 `decimate_ratio`；默认 1，不减面。范围为 `(0, 1]`，它是目标比例，不保证精确三角面数或视觉质量。拼合与减面拒绝骨架、对象动画、形态键及其他非 Mesh/Empty 对象。角色仍可用 convert 路线转换，但应另行检查骨架/动画；不能用静态减面接口处理角色蒙皮。

没有自动重拓扑、绑骨、布料、烘焙、纹理缩图、LOD、碰撞或导航生成。已有带手工调整的 `.blend` 不作为输入；需要这类工作时使用专门配方，不能将本接口解释为保留任意已有场景编辑。

已有可编辑场景另有 [blender_environment.py](blender_environment.py) 专门配方：只读表面/UV 测量、明确网格的标准材质烘焙、静态 GLB 导出读回及固定机位渲染。它读取 `.blend` 并输出新目录，不保存源场景。请求与限制见 [场景制作工具](../../skills/game-environment-art/references/environment-tools.md)；这些能力不改变上述 convert/assemble/optimize 的参数与边界。

此限制适用于本 Blender 处理器。UE 原生静态网格可使用 [网格资源接口](../engines/unreal/mesh-resources.md) 只读审计、自动生成多级 LOD 或配置 Nanite 派生副本；仍需重开读回与场景验证。

## 请求示例

假设以下两个文件已在游戏项目中，保存此 JSON 为该项目内的请求文件：

```json
{
  "inputs": ["assets-source/column.glb", "assets-source/wall.glb"],
  "parameters": {
    "operation": "assemble",
    "format": "both",
    "decimate_ratio": 0.65,
    "instances": [
      {"id": "column_north", "input": 0, "position": [2, 5, -0.4], "rotation_degrees": [0, 12, 35], "scale": [1, 1, 1]},
      {"id": "wall_west", "input": 1, "position": [-4, 3, -0.2], "rotation_degrees": [0, 0, 90], "scale": [0.8, 0.8, 0.8]},
      {"id": "column_broken", "input": 0, "position": [-2, 1, -0.7], "rotation_degrees": [65, 0, 15], "scale": [0.6, 0.6, 0.6]}
    ]
  }
}
```

使用现有命令 `python tools/asset_workflow.py --project "游戏项目路径" submit --provider blender --request "请求文件相对路径"`，再对返回 job ID 执行 run。请求中使用项目相对路径；工具生成不可变快照后，worker 才接收绝对 snapshot 路径。glTF/OBJ 的贴图、MTL、bin 等依赖同样加入 inputs，维持原有相对目录；不要把 sidecar 索引当成主模型。

每个实例的稳定 ID 只允许字母、数字、下划线和连字符，长度 1–80；每次 1–512 个实例。position 单位为米，使用 **Blender 右手 Z-up 坐标**；rotation_degrees 是 XYZ Euler 角度，scale 是三个正数，默认均为 1。所有数值必须有限。GLB 导出器负责转换为 glTF 的 Y-up；消费布局的引擎须明确坐标转换，不能原样把 Z-up 数组当 Y-up。

实例变换作用于保留导入层级的父节点，不把所有子网格挪到原点。镜像应在明确轴向的资产处理阶段制作，接口拒绝负缩放。重复素材可改变角度、大小和半埋深度；此接口执行明确布局，不随机替代美术设计。

## 源文件与证据

每次运行从干净场景重建，输出目录必须为空或尚不存在；旧产物不被覆盖。由实例 ID 创建父节点，导入对象加实例前缀，重新执行不会在上次场景上叠加。保存 blend 前打包可打包的贴图依赖；实际重开验证仍必需。

`processing-report.json` 随产物登记，记录 Blender 版本、所有输入（含 sidecar）哈希、实例布局、减面比例、各实例前后及整体网格/顶点/三角面/材质数量。它始终保留 `quality_validation: not_checked`。三角面数为实际网格统计，不能替代目标引擎的绘制次数、透明覆盖、纹理和帧时间测量。

## 验证

在源码仓库根运行 `python -B -m unittest discover -s tests -p test_blender_recipes.py -v`（完整维护测试不随运行包分发）。没有配置 Blender 时，只验证参数与失败边界；真实往返测试会显示 skipped。设置 `OAGD_BLENDER` 为本机绝对可执行路径后，运行同一命令会用自制临时模型执行拼合、减面、贴图打包、重开两种格式、布局/原件保持、重复运行和形态键保护检查。测试不读取真实游戏素材。

Blender 联调需设置 `OAGD_BLENDER` 为实际可执行文件，再运行 `python tools/run_tests.py`。记录所用 Blender 版本、输入、输出与原始日志；CI 没有 Blender 时不能把 skipped 写成实机通过。测试夹具的几何与依赖检查不构成美术验收，仍需在项目镜头、地形和目标运行环境中审阅实际资产。
