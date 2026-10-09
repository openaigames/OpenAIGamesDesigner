# 材质、布景、画面对照与地图交接工具

按当前问题选用。已有风格、布局、素材范围和审批约定继续有效；局部修改无需重做概念图，也不增加一轮固定审批。工具不预设建筑类型、地图规模、玩家人数或美术风格。

以下命令在工具包根目录运行；安装版使用 `game-preproduction/runtime`。输出写入游戏项目的新目录，已有文件拒绝覆盖。普通使用者描述需求即可，参数和记录由执行制作的 Agent 整理。

## 1. 把已选外观转成制作依据

从当前概念和有效规范提取区域用途、表面类型、纹理实际尺度、颜色关系、粗糙度、旧化位置和光照条件。概念图里的阴影与受光颜色不能直接当作基础颜色贴图；概念中看不出的物理数值是制作选择，先在样板上验证。只有任务需要时增加近、中、远距离机位，距离按实际玩法决定。

优先在既有材质规格中补这些信息。需要检查时导出 `environment-materials/1` 副本：

- `revision`、`style`、`basis`：当前版本、已选风格及依据。
- `materials`：每项有稳定 `id`、`purpose`，可填 `tile_size_m`、`texels_per_m`、`roughness`、`metallic`，以及 `scale_basis`、`variation`、`wear`、`lighting_response`、`source_ids`。数值来自项目，不套通用的写实标准。
- `regions`：稳定 `id`、`materials` 的 ID 列表、`sample_views` 的已有机位 ID。风格相同的区域可以共享材质；变化应服从结构和用途，不随机换色。
- `sources`：稳定 `id`、`kind`、项目相对 `path`、实际 `consumer`，及由该文件控制的 `parameters` 名称列表。几何、UV、贴图、着色器、灯光按实际修改入口记录。

```sh
python tools/environment_workflow.py materials --project PROJECT --input 材质检查输入.json --out 新目录/材质报告.json
```

检查未绑定的区域材质、缺失来源、无效参数和同一使用对象的参数被多份来源控制。报告保存文件哈希。它不会把填写的粗糙度冒充引擎读回，也不会另建一套游戏配置。

在引擎中组合代表几何、材质和灯光。观察轮廓、尺度、接触阴影、反射和远近表现，按用户当前授权处理样板。确认适用后扩展同类制作；既有有效样板直接复用。

## 2. Blender 表面测量与贴图烘焙

使用 [Blender 配方](../../../adapters/processing/blender_environment.py)，在独立后台进程读取 `.blend`，原件不保存。请求字段：

```json
{
  "schema": "blender-environment/1",
  "operation": "audit",
  "source": "本机现有场景的绝对路径.blend",
  "meters_per_unit": 1,
  "coordinate": "来自项目的坐标说明",
  "objects": ["文件中真实对象名"],
  "surface_limits": {"min_texels_per_m": 256, "max_anisotropy": 4},
  "id_properties": ["项目已有对象编号属性"]
}
```

示例阈值不是默认品质标准。`objects` 省略时检查当前场景对象，包含隐藏对象；需要只检查某区域时提供明确名单。`meters_per_unit` 必须按源文件实际尺度填写；`coordinate` 只描述坐标，不能用改文字代替坐标转换。

```sh
blender --background --factory-startup --python-exit-code 1 --python adapters/processing/blender_environment.py -- --request 检查请求.json --out 新测量目录
```

输出每个对象的求值后三角面、实际世界尺寸、面积、材质图片尺寸/色彩空间/依赖，以及按表面积加权的纹理密度分布和方向拉伸。密度单位是每米像素；考虑对象缩放及支持的 UV Mapping 变换。有效图片分辨率只是采样分辨率，放大源图不会补出原始细节。

