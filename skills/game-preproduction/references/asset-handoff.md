# 资产生产登记与交付检查

适用于已授权的资产制作、获取、转换、换色、导入、替换及旧项目资产接手。登记由执行这些工作的 Agent 同步完成，不等用户打开看板后逐项补表；纯研究、选材讨论和只读扫描不写生产完成状态。

完整地图跨引擎移交可使用 [场景交接工具](../../game-environment-art/references/environment-tools.md#6-当前版本的跨引擎交接)，从这里的既有选用与文件记录生成带依赖的当前任务副本。打包结果回链到当前资产记录；目标引擎尚未运行时维持未验证，避免旧版交接说明被当成当前完整场景。

## 同一份权威记录

先读取 Art Direction 及其指向的既有资产清单。用途、稳定 ID、来源/许可依据沿用原记录；不把旧文档未采用看板表格格式当作没有登记，也不另起一套资产编号。自定义权威文档用项目 `.openaigame/workbench.json` 的 `art_document` 指定，例如 `{"art_document":"design/Assets.md"}`。选定入口后再做下述映射；已有多个清单时先明确各自职责，不能静默切换主源。

共享工具在这份文档中维护 `art-objects`、`art-assets` 文件映射和 `art-lifecycle` 生产记录。看板、制作任务和交付检查读取同一份文档。生命周期中的接入/验证状态是机器可查字段；表内“制作/导入状态”为其摘要，更新用共享工具，不单独手改摘要。原有方向文字、历史表格和规格保留；`legacyRef` 指回原条目，映射沿用旧 ID，只补文件对应关系和可核实事实，不复制维护第二套规格或许可正文。

一个文件对应一个文件 ID；多个文件可关联同一用途对象。包内模型、贴图、声音保留各自文件身份，来源依据可共用。多个逻辑表现由同一代码文件实现时合并记录并列使用方锚点，无需为每个实例建行。

## 生产过程中的职责

- 制作/获取方：记录已知用途、来源/许可状态、采用或候选依据，保存实际产物和版本；取得文件就同步登记，不把登记推迟到发布阶段。
- 转换/技术美术方：记录源文件与派生物，保留源资产身份。换色是新派生资产；同一文件原地修改沿用 ID、更新哈希，旧验证不沿用。
- 工程接入方：补实际使用方（场景、脚本、材质或配置）与导入/引用检查证据。程序资产填真实代码入口，并明确无需独立导入。引擎适配器没有自动接入登记的路径，由实施脚本在成功后调用本工具。
- 验证方：更新执行范围、结果和真实证据。动画、声音、视觉和性能不能因文件存在或运行成功而一并通过；检查失败也保存结果。
- 当前任务交付方：按实际修改、实际引用和引擎依赖核对范围；补上遗漏，再报告登记、接入、验证分别完成到哪里。不要把全项目工具代码、缓存、截图都当成当前任务待交付美术。

不要求用户再次提供已有记录中的信息。可以确定的事实直接维护；许可、用途或品质无法核实则明确待核实，不填猜测。未知许可可完成记录检查，但不能据此宣称允许发布；用途缺失则当前任务资产交接尚不完整。

## 自动登记的入口

`asset_workflow.py` 的 run/resume/register、`asset_versions.py` 的本地版本保存/record-native，以及 `asset_library.py` 的 acquire/from-job 已接入登记。只有实际成功输出才登记；失败保留已产生的文件及错误，不把候选自动改为工程采用。

生成/获取请求、record-native 请求可提供：

```json
{"art_record":{"object":{"id":"PLAYER","label":"玩家角色","tags":["主角"]},"source":"已有资源包记录或当前任务制作依据","license":"既有授权依据；未知时写待核实"}}
```

来源与用途由实际任务提供，不从提示词或文件名猜测。获取入口复用其正式来源和许可记录。没有上下文的旧调用仍登记文件事实并保留用途待补。重复执行登记保持 ID；已有记录不被自动候选信息覆盖。资产版本库保留方案与历史，生产记录保留文件接入事实，两者链接而不互相冒充。

生产成功、登记失败时，保留原成功状态并返回登记错误/非零退出码。修复权威文档或写锁后用 `asset_workflow.py --project PROJECT sync-records --job JOB_ID` 重做登记，不重新生成、不重新收费；获取入口重用已取得的文件，不重复下载。版本保存返回 `artRegistrationError` 时同样只修复登记，已经保存的版本仍存在。

## 导入、历史映射与验证更新

从 runtime 执行以下命令；manifest 是当前任务写入请求，不是另一份需要长期同步的资产清单。旧项目采用同一命令，沿用已有 ID 并填写 `legacyRef`。

```sh
python tools/asset_handoff.py --project PROJECT apply --manifest handoff.json
```

示例中的路径、哈希与证据必须替换为当前工程实际内容；缺证据不得照抄 passed：

```json
{
  "schema_version": 1,
  "objects": [{"id":"PLAYER","label":"玩家角色","tags":["主角"]}],
  "assets": [{
    "id":"PLAYER-MESH",
    "path":"game/assets/player.glb",
    "sha256":"当前文件的完整 SHA-256",
    "objectId":"PLAYER",
    "details": {
      "production":{"method":"converted","source":"现有角色源资产；来源详见原清单","license":"沿用原清单授权依据","evidence":["production/character-source.md"]},
      "derivedFrom":["source/player.blend"],
      "legacyRef":"design/Assets.md#player",
      "selection":{"state":"adopted","basis":"用户已选定的玩家角色"},
      "integration":{"state":"imported","consumers":["game/player.gd#build_body"],"evidence":["production/import-check.json"]},
      "verification":{"state":"partial","scope":"已检查行走；换弹握持待复核","evidence":["production/player-check.json"]}
    }
  }]
}
```

`production.method` 为 generated/acquired/authored/converted/procedural/existing；selection 为 candidate/adopted/replaced/unknown；integration 为 not_run/imported/procedural/failed；verification 为 not_run/passed/failed/partial。来源、许可状态和选用依据写实，不是隐含审批流程。使用方允许 `文件#函数或节点`；工具检查文件存在与版本，锚点及证据内容由执行方核对。

更新同一路径可省略 ID、对象和未修改的 details 部分；显式传入的部分整体替换，避免残留旧参数。文件哈希改变后，未重新提交的接入/验证记录自动失效。重复提交相同内容不新增记录。文件迁移用 `previousPath`，仅允许原文件已移走且内容/格式相同；转换或副本使用新 ID 与 `derivedFrom`。批次先全部校验再写；文档版本可通过 manifest.revision 进行乐观锁校验。共享写入使用项目锁并保留 `.openaigame/art-history` 文档备份。

生产证据和派生源记录历史哈希，后续来源变化产生提示；实际接入和验证依赖使用方/证据当前哈希，变化则要求复核。工具验证记录结构与版本，不能独立判断录像、声音或模型是否合格。

## 交付检查要绑定当前任务资产

在现有任务中保存实际资产路径范围，而不是只检查文档存在或行数。生成/转换输出、工程使用方实际引用、配套贴图/声音和程序资产均按当前任务范围核对；新生成文件遗漏不能靠一份不完整的手填列表掩盖。

范围格式：`{"paths":["game/assets/player.glb","game/player.gd"],"require":"integrated"}`。

- recorded：当前文件已登记，用途、来源/许可状态、制作与选用依据可追溯。候选制作任务可用这一层。
- integrated：还需明确采用及实际接入、使用方和当前证据。验证未完成可如实交付“已接入，待验证”。
- verified：还需指定范围的验证记录通过，且证据与使用方版本未变化。不能由通过此检查推导未检查的视听品质。

```sh
python tools/asset_handoff.py --project PROJECT check --scope scope.json
python tools/validate_records.py --project PROJECT --asset-scope scope.json
```

检查只读，有遗漏或失效时返回非零退出码，问题由当前执行任务补齐。纯扫描的“未登记”仍保留；不要隐藏提示或批量填“通过”来消除缺口。

使用结构化任务时，在资产制作/接入任务的 `asset_scope` 中保存上述范围；已存在的任务用 `asset-scope` 更新操作绑定，附当前任务范围理由。范围尚未确定时继续盘点，确定后在标记交付完成前绑定；局部追加/移除资产时同步修订。任务关闭会重新检查清单，遗漏不能关闭；关闭后文件或使用方变化会显示 needs_revalidation。已有不涉及资产的任务不受影响。未使用结构化任务的项目把同一范围与检查结果写入原有交付记录，不强制换任务体系。
