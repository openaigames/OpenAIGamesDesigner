# 从空间数据生成图纸与检查

`scripts/spatial_drawings.py --input 当前.json --before 原方案.json --out 新目录`

`--before` 可省略。输出平面、立面/剖面 HTML，以及 JSON 问题列表和修改前后对照。输入是从设计或引擎导出的检查副本，游戏场景仍使用原有编辑方式。图纸类型由任务决定，不要求所有项目都有建筑立面或固定张数。

## 数据约定

顶层：`schema: spatial-drawings/1`、`revision`、`source`、`coordinate`、`unit`（m 或 cm）、`up: +Z`、`objects`。`boundary`、`routes`、`limits`、`views` 可选。

- `objects`：稳定 `id`、XY 简单多边形 `footprint`、`z_min`、`z_max`。支持凹多边形，拒绝自交与零面积。模型是竖直挤出的体块，任意倾斜曲面、洞穴和地形需要引擎或更适合的几何工具。
- `kind` 可注明 cover、stairs 或项目自己的类别。`blocks_routes` 默认 true；可通行地面/台阶应明确为 false。
- `wall_thickness` 是声明墙厚。若需要检查复杂墙体实际厚度，应从真实模型测量后导出，不以填写值冒充测量。
- `openings`：`id`、`edge`（占地边编号）、沿边的 `start/end`、`z_min/z_max`。检测是否越界；检查通行时必须把墙拆成门洞两侧与上方的实体多边形，本版不自动挖洞。
- stairs 另有 `risers`、`treads`、`run`，分别是踢面数、踏面数、水平总进深，不假定两种数量相同。
- `routes`：稳定 `id`、XY `centerline` 折线、净宽 `width`、本段通行高度范围 `z_min/z_max`。多层或变高路线分段记录。
- `boundary`：可选允许的平面边界。范围外的物体和完整宽度路线分别报告。

`limits` 按需填写 `min_wall_thickness`、`max_step_height`、`min_tread_depth`、`cover_height_range`，单位与文件一致。阈值来自项目玩家能力与建筑规格，不内置某类游戏尺寸。

视图示例：

```json
[
  {"id":"level_zero","type":"plan","height":1},
  {"id":"east_west","type":"elevation","axis":"X"},
  {"id":"cross_cut","type":"section","axis":"X","at":3}
]
```

plan 的 height 可省略以显示全部占地；平面 +Y 向上。elevation 沿指定轴显示水平距离、Z 显示高度，采用体块投影，不做遮挡消隐。section 在另一轴的 at 位置切开实体，显示真实相交区间。复杂屋顶、洞口表达和施工细节仍需专门图纸或建模工具，本工具不会虚构它们。

## 检查含义

路线检测覆盖整段净宽，以圆形连接与端帽扫过中心线；可发现中心线没碰到、两侧却被掩体挤占的情况。它比较路线与声明为阻挡的体块，也会检查高差分层避免误报高架物体。不能由此确认胶囊爬坡、导航、跳跃或实机视线通过。

修改前后保留同一对象 ID，报告新增、删除、占地与高差变化，以及问题是否仍在。建议修改没有用户确认时保留建议状态，不覆盖原方案。不同玩法可采用不同表达；工具不固定路线数、包点、建筑风格、地图形状或关卡规模。
