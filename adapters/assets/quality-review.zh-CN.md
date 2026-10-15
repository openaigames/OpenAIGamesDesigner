# 资产证据与质量评审

[English](quality-review.md) | [简体中文](quality-review.zh-CN.md)

采集可复查证据、比较有尺度依据的视图，并依据预先定义的检查项记录 Agent 判断。结论绑定具体文件、参考和用途。源资产通过不代表引擎或游戏验收通过。

本流程接续[输入准备](input-preparation.zh-CN.md)，只处理本地文件，不提交生成任务、读取 API 密钥、替换资产或自动选用新版本。

## 运行条件

执行 `tools/asset_quality.py` 的 Python 需要 3.10+ 和 Pillow。图片支持单帧 PNG、JPEG、WebP，单张最多 1600 万像素、每次采集总计最多 6400 万像素，EXIF 方向需预先归一化。轮廓测量需要透明背景或明确的前景遮罩；不透明图片没有遮罩时保留未知。

模型采集还需要已安装、支持 `BLENDER_EEVEE_NEXT` 的 Blender，传入其绝对路径。仅直接采集自包含 GLB；外部缓冲、外部贴图及未支持的扩展会被拒绝。其他格式先通过已有[处理工具](../processing/README.zh-CN.md)转换，并保留依赖。

## 采集与评审

将[模型或图片计划](../../templates/asset_quality/README.zh-CN.md)复制到工程，修改路径、要求、用途和环境。项目路径使用正斜杠，不能越出项目；每次输出使用新目录。

```sh
python tools/asset_quality.py --project MyGame capture --model assets/door.glb --blender "C:/Tools/Blender/blender.exe" --front=-Y --units meters --output evidence/door-capture
python tools/asset_quality.py --project MyGame collect --plan production/door-quality.json --output evidence/door-review
python tools/asset_quality.py --project MyGame assess --evidence evidence/door-review/evidence.json --review production/door-review.json --output evidence/door-assessment
python tools/asset_quality.py --project MyGame check --report evidence/door-assessment/quality.json
```

`collect` 生成联系图、测量值、疑点和评审模板。既要看联系图，也要打开原图检查细节。将 `review-template.json` 复制到评审路径，填写实际评审者，查看证据后再替换未知项。采集不会自动填写美术判断。

`capture` 保存源模型副本，使用统一正交比例渲染正、右、背、左四面，记录相机、包围盒、求值后的顶点数与三角面数及 Blender 设置。左右以物体自身为准：右向量为前向量与上向量的叉积；上方是 GLB 导入后的 Blender +Z。`--front` 声明源模型朝向，工具不能推断角色脸朝哪里。`--units` 只标注测量坐标单位，不缩放几何，也不能证明原模型的真实物理尺寸；没有依据时保留 unknown。

渲染使用 EEVEE、AgX、固定光照、透明背景与动画第一帧，不验证变形、动画、引擎材质、碰撞或玩法。原始视图共用相机比例；联系图缩略图仅供浏览，所有计算使用原始像素。

## 证据计划

[计划格式](../../schemas/asset-evidence-plan.schema.json)包含：

- `asset_id`、`kind`、`use`、`environment`、`files`：源资产及用途；文件列表应包括复现所需依赖。
- `views`：图片 ID、路径、分组、方向、投影，以及可选遮罩、标定和关键点；`capture` 可加入 GLB 渲染视图与模型量测。
- `required_views`：每组必需方向；缺失视图保持待补，不能通过解释豁免。
- `checks`：图片测量、必需或偏好优先级、针对该资产设定的容差。
- `model_checks`：`triangles`、`vertices`、`meshes`、`size_x/y/z` 的最小/最大值；尺寸还需 `units`，单位缺失或不同保留未知。
- `criteria`：Agent 检查项，分为结构、风格、可读性、技术和多视图；评审前明确可观察的预期。
- 可选 `preparation`：输入准备的 ready `preparation.json`。每个必需要求都需以 `requirement` 关联必需检查项，或在 `deferred` 中注明后续 `engine` / `game` 检查及原因；后续项始终保留未验证状态。
- 可选 `version`：以 `{ "group": "VG…", "version": "V…" }` 固定已有资产版本；`files` 必须与整套版本快照一致。工作文件变化不影响未变化的历史快照，但快照文件或其元数据变化会使报告失效。
- 可选 `media`：本地音频、视频或报告的 ID、路径、类型；这里只绑定哈希，不自动解码、监听或评审这些媒体。