支持默认 UV、UV Map、Texture Coordinate 的 UV 输出、固定 POINT/VECTOR Mapping 链。世界坐标、节点组、动态映射和 UDIM 密度返回未测及原因。报告不武断判定 UV 重叠错误，镜像、平铺和 trim sheet 可能有意重叠。程序纹理、生成图与扫描纹理的来源分别记录；不能由分辨率推导真实感。

同一配方的 `operation: bake` 支持一个明确网格：

- 必须有有效活动 UV，并明确 `uv_layout_reviewed: true`，表示已检查覆盖和重叠。
- `channels` 选 `base_color`、`roughness`、`metallic`、`normal`；`resolution`、`samples`、`margin` 按目标填写。
- 当前支持直接连接输出的 Principled BSDF；复杂混合材质需专门处理，不能静默烘错。
- 颜色经无光照的发光通道烘焙；数据图为 Non-Color，法线为切线空间 OpenGL +Y。它烘焙现有表面，不生成高模细节，不自动重做 UV，也不修改原材质。
- 结果必须放回目标引擎看接缝、法线方向、反射和实际镜头。UE、Godot 或网页材质的通道约定由实际接入方确认。

## 3. 建筑用途和布景检查

入口、封闭门、家具、装饰分别保留用途。开启比例由建筑用途决定；不默认半数门开启。可见门扇与实际洞口需要相符，不能展示开门却保留不可通行的实墙。

`environment-placement/1` 输入包含：

- `spatial`：已有 [空间图纸数据](../../game-level-design/references/spatial-drawing-tools.md)，复用同一对象和路线编号。
- `measured_objects` 可选：`objects` 为 Blender 测量中的对象名，`purpose` 说明用途，`blocks_routes` 明确是否参与阻挡检查。通过 `--measurements` 直接使用实测边界，禁止靠填写尺寸冒充测量。
- `clearances` 可选：`id`、`purpose`、`footprint`、`z_min/z_max` 和可选 `ignore` 对象 ID；用于入口净空、操作空间或其他项目需要的空区。
- `doors` 可选：`id`、`purpose`（entrance/sealed/decoration）、`hinge` XY、`width`、`thickness`、`closed_yaw_deg`、相对关闭姿态的 `angle_deg`、`z_min/z_max`。入口关联 `clearance_id` 和实际空间 `connection`。`check_travel: true` 检查开合过程，否则仅检查当前姿态。双开门分别记录两扇。

```sh
python tools/environment_workflow.py placement --input 布景输入.json --measurements 测量目录/report.json --out 新布景报告.json
```

量测使用米制 +Z 向上数据，需与空间记录坐标一致。对象包围盒和门扇扫过区域是保守代理，会产生待复核候选；真实曲面、台阶、穿行和开门逻辑仍由引擎检查。门洞墙体要拆成两侧及顶部实体；整栋房子的包围盒不能用于判断内部可通行。`ignore` 只接受已存在对象，不为消除失败随意排除家具或碰撞。

## 4. 固定机位与前后对照

保存 `environment-views/1`：`revision`、`engine`、`scene`、`coordinate`、`unit`（m/cm）、`rotation_order`、`resolution`、`conditions`、`dependencies` 和 `views`。机位项包含 `id`、`position`、`rotation_deg`，透视使用 `fov_deg`，正交使用 `projection: orthographic` 和 `ortho_size`。机位 ID 只用字母数字、下划线和连字符。

`conditions` 放实际需要比较的曝光、画质、时间、灯光版本等条件；请求值与运行读回分别保留。需要改变光照时允许改变，报告列出差异，不为追求“同条件”抹掉当前任务修改。`dependencies` 为真正影响画面的项目相对文件。只重拍受影响机位；新增机位不伪装成已有对照。

已有工程采集器可以直接接入：

```json
{"argv":["本机Python绝对路径","项目已有采集入口.py","--plan","{plan}","--output","{output}"],"timeout_s":300}
```

