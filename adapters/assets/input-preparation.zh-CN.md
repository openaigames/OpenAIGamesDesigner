# 资产要求与输入准备

[English](input-preparation.md) | [简体中文](input-preparation.zh-CN.md)

使用 [asset_prepare.py](../../tools/asset_prepare.py) 将资产要求整理成可核对的生成请求。工具读取本地文件、校验适配器、冻结参考文件并输出提交预览，不会联系生成服务、读取 API 密钥、授予付费权限或生成资产。

## 要求与输入方案

在[资产要求文件](../../schemas/asset-requirements.schema.json)中保留原始描述。每条要求包含稳定 ID、文字、类别（identity 身份与结构、appearance 外观、technical 技术条件）和优先级（must 必须保留、preference 偏好）。可选 attribute/value 字段检查同一明确属性的必选值冲突，不能识别任意自然语言矛盾。参考文件使用项目相对路径，分别标明造型、材质或风格等职责；3D 视图以物体自身方向为准。

Agent 根据所选服务编写[输入方案](../../schemas/asset-input-plan.schema.json)，保留用户选择，为每条要求安排一种落实方式：

| 方式 | 含义 |
| --- | --- |
| prompt | 将要求原文追加到基础提示词，仅适用于支持文字的接口 |
| reference | 发送选定图片，记录 Agent 实际观察到的对应特征 |
| postprocess | 保留待处理操作和明确验收方法，生成过程不保证满足该项 |
| unresolved | 保留缺口并阻止排队 |

每份参考须明确发送或仅留本地，排除时说明原因。要求不能依赖未发送图片。参考职责和观察属于本地记录，不会自动变成服务参数；需要向支持文字的服务说明用途时，也应写进实际提示词。

Agent 可以提供 rewrite.text 和 rewrite.reason。原始描述和差异会保留，prompt 路径的要求原文仍追加在基础提示词后。未填写改写时保留原文。保留用户选择的语言、风格、模型和输入。Agent 核对完整需求、保留项、额外内容和参考职责，记录执行者及理由。该记录是 Agent 工作声明，不是计算得到的品质分数或用户批准。

例如，门的材质通过文字描述，门洞净宽则安排模型尺寸与碰撞的后续检查。材质描述不能证明门正常转动或玩家可以通过。

## 准备、核对和排队

从[示例](../../templates/asset_preparation/README.zh-CN.md)复制一组文件到游戏项目，按真实需求修改并完成 Agent 核对。示例核对项故意保留为 false。两个文件中的路径均相对于游戏项目根目录。

```sh
python tools/asset_prepare.py --project "MyGame" prepare --spec production/crate.spec.json --plan production/crate.plan.json --output production/prepared-crate
python tools/asset_prepare.py --project "MyGame" check --request production/prepared-crate/request.json
python tools/asset_workflow.py --project "MyGame" submit --provider tripo --request production/prepared-crate/request.json
```

输出包括：

- preparation.json：冻结的要求、方案、源文件哈希、约束对应关系、Agent 核对、解析后的参数和拟发送内容。
- request.json：现有资产任务请求格式，附准备记录的路径和哈希。
- preview.md：提示词差异、约束路径、参考选择、待验收项和提交预览。
- references/：全部声明参考的副本，包含仅留本地的参考。

退出码 0 表示可排队，1 表示报告存在待解决项，2 表示文件/格式错误或核验失败。已有输出目录不会覆盖；修改后使用新目录保留历史。

预览复用适配器请求构建方法，将图片数据和远端上传令牌替换为哈希标记。它表示计划发送什么，不代表服务已接收。宿主生图预览描述提示词和参考，由 Agent 映射到当前实际可用工具。

排队前检查准备记录、服务设置、提示词、参数、参考和原始源文件哈希，变化时在建立任务前拒绝提交。已排队任务和明确重试沿用冻结输入，不随工作副本变化。准备目录应随任务保留；执行、记录校验、授权指纹和版本来源均关联该记录。付费执行沿用逐任务授权。

## 支持范围与检查边界

支持已接入的 Tripo、Hunyuan3D API 路径，Seedream 图像、Seedance 视频、ElevenLabs 音效/配乐/台词和宿主生图。优先读取项目 asset-providers.json；未配置时云服务使用 API 模式，image 使用宿主模式。混元按需要明确认证方式。命令包装器继续使用原资产流程，没有本工具的输入能力约定。

仅接收图片的 3D 路径不会发送改写文字。要求须有实际参考依据或明确后续处理安排，未解决项阻止排队。已有用户/项目 Prompt 要求继续生效。生成多视图参考属于图片交付，进入模型生成前仍需视觉检查。

台词逐字保留，不允许改写或附加制作指令。关联动作窗口的音频继续使用[音频窗口流程](elevenlabs-audio.zh-CN.md)，本工具暂不编译该类请求。

自动检查覆盖格式、显式属性冲突、输入路径、图片签名/尺寸、适配器限制和哈希；不完整解码每张图片，也不证明造型一致、风格正确、几何合格、许可成立或 Godot/Unreal 适配。后续加工项保持待处理，生成结果质量记为未验证。

生成或获取结果后，用[证据与质量评审](quality-review.zh-CN.md)检查真实输出是否符合已记录要求。

已确认的缺陷通过[结果驱动迭代](result-iteration.zh-CN.md)准备针对性调整，保留原输入基线及服务实际接收的路径。
