# 规格驱动的静态模型与小型场景

[English](PROCEDURAL.md) | [简体中文](PROCEDURAL.zh-CN.md)

`procedural` 是本地确定性生成器，不调用收费服务，不要求 Blender。它补充既有 Blender 转换、拼合与减面入口，不替代角色制作、布料适配或完整 DCC。

## 能生成什么

部件规格支持 box、ramp、cylinder，米制尺寸、颜色、碰撞标记、平移父子关系、包围盒表面依附和镜像。`parent` 引用部件 ID；`attach: "+y"` 把部件底面贴到父部件包围盒顶面；`position` 是额外平移。镜像以场景原点的 x/y/z 平面为基准。父子关系只传递平移，尚无旋转、布尔运算、关节或机械约束求解。

示例：[部件规格](../../templates/procedural/parts.json)包含地面、墙、坡道、平台及带顶盖的对称柱体。修改柱体高度后，依附顶盖随高度移动。检查器拒绝循环／缺失父引用、重复 ID、非有限坐标、过小尺寸、退化面、超出面数预算及镜像命名冲突；面朝向和镜像法线另有几何测试。

[地形规格](../../templates/procedural/terrain.json)支持 flat、hills、basin、canyon 高度场、沿 Z 轴的直路压平、矩形平台／净空区、带间隙和坡度上限的固定种子散布。道路边缘用一个网格单元过渡。无法放下要求数量时失败并说明已找到的数量，不静默减少。此地形模式仍没有曲路压平、河流侵蚀或生态系统；新增 scene 模式单独提供模块房间、连接端口和曲线路面，并交给双引擎导航验证。

生成器将道路与平台边界加入网格，避免粗网格漏掉窄路。平坦内部优先于其他区域的过渡带；内部实际重叠时，后定义区域优先，道路排在净空区之后。`cells` 是基础分辨率，边界细分可能增加实际面数，仍受面数预算约束。

散布高度和 `max_slope` 读取最终三角面；坡度表示水平距离每米的高度变化，即坡角的正切，0.5 约为 26.6 度。坡度检查点与高度贴合点均为物体底面中心，不保证整个平底物体在斜坡上无缝贴地，不替代导航或完整接地验收。

## 生成和记录

独立生成到一个新目录：

```powershell
python tools/procedural_assets.py build --spec templates/procedural/parts.json --output C:/Trials/Generated/v1
```

输出 `scene.glb`、`scene.json`、`spec.json`、`validation.json`。GLB 可进入现有资产浏览、导入和 Blender 工作流；场景 JSON 供 Godot／UE 原生加载器使用。输出目录必须为空，避免覆盖旧版本。

需要任务、版本和交接记录时使用已有资产入口。请求的 `parameters.spec` 放入同一规格对象，`inputs` 为空：

```json
{"parameters":{"spec":{"schema_version":1,"kind":"parts","parts":[{"id":"crate","size":[1,1,1]}]}},"inputs":[]}
```

将请求保存到项目内 `request.json`，再运行：

```powershell
python tools/asset_workflow.py --project C:/Games/MyGame submit --provider procedural --request request.json
python tools/asset_workflow.py --project C:/Games/MyGame run --job 返回的任务ID
```

该 provider 默认使用本地 Python，无需密钥；四个配套文件登记为同一资产版本，规格冻结在任务请求中，自动登记沿用既有 handoff。结构检查通过不等于目标引擎已导入，也不等于视听品质已验收。后续选择、应用和验收仍沿资产版本与交接流程记录。

## 保留手工修改的再次生成

先生成新版本，再合并原基线、新生成和人工修改过的 `scene.json`：

```powershell
python tools/procedural_assets.py merge --baseline C:/Trials/v1/scene.json --generated C:/Trials/v2/scene.json --current C:/Trials/edited/scene.json --output C:/Trials/merged
```

合并按稳定对象 ID 比较整个对象。只改过生成侧的对象采用新结果；只改过人工侧的对象保留；两侧改成相同内容也可以合并；不同修改、删除与修改冲突会列出 ID 并停止，输出不覆盖现有目录。合并结果保存三份输入的指纹，不再标成某一份单独规格的完整产物。该保护不识别 Blender／引擎场景里尚未回写 JSON 的修改。

两引擎的使用方式和可运行案例见[可选运行组件](../engines/runtime_components/README.zh-CN.md)。

## 模块场景

`kind: scene` 支持房间净尺寸、端口、三次曲线路径和角色净空／坡度分析，沿用上述四文件和资产任务入口。完整字段、双引擎运行及边界见 [SCENE.md](../engines/runtime_components/SCENE.zh-CN.md)。JSON 三方合并后删除旧 navigation 和 spec_sha256，避免沿用修改前的通行结论。
