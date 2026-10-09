# 项目资产工作台

工作台保留资产库（`#assets`）、生成服务（`#services`）、生成任务（`#tasks`）三个页面。资产库按用途分类、文件类型、标签和候补／游戏应用范围筛选，归属依据实际文件位置和项目配置。旧 `#review`、`#production`、`#observation`、`#actions` 链接及对应 `--view` 参数转到资产库；不删除项目阶段、运行观察或历史检查记录，CLI 和数据接口继续可用。目录归属不代表实际绑定或品质通过。

`GET /api/assets` 返回每个资产的 location（candidate/game）、previewCopy，以及 characters 与 characterBindingError。派生预览不作为独立候补展示；选择已绑定的模型，在详情中用“展示动画”切换实际绑定动作，多个角色共用模型时可先选角色。绑定失效时显示原因，原文件仍可浏览。

资产库侧栏“素材方案”读取同一响应中的 fits 与 fit_errors，展示能力、需求覆盖、缺口、取舍、来源与版本是否过期。尚未下载的方案也可查看；本地成员可打开资产预览。方案由 `asset_library.py fit/fits` 维护，页面不新增登记或晋升步骤。

FBX 动作的“预览模型”先检查实际骨架名称、父子层级与有效蒙皮，仅提供结构匹配的模型；静态道具、不匹配骨架和无法解析的文件不进入列表。没有配套模型时继续播放原骨架。此选择只用于当前浏览会话，不写入游戏绑定。结构匹配不会补齐独立弹匣、武器附件或其他对象的同步动作；确认效果时须观察实际网格变形，时间轴运行不能作为完整动作预览的通过依据。

“资产生成模型配置”页分为 2D、3D、视频、音频四个区，每个模型卡片均提供对应平台的“获取密钥”入口。侧栏可直接跳到各区。3D 资产生成支持 Tripo AI、混元 3D；音频生成支持 ElevenLabs（音效、配乐、台词），仍沿用独立密钥和既有生成授权。

2D 资产生成接入 Seedream，视频生成接入 Seedance；两张卡片与 Tripo AI 使用同样的 logo、状态、密码输入及加密保存布局，使用 ByteDance Seed 官方原版标识。两者共用 `ARK_API_KEY`，在任一卡片保存、更新或移除，另一张同步反映配置状态；环境变量仍优先。

“生成任务 → 新建任务”支持 Seedream 文生单图／单张参考图改绘，以及 Seedance 文生视频／首帧生视频。可设置 Model ID、图像尺寸或视频时长、分辨率、比例、声音与水印；可选当前项目内参考图。保存任务后仍需逐次授权，由 Agent 执行，结果下载后在资产库预览。默认模型分别为 Seedream 5.0 Pro、Seedance 2.5，需在火山方舟账户开通。

选择参考图时显示缩略图；任务详情展示保存时的输入快照，可点击查看原图，并区分改绘参考图和视频首帧。生成使用同一份快照；原素材后续修改不会改变该任务的输入，快照自身变更则停止预览与提交。Tripo／混元的网页表单目前只提供文本生成，适配器接收的图生模型输入同样可在任务详情查看。参考图只是生成输入，不代表生成结果。

