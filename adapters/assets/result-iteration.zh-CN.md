# 结果驱动的资产迭代

[English](result-iteration.md) | [简体中文](result-iteration.zh-CN.md)

把评审确认的问题转成下一轮输入调整，再按同一组要求比较结果。Agent 负责查看证据、判断原因和编写调整；工具负责保留原要求、编译实际输入、核对证据及记录进展。工具本身不会调用语言模型或执行生成。

本流程承接[输入准备](input-preparation.zh-CN.md)和[质量评审](quality-review.zh-CN.md)。需要 Python 3.10+ 与 Pillow。记录放在游戏项目中，每次使用新的输出目录。

## 选择下一步

| 动作 | 适用情况 | 输出 |
| --- | --- | --- |
| `regenerate` | 已确认缺陷可以通过模型支持的输入调整 | 固定的要求、参考、请求和预览 |
| `postprocess` | 更适合本地加工，例如修枢轴或减面 | 加工任务与可观察结果，不产生生成请求 |
| `collect_evidence` | 缺视图、尺度未知或判断置信度不足 | 补证任务，不猜测修正方向 |
| `accept` | 源资产评审通过 | 对应范围的接受记录 |
| `stop` | 不值得继续尝试 | 附理由的停止记录 |

接受不会自动选用资产版本、替换工程文件或标记引擎及游戏验收通过。加工与补证任务需要 Agent 使用相应工具落实，记录本身不代表已经执行。

## 准备调整

```sh
python tools/asset_iterate.py --project MyGame draft --report evidence/base-assessment/quality.json --output production/revision-draft
python tools/asset_iterate.py --project MyGame prepare --plan production/revision-decision.json --output production/revision
python tools/asset_iterate.py --project MyGame check --iteration production/revision/iteration.json
```

查看 `issues.json`，把草稿复制到决定文件路径，依据真实观察填写。草稿的评审项未完成，不能直接提交。每个目标问题都要对应具体调整或任务，说明原因与下一轮应看到的结果。

问题 ID 带命名空间，如 `criterion:opening`、`check:triangles`、`finding:...`。标准与量测必须复查原 ID。多视图疑点还必须关联已有的语义检查项：重复像素警告消失，不等于造型一致。

[计划格式](../../schemas/asset-iteration-plan.schema.json)和[示例](../../templates/asset_iteration/README.zh-CN.md)支持四种调整：

- `prompt`：在上一轮提示词后追加针对性指令，保留原始描述与所有要求定义。
- `reference`：新增或替换参考，明确职责、方向、实际观察及是否发送。新图复制进本轮；替换参考后，重新核查所有使用它的要求落实路径。
- `parameter`：按 key/value 修改服务支持的参数。已有模型和设置保持固定，除非通过支持的输入明确调整。
- `route`：调整已有要求的落实和检查方式，不能删除或降低要求。

查看 `preview.md` 与 `prepared/preview.md`，后者显示真正送给服务的内容。Tripo 图生模型路线不接收提示词时，只改文字会被拒绝，需要调整参考及对应路径，或改用其他方法。实际发送内容不变时，即使修改了说明也不会产生有效重试。语音的提示词调整不能改写原定台词。

## 生成并重新评审

通过既有工作流排队：

```sh
python tools/asset_workflow.py --project MyGame submit --provider tripo --request production/revision/prepared/request.json
```

排队不执行服务。真正生成仍沿用已有的单任务授权、任务恢复和防重复提交流程。请求与授权指纹包含本轮关系；基线绑定资产版本时，新结果登记会保留父版本和迭代来源。父版本关系不会隐式上传父版本图片。

对实际产物新建质量采集与评审。保持资产、用途、环境、标准、容差、延期要求和必需方向一致，绑定 `production/revision/prepared/preparation.json`。原有视图 ID 的集合与方向不变，可以增加补充视图。除了目标缺陷，还要复查原先通过的要求。

```sh
python tools/asset_iterate.py --project MyGame compare --iteration production/revision/iteration.json --report evidence/candidate-assessment/quality.json --output evidence/revision-comparison
python tools/asset_iterate.py --project MyGame check --comparison evidence/revision-comparison/comparison.json
python tools/asset_iterate.py --project MyGame draft --report evidence/candidate-assessment/quality.json --previous evidence/revision-comparison/comparison.json --output production/next-draft
```

手工加工或补证沿用原输入准备。保留源文件、渲染、参考、决定与报告；检查会追溯依赖，证据过期不能复用。哈希只能核对内容一致性，不能证明作者身份或评审者确实看过文件。

## 进展与停止

`comparison.json` 分别记录已解决和未解决项、量测是否接近合格区间、必需项退步、新失败及偏好项退步。总分上升不能掩盖原先通过的要求变成失败或未知。生成或加工后文件字节完全相同，不计为进步；补证可以在源文件不变时消除未知。

建议包括 `continue`、`collect_evidence`、`change_method`、`complete`、`stop`。默认最多三轮、连续两轮无进展停止；首轮可在八轮以内设置，后续必须关联上一次比较并保持策略。退步需要换方法；停止或完成的链不能继续发起生成。新策略需要明确建立新基线并说明原因，不能丢掉记录重置次数。

`complete` 只表示固定的源资产评审范围通过。性能、动作、碰撞和实际镜头可读性仍要在 Godot 或 Unreal 项目中另行验证。

退出码：0 表示草稿、就绪、接受、停止、完成或进步；1 表示补证/加工交接或仍需处理的比较；2 表示输入无效或证据过期。源码仓库的 `tests/scenarios/asset_iteration_audit.py` 提供离线命令行案例，其中的合成判断只验证流程，不代表生成服务的美术质量。