准备阶段参考关联冻结副本；采集还绑定当前计划、源文件、图片、遮罩、渲染元数据与联系图。任一关联文件改变都需重新采集；评审报告再绑定填写后的判断文件。哈希用于检查证据是否变化，不能证明评审者实际看过或听过。

## 多视图测量

| 测量项 | 条件和含义 |
| --- | --- |
| `height` | 根据每单位像素数换算后的相对高度差；容差为比例 |
| `baseline` | 轮廓底部相对共同地面的高度差；容差为标定单位 |
| `landmark_height` | 同名可见关键点的高度差；归一化坐标由评审者标注，不是自动识别 |
| `silhouette_iou` | 相同方向、画布、标定和对齐下的轮廓重叠率；容差是最低可接受重叠率 |

可比较图片应为相同姿态、同一坐标组的正交视图。使用相同 `calibration.group`、正的 `pixels_per_unit` 和以像素计的 `baseline_y`；组声明也意味着对齐可比。标定必须来自相机记录或实际参考尺度，不能把各自缩放后的图片虚构成同尺度。透视、无遮罩、轮廓出框或关键点遮挡时返回未知。

正面与侧面的轮廓本就不同，不能拿来通过同视角 IoU。不同方向存在完全重复或水平镜像像素时产生疑点；对称物体可以合理相同。评审者必须引用两个视图并解释对称依据，或确认缺陷。光照、姿态、接缝、左右手、身份和隐藏部位仍需看图。本工具不从图纸重建三维物体，也不证明所有图片一定描述同一造型。

## 判断与评分

[评审格式](../../schemas/asset-quality-review.schema.json)要求逐项记录预期、观察、置信度和证据 ID。可选局部标注使用图片内归一化的 `x`、`y`、`width`、`height`。

`pass` 对应 3–4 分，`fail` 对应 0–2 分，`unknown` 不评分。偏好项可用 `na`，但仍需证据和解释；必需项不能豁免。必需项低置信度通过仍按待确认处理。报告按维度显示均分及已评/总数，未知不算零分或通过。评分是结构化的评审声明，不是自动感知模型打分。

必需自动测量失败或确认多视图缺陷，外部结论即为 `fail`；必需证据不足为 `needs_review`，美观高分不能抵消这些问题。`pass` 仅限所列源资产用途，后续要求、引擎和游戏验收仍独立保留。

## 接入资产评审

需要修正失败结果时，使用[结果驱动迭代](result-iteration.zh-CN.md)，把确认的问题接到输入调整、把未知项接到补证，并按原标准比较后续结果。

在已有[资产评审流程](../../tools/workbench/README.zh-CN.md)建立相同源文件、用途和环境的 testing 记录，再执行：

```sh
python tools/asset_quality.py --project MyGame publish --report evidence/door-assessment/quality.json --record REVIEW_RECORD_ID
```

仅更新 external 源资产检查：pass 对应通过，fail 对应失败，needs_review 对应阻塞。不会自动纳入合格资产，也不会替代来源许可、引擎或游戏验收。评审台继续检查间接关联证据；参考、遮罩、渲染、判断或源文件变化后，旧通过状态自动失效。

命令退出码：采集/发布成功或报告通过为 0，评审失败/待确认 为 1，输入无效/证据过期为 2。`quality.json` 是机器可读结论，`report.md` 是阅读版；保留它们引用的项目文件。

从源码仓库可用 `python tests/scenarios/asset_quality_audit.py --output NEW_DIRECTORY` 复现合成案例。该脚本禁止 CLI 子进程网络连接，判断明确标注为测试夹具，不代表正式美术通过。源资产检查后继续使用对应工程工具完成引擎和实际用途验收。