工具以参数数组运行已有采集入口，不建常驻服务；`{project}` 可用于工程路径。采集器负责应用机位、等待画面稳定、返回实际 PNG 和同名 JSON。JSON 使用 `environment-view/1`，包含同一上下文、真实相机参数、`resolution`、`conditions`、`source`；不得直接复制请求参数充当实测。相机姿态必须来自实际渲染相机，未知条件保留缺失提示。

```sh
python tools/environment_workflow.py capture --project PROJECT --input 机位计划.json --runner 既有采集入口.json --out 新采集目录
python tools/environment_workflow.py record-views --project PROJECT --input 机位计划.json --captures 已有真实采集目录 --out 新采集报告.json
python tools/environment_workflow.py compare-views --before 修改前报告.json --after 修改后报告.json --out 新对照目录
```

采集保存依赖前后哈希、执行日志和真实相机差值；输出目录不覆盖。对照页复制原图，可离线查看。报告会列出机位、曝光等条件变化，图片改变或上下文不一致会被检出；不以像素差自动认定美术通过。历史截图标明原采集时间，登记旧截图不算当前任务重新运行。

Blender 配方另支持 `operation: capture`，`plan` 指向上述机位计划；仅接受 Blender 米制、XYZ 欧拉角，读取场景本身的灯光与曝光。UE/Unity/Godot/网页项目沿用各自现有引擎或浏览器采集器并输出相同记录。提供共享协议不等于已实现每个引擎的原生采集插件。

## 5. 修改来源与参数

用第 1 节 `sources` 记录实际修改入口：模型/UV 在 DCC，基础图片在资产目录，引擎着色器和灯光在各自配置或场景。项目可采用其他分工，关键是同一实际参数有明确主来源。

发现数值散落在脚本中时，在项目授权内收拢到现有配置入口，使用项目引擎 API 读回生效值；工具包不把概念参数直接写入所有引擎。引擎特有轴向、文字镜像和材质补偿优先放入导出副本，避免污染可编辑源。旧修正已经进入源模型时，应明确记录并在转换前逐项核对，不能自动全场景反转。

## 6. 当前版本的跨引擎交接

从既有版本记录中取得当前选用源、依赖和实际工程引用。交接请求是当前任务导出副本，继续使用 [资产生产登记](../../game-preproduction/references/asset-handoff.md)，不另建长期维护的地图清单。

`environment-handoff/1`：`revision`、`selection_source`（项目相对权威记录）、`selection_sha256`、`coordinate`、`unit`、`target_engine`、`files`。文件项为 `id`、项目相对 `path`、当前 `sha256`、`role`、`transfer`，可附 `depends_on` 和 `note`。

- `portable`：该文件作为目标通用输入；仍须目标引擎验证。
- `rebuild`：需要重建，必须说明原因，例如引擎专用 shader、GI 或碰撞。
- `reference`：查看或校核用，例如概念、原引擎截图和脚本。
- `unknown`：尚未确定如何迁移。

```sh
python tools/environment_workflow.py handoff --project PROJECT --input 交接请求.json --out 新交接报告.json
python tools/environment_workflow.py handoff --project PROJECT --input 交接请求.json --package --out 新交接目录
```

选用记录或文件改变就拒绝沿用旧请求。打包保留相对结构、哈希、处理说明；glTF/GLB 外部图片和 buffer 自动检查并包含，远程依赖与越界路径拒绝。其他格式的依赖由已有资产清单和实际导出报告提供。交接不接触密钥，也不覆盖接收工程。

Blender `operation: export` 将明确选择的静态场景导出 GLB，再重新导入测量；保留对象、UV、标准材质和自定义属性。原件保持不变，动画/骨架使用专门导出流程。节点材质能否转换由 glTF 支持范围决定；复杂程序材质先烘焙或在目标引擎重建，不能宣称 UE HLSL 和最终光照已随 GLB 完整迁移。

目标引擎接入后另存实际读回，核对单位、朝向、包围范围、材质依赖、碰撞和固定视点，再执行需要的通行与性能测试。打包完成不自动标记这些检查通过。
