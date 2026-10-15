# 组合场景与工程接收

[English](RECEPTION.md) | [简体中文](RECEPTION.zh-CN.md)

将静态资产导入、灰盒替换、碰撞和回退放入可重建的 Godot / UE 5.8 工程，并提供文件交接核验。

## 接收普通工程

`scene_handoff.py` 使用已有 `environment.handoff` 打包器，保留权威选用记录、文件哈希和 glTF 图片/buffer 依赖检查。接收层声明引擎版本、入口和来源文件，并验证搬迁后的字节完整性。它不运行包内脚本，也不推断未声明的 native 资源依赖。

```json
{
  "id": "MySceneRevision",
  "files": ["RECEIVE.md", "scene.glb", "provenance/SELECTION.md"],
  "engines": {"godot": "4.7.2", "unreal": "5.8.2"},
  "entrypoints": {"instructions": "RECEIVE.md"},
  "provenance": ["provenance/SELECTION.md"]
}
```

`provenance` 第一项是项目权威选用记录。所有文件均为 project 相对路径，入口和来源必须在 files 中；GLB/glTF 外部依赖沿用原管线自动包含。需要的引擎插件、编译工具、私有资源许可和构建步骤必须由接收说明明确。

```sh
python tools/scene_handoff.py create --project AUTHOR --spec SPEC.json --output NEW_SNAPSHOT
python tools/scene_handoff.py check NEW_SNAPSHOT --pristine
python tools/scene_handoff.py receive NEW_SNAPSHOT --output NEW_RECEIVER
python tools/scene_handoff.py check NEW_RECEIVER
```

快照封口清单 `scene-handoff.json` 最后写入。文件缺失、损坏或多余文件会阻止 pristine 接收；已存在的输出目录一律拒绝，不能覆盖接收方修改。中断留下的目录保留用于诊断，修复存储问题后接收到全新目录。普通 check 允许引擎生成新的缓存/输出，但仍要求原输入字节不变；有意改源码之后应创建新修订，不能重写旧清单冒充未变化。

引擎可能在启动时补写原输入配置，导致运行后完整性检查报告差异。应记录实际差异并保留构建前快照；创建新的工程修订后再交接。

## 六组组合案例

[场景模板](../../../templates/static_scene/reception/RECEIVE.zh-CN.md)包含两扇不同位置/方向/缩放的门、保留灰盒碰撞的箱子、三角网格碰撞箱和两个建筑片段实例。移动路线连续经过两个门；测试门独立开关、重复资源实例、建筑墙体与外部通路。

```sh
python tools/scene_reception.py --revisions FROZEN_REVISIONS --provenance PROVENANCE --output NEW_CASE
python tools/scene_handoff.py create --project NEW_CASE --spec NEW_CASE/handoff-spec.json --output NEW_SNAPSHOT
```

这是一个有明确输入合同的接收案例，不是任意地图的自动布局生成器。`FROZEN_REVISIONS` 包含 box、door、clockhill 三个 冻结目录；box/door 使用 `make_fixtures.py` 的几何和层级，clockhill 使用原验证项目的 1、3、25 节点及坐标范围。其他资源应建立自己的布局/探针配置，不只改文件名来复用通过标准。`PROVENANCE` 包含 `SELECTION.md` 和引用的授权/来源记录；真实 FPS 美术不随工具包分发。

环境通过 `OAGD_ENGINE_CONFIG` 指向 JSON，提供 `godot` 可执行文件、`unreal` 安装目录、`godot_template` Windows 导出模板和 `ddc` 缓存位置。工程脚本只从接收目录读取输入、工具和原生资源。具体顺序见模板 RECEIVE.md；每次运行附不同 `--label`，报告写入 evidence。

## 故障与兼容

案例包含：真实冻结 GLB 损坏拒绝、复制中断/现有目录保护、Godot 后续组 staging 失败、保存失败后回退、UE staging 和隐藏目标中途异常、错误收据拒绝、新进程回退/重应用，以及故意错绑门碰撞的运行探测。失败恢复后重新走相同完整路线。

UE 基线/收据使用标记 `fingerprint_format: canonical-zero/1`。保存前后的 `-0.0` / `0.0` 统一，精度仍为 1e-5；实际变换、资源或碰撞改动仍拒绝。未带标记的旧基线/收据沿用旧指纹算法，不自动改写。若旧收据本来已遇到符号零差异，应保留旧基线并重新捕获/应用形成新修订；不绕过冲突强制删除现场。

文件核验、原生重建、独立包运行、技术画面核对和真人接收分别记录。此处的工程接收指从新目录重新生成原生资产、编译并运行；不是独立用户已试玩或认可，也不代表整张 Clockhill 地图内部导航和最终灯光达标。
