# 模型、骨架与武器的测量工具

用于找出差异发生在生成、比例调整、蒙皮还是导入阶段。先选同一份目标骨架与实际模型，保存原件；输出到新目录。工具读取和测量，不自动修改骨架或承诺任意模型一键绑定。

## Blender 读取与采样

```text
blender --background --factory-startup --python-exit-code 1 --python scripts/blender_asset_probe.py -- --spec 测量配置.json --out 新目录
```

支持 `.blend` 与 `.fbx`，需在 Blender Python 中运行，使用 Blender 自带 NumPy。配置以 `schema: asset-probe/1` 开始，必填：

| 字段 | 含义 |
| --- | --- |
| source | 本地源文件绝对路径 |
| coordinate | 转换后坐标的说明，如项目约定的前、右、上方向与原点 |
| to_cm | Blender 世界坐标到该坐标的 4×4 矩阵；显式包含厘米换算。支持旋转、反射、平移与统一缩放 |
| rigs | `[{"id":"body","object":"实际骨架对象名"}]` |
| meshes | `[{"id":"body","object":"实际网格对象名","rig":"body","sections":[]}]` |
| frames | 可选 `[{"id":"sample_1","clip":"实际动作标识","frame":15,"actions":{"body":"已存在的 Action 名称"}}]` |
| views | 可选 `[{"camera":"文件中已有相机名","width":640,"height":640}]` |

不会根据骨名猜方向，也不自动重定向。省略 `actions` 时采样源场景原有动画；指定时使用文件里已存在且适用于目标骨架的 Action，并关闭该骨架的 NLA 叠加。报告记录实际 Action 名称。源动画关联是否正确仍须检查。渲染使用同一已有相机和指定帧，输出 Workbench PNG 作为轮廓/姿态对照，不作为最终材质效果。

输出 `snapshot.json` 包括源哈希、单位、骨骼父子关系、参考头尾和变换、网格范围/面数、有效变形骨权重、未绑定顶点、逐帧边长变化，以及相机变换。非变形顶点组不算蒙皮权重；“权重总和为一”不代表接触或变形美观。

### 手臂、手掌与手套截面

每个网格的 `sections` 可填：

```json
[{"id":"forearm","center_cm":[0,0,0],"normal":[0,0,1],"half_thickness_cm":0.5,"radius_cm":8,"join_tolerance_cm":0.0001}]
```

中心与法向由实际模型/关节测量给出，不照抄示例零点。测手臂等局部时指定 `radius_cm`，排除同一平面远处的躯干；半径应包住完整截面，穿过半径边界的轮廓会标为无法计算。工具在中间和两侧切面求三角面交线，闭合时计算截面积，再用三层截面积估算薄层体积。开放边缘、切线重合顶点或无法拼合的轮廓会返回空值；不能把缺失当作零体积。交叠的多个壳层可能重复计入，应先分离测量对象。变形体积变化还要结合正侧轮廓和实际动作观察。

## 调整前后与导出读回

```text
python scripts/asset_compare.py --before 前/snapshot.json --after 后/snapshot.json --limits 项目阈值.json --out 新报告.json
```

两份记录必须在同一坐标中，使用相同稳定 ID；源对象名字可以不同。导出后重新导入 FBX 再采一次，不用源场景冒充读回结果。阈值由项目指定：`joint_cm`、`axis_deg`、`weight_error`、`volume_ratio_min`、`volume_ratio_max`、`stretch_max`。这些是定位问题的阈值，不是美术合格线。

对照会报告缺骨、增骨、层级变化、骨位置与轴向差、尺寸比例、截面积/体积变化及异常拉伸。同样编号的帧必须对应同一动作和时间；两边有相机时还会核对相机。骨尾可能受导入器表示影响，出现差异先判断是否实际改变关节与蒙皮。截图不能替代完整播放。

## 武器适配记录

`scripts/weapon_fit.py --input 武器记录.json --out 新报告.json`

记录采用 `schema: weapon-fit/1`，`unit: cm`，`coordinate`、`space`（`weapon_local`、`world` 或 `component`）、`source` 必填。所有位置先转换到声明的同一空间，不能混用骨局部与组件位置。

- `bones`：实际存在的骨名列表。
- `points`：由项目命名的握点、枪口、瞄具与接触点，形如 `{"muzzle":{"position_cm":[0,0,0],"bone":"实际骨名"}}`。
- `required_points`：本次必需点名列表。点名和骨名均不预设。
- `targets`：可选目标位置与 `tolerance_cm`，用于新旧枪或设计/实测差值。
- `sight_line`：可选后、前瞄具的点名二元组，输出长度与方向。
- `parts`：`id`、`bounds_cm`（min/max）、`moving` 和 `bone`；弹匣及其他活动件需要有独立绑定依据。

可编辑 JSON 是测量与调校记录，不是另一套游戏配置。修改后通过项目已有配置/导入入口接入，再读回实际生效值。枪口轨迹、双手接触、弹匣交接和近墙遮挡仍要在游戏中复测。