Seedream 与 Seedance 的密钥入口为 [方舟 API Key 管理](https://ark.volcengine.com/region:cn-beijing/apiKey)。这是账户网页，模型调用由适配器使用官方 API 地址完成。配置成功不代表真实账户权限、额度或生成质量已验证；完整支持范围、请求示例及同步图像／异步视频的恢复区别见 [Seedream 与 Seedance 接入](../../adapters/assets/ark-generation.md)。

## 资产分类标签

侧栏先选择资产范围，再筛选资产分类和用途标签。卡片与详情均显示文件主分类，音频细分和“含动画”作为补充标签；共享用途标签仍来自 Art Direction。分类不会改变文件格式、目录位置、绑定或验收。

自动分类只读；手动或 Agent 核对后的分类保存到 `.openaigame/asset-taxonomy.json`，记录当前文件 SHA-256。相同版本的已保存分类优先，内容变化或没有版本的旧记录显示“分类待核对”。唯一的同内容同扩展名移动候选可在详情核对后迁移；副本不自动继承。旧专题数据保留，但不再提供专题编辑控件。

`asset_audit.py --classify <category> --paths <项目相对路径...>` 与看板共用保存逻辑；`--audio-kind music|sfx|speech` 设置音频用途，`--reset-classification` 恢复自动分类。分类操作不要求创建 Art Direction。扫描结果的 `taxonomy.needsReview` / `missingRecords` 列出需核对记录，资产 `classification.version` 用于保存时校验；POST `/api/asset-classification` 的 `versions` 为路径到当前哈希的映射，版本过期返回 409。单文件移动核对可传 `previousPath`，服务器重新检查唯一对应和源文件已不存在后更新记录。

## 游戏内容根

项目可通过 `.asset-browser/catalog-config.json` 限定资产库的展示范围：`includePaths` 是可选的项目内文件路径列表，省略时显示所有符合扫描规则的文件，空列表表示不展示文件；`excludePrefixes` 排除指定子目录。筛选只影响展示与当前范围的清单检查，不移动或删除源文件，也不代表这些资产已经绑定或验证。版本组的主文件被筛掉时，仍显示符合筛选条件的配套文件。

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

模型预览提供动作列表、播放暂停、速度、时间轴和骨架显示。共享看板不提供动作取舍表单或独立动作检查页面。需要读取旧项目记录时，使用 [历史动作取舍接口](motion-review.md)。


## 版本历史与生成依据

同一交付物登记版本后，资产库以一张卡展示，保持原有范围、类别和筛选。详情的“版本历史与对比”可查看父版本、参考用途、真实文件、制作来源和选用记录，支持两版图片对比、旧版选用、归档及从任意版继续修改。多视图等配套文件随版本保留；角色设定、模型、动作等不同交付物分别建组。当前选用、最新生成和工程中的真实文件分别显示，点击选用不复制到 game、不修改引擎绑定。

“加入版本记录”将现有文件及明确选择的配套文件保存为独立副本；旧项目无须先批量迁移。版本库存放于 `.openaigame/asset-versions`，摘要校验失败的文件停止用于预览、选用和生成输入。归档保留文件，默认历史列表折叠已归档版本。对象与标签仍由美术记录维护，分类针对文件保存。

生成表单默认“内置生图”，由 Agent 使用当前可用的内置工具执行；页面本身不调用模型。可选择修改底稿、补充参考用途、修改说明及项目图片。关联的图像版本自动成为真实输入快照，数量与格式受当前适配器限制；服务不支持时明确报错，不静默丢参考。云端收费授权流程不变。

POST `/api/asset-versions` 支持 create / add / select / archive，使用 GET 返回的 revision 防止覆盖并发修改。`select` 必须有 reason，`archive` 接收 archived 布尔值；GET 包含不可变文件、参考复核提示及与原路径摘要匹配的游戏文件。文件访问仍要求会话、明确登记和完整性校验。CLI 格式见 [工具说明](../README.md#资产版本与内置工具结果)。

## 动作记录开发接口

`GET /api/action-runs` 列出当前项目记录，`GET /api/action-run?id=...` 读取事件、设定副本与检查结果，`GET /api/action-compare?a=...&b=...` 比较两份记录，`GET /api/action-video?id=...` 验证文件版本后播放已关联录像。`POST /api/action-import` 接收项目内 capture、可选 spec、title、video 与 video_zero_s；沿用当前会话、同源与 CSRF 校验。

相对间隔、轨道同步、固定时刻与不确定度由动作管线的同一分析工具计算。适配器、路径和数据说明见 [跨引擎动作记录](../../adapters/engines/action_timing/README.md)。独立工程没有安装动作管线时，只在此功能中显示缺失说明，其他看板页面仍可用。

保留的动作编辑协议可连接已登记的原生测试场景，隔离草案、确认应用版本、回传实际 Viewport 画面及运行事件。当前随包提供 Godot 桥接及可选 AnimationPlayer 使用方；当前看板不加载动作前端模块，客户端需自行实现；既有记录与适配器保留。协议、场景接口与能力边界见 [原生预览](../../adapters/engines/action_timing/PREVIEW.md)。

## 资产生产交接

asset_handoff.py apply 与共享生产入口共同写入 Art Direction 的文件映射及 art-lifecycle；check 按指定资产范围检查登记、接入或已记录的验证。用途标签仍来自同一入口，扫描不自动采用资产。接入与历史映射见 [资产生产登记与交付检查](../../skills/game-preproduction/references/asset-handoff.md)。
