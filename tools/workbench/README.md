# 项目素材看板

`#review` 按实际文件位置和项目配置呈现候补素材、游戏应用两栏。文件可直接浏览；旧检查记录保留，兼容 API 供历史工具使用。目录归属不代表实际绑定或品质通过。

`GET /api/assets` 返回每个资产的 location（candidate/game）、previewCopy，以及 characters 与 characterBindingError。派生预览不作为独立候补展示；角色模型与绑定动作在看板合并为角色卡片，其余文件按类型浏览。角色详情用“展示动画”切换实际绑定动作。

## 游戏内容根

归属由 `tools/content_roots.py` 统一计算，读取项目 `.openaigame/project.json`。保留已有 `engine_root` 和引擎配置，不为使用看板移动原工程。

| 配置情况 | 默认游戏内容范围 |
| --- | --- |
| 未建立项目配置 | 项目根的 `game/`，按完整目录段匹配 |
| Unreal | `engine_root/Content` 及工程插件中的 Content |
| Unity | `engine_root/Assets` |
| Godot / Three.js / Phaser | `engine_root` |

显式 `content_roots` 覆盖上述默认范围；目录必须位于已配置的引擎根内。`asset_exclude_roots` 排除辅助目录。两者使用相对游戏项目根的路径，例如在现有 UE 配置中合并以下字段：

```json
{
  "engine": "unreal",
  "engine_root": "UEProject",
  "content_roots": ["UEProject/Content", "UEProject/Plugins/Combat/Content"],
  "asset_exclude_roots": ["UEProject/Content/SourceReferences"]
}
```

示例仅展示归属字段；保留项目已有的版本、编辑器和运行配置。扫描仍过滤构建缓存、派生预览及约定的项目记录目录，不把它们作为游戏源资产。配置无效时报告原因并停止推断游戏归属，不静默退回默认目录。支持格式且位于游戏内容根之外的普通素材归为候补。

## 角色绑定清单

项目 `.asset-browser/characters.json` 示例（SHA-256 必须为实际值）：

```json
{
  "version": 1,
  "characters": [{
    "id": "player", "title": "主角", "role": "player",
    "model": "game/Content/Hero.uasset",
    "actions": [{"label": "长剑连击", "path": "game/Content/Attack.uasset"}]
  }],
  "dependencies": {
    "game/Content/Hero.uasset": "模型文件的SHA256",
    "game/Content/Attack.uasset": "动作文件的SHA256",
    "game/Content/CharacterConfig.uasset": "绑定配置的SHA256"
  },
  "evidence": "从实际引擎角色配置读取"
}
```

从工程真实绑定导出清单，不能由同目录或文件名推测。所有模型、动作须属于配置的游戏内容根并覆盖哈希；依赖变化、丢失或非法路径会停止绑定展示并报告原因。支持多个角色共享模型。绑定清单仅描述工程事实，不负责导入或改写游戏。

UE 预览映射 `.asset-browser/previews.json` 沿用 version 1，path 现在允许独立 GLB 或二进制 FBX，source_sha256、sha256、dependencies 仍按原规则验证。角色动作预览必须含网格，以便切换动画时继续显示人物。FBX 内嵌动画和源骨架使用已随包提供的 FBXLoader，纯动作候补仍支持会话中的同骨架人物预览。

## 历史接口（不再作为当前页面流程）

记录在项目 `.openaigame/asset-review/registry.json`，schemaVersion 为 1。GET `/api/asset-review` 返回记录、计算后的 effectiveStage、检查失效状态与 revision。POST 同一路径接收 revision 和 action，支持 create、edit、start、check、qualify、return、new_version、archive；需要原工作台的 session cookie、同源 Origin 和 CSRF token。

本地自动化也可将 `tools/` 加入 Python 模块路径，调用 `workbench.asset_review.load(root)` / `mutate(root, request)`，沿用文件锁、版本校验与原子写入。不要直接写 JSON 阶段。接口实现见 [asset_review.py](asset_review.py)。

每条记录针对一个用途 / 片段和一个版本。files 首项是预览主体，其余包含相关源、派生和依赖文件，均为项目相对路径。sourceUrl 可以单独建立候选；start 需要文件、use、testPlan、environment。角色职责 role 与 Art Direction 的 objectId 分开，标签仍由美术清单维护。

check 的 gate 为 source/external/engine/game，status 为 pass/fail/blocked/na，填写 method、reviewer、conclusion、evidence。证据格式为 `[{"path":"reports/review.md","type":"run_report"}]`，可用类型 report/run_report/video/image/license。通过需真实证据；动态素材的引擎/游戏检查需要 video 或 run_report。只有 external 允许说明不适用。运行报告必须描述实际观察，测试断言通过不能替代视觉与手感结论。

qualify 只在当前版本四项适用检查通过、证据与依赖哈希有效、无 issues 时成功。合格不代表已绑定。实际引用仍从 `.asset-browser/usage.json` 核对，不能用审核记录替代引擎引用清单。刷新发现变化会让 effectiveStage 显示 testing；已记录的历史版本保留。

new_version 需要不同 version 名称，清空检查，从候选重新开始，supersedes 和 lineageId 关联历史。archive 必须说明原因，可恢复。return 也需要原因并清空当前有效检查，操作历史保留。并发 409 时重新读入核对，不能以自动重试覆盖用户修改。

方案目前通过 plan 字段、用途说明和规格链接关联；不提供自动组合依赖图、批量晋升、下载器、动画编辑或引擎执行器。项目内的合格记录是执行者提供的验收结论，程序不会自动判定艺术质量。

片段选择、FBX 观测、角色上下文、schema 迁移与导出接口见 [动作取舍](motion-review.md)。
