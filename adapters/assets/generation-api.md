# Tripo 与 Hunyuan3D API

本地已接入的生成方式见 [能力表](generation-capabilities.md)，由程序中的同一份说明生成；看板和提交检查也读取这份说明。Tripo 的单图生成多视图会输出图片，后续模型生成是另一项任务。两个服务均可查询任务、下载结果和恢复中断的任务。使用 Python 3.10+ 标准库，不要求本地 GPU、模型权重或第三方 SDK。绑定、动作生成、自动拓扑优化及引擎导入是后续独立任务。

## 模型生成与骨架的边界

当前本地适配器调用普通模型生成接口，没有接入平台自动绑骨任务，也不接受任意骨架文件或尺寸 JSON 作为生成约束。平台能力与本地已实现能力分开核实，不能用未知参数模拟未接入接口。GLB/FBX 扩展名不证明文件含骨架、有效蒙皮或可用动画；应在 DCC/引擎中读取并实际播放。

需要动画的新模型，先沿用或确认用户的制作路线：先定模型再绑骨配动作，或按已有动画/骨架比例制作。具体方法见 game-technical-art 的 `references/rig-aware-asset-production.md`。尺寸可以写入文生提示或用于构造图片参考，但是否真正传入以当前接口为准；按所选方式核对是否支持图片和约束文字共同输入。用户要求共同输入时，不能自行删掉文字或图片；已明确选用只发送图片的任务沿用该选择。没有发送的长度记录用于生成后校准，不宣称服务已读取。路线确认沿用已有决定，不代替本节后续的收费任务授权。

未指定模型的新任务默认使用 Tripo H3.1 / `v3.1-20260211` 和混元 `3.1`。模型在创建任务时写入请求并参与授权摘要；具体来源与更新规则见 [旗舰模型策略](model-defaults.md)。Sketch / LowPoly 仍须显式指定兼容的 `3.0`，不会为兼容模式自动降级。

## 配置

推荐先打开 [本机服务与密钥设置页](local-settings.md)：`python tools/settings_server.py`。在页面保存 Tripo / 腾讯混元兼容接口 API Key 后，项目可直接使用默认 API 配置，无需手填 mode/auth。工具读取本机配置，密钥不经过模型。

需要项目独立设置、腾讯云 TC3 认证或已有本地命令时，在游戏项目的 `.openaigame/asset-providers.json` 添加需要的提供器，保留其他配置；对应项目配置优先：

```json
{
  "tripo": {"mode": "api", "api_key_env": "TRIPO_API_KEY", "poll_seconds": 5},
  "hunyuan3d": {
    "mode": "api", "auth": "tc3", "region": "ap-guangzhou",
    "secret_id_env": "TENCENTCLOUD_SECRET_ID",
    "secret_key_env": "TENCENTCLOUD_SECRET_KEY", "poll_seconds": 5
  }
}
```

Tripo 在 [API 平台](https://platform.tripo3d.ai/) 创建密钥。通过密钥设置页保存的混元 API Key 使用 API Key 认证；项目显式配置 TC3 时使用 SecretId/SecretKey 和账户支持的地域。示例地域须按账户实际配置。临时凭据可增加 `token_env`，默认读取 `TENCENTCLOUD_TOKEN`。

如账户使用混元 API Key 接口，将混元配置替换为：

```json
{"mode": "api", "auth": "api_key", "api_key_env": "HUNYUAN3D_API_KEY"}
```

这一路径针对腾讯官方 `api.ai3d.cloud.tencent.com/v1/ai3d`，不代表所有第三方 Hunyuan 托管服务都兼容。腾讯已说明该平台逐步迁移，新账户应核对实际开通的接口；TokenHub 或其他提供方使用不同协议时需要另外接入。

Tripo / 混元 API Key 可在设置页加密保存；也可将密钥值放在运行工具的进程环境中。Windows 环境变量方式需要重启运行工具的终端或 Agent 运行环境，设置页保存则即时供后续调用读取。TC3 凭据继续使用环境变量。配置文件只存变量名，环境变量优先于本机存储。不要把密钥放进聊天、请求参数、版本库或命令参数。只检查本地配置、不发起收费任务：

```sh
python tools/asset_workflow.py --project "MyGame" doctor --provider tripo
python tools/asset_workflow.py --project "MyGame" doctor --provider hunyuan3d
```

`ready_to_attempt` 只证明本地配置与凭据存在，不证明账户额度、权限或网络可用。

## 提交与下载

先保存游戏项目中的 `production/asset-request.json`。Tripo 文生模型：

```json
{"parameters": {"prompt": "A stylized wooden supply crate", "model_version": "v3.1-20260211", "pbr": true}, "inputs": []}
```

混元文生模型：

```json
{"parameters": {"Prompt": "风格化木质补给箱", "Model": "3.1", "EnablePBR": true}, "inputs": []}
```

已选用只发送图片的模型生成方式时，不添加不支持的 prompt/Prompt，使用 `"inputs": ["assets-source/reference.png"]`。只读输入快照；Tripo 接受最多 20 MiB 单图。混元单图接受 PNG/JPEG/WebP，多视图接受 PNG/JPEG，每边大于 128、小于 5000，单文件至多 6 MiB，所有图片 Base64 编码后的总量至多 8 MiB。超限会在排队前报错，不自动缩图或省略输入。模型版本等参数在 `parameters` 指定，以所选服务实际支持范围为准，不自动替换服务或模型。

### 混元多视图与文字

```json
{
  "parameters": {"Model":"3.1", "GenerateType":"Normal", "EnablePBR":true, "FaceCount":1000000},
  "inputs": [
    {"path":"assets-source/object-front.png", "view":"front"},
    {"path":"assets-source/object-left.png", "view":"left"},
    {"path":"assets-source/object-back.png", "view":"back"}
  ],
  "brief":"本地制作说明：实际风格和比例须体现在输入图片中。这段文字不会上传。"
}
```

`front` 映射为 `ImageBase64`，其他视图映射为 `MultiViewImages` 中的 `ViewType` 与 `ViewImageBase64`。必须有且只有一个正面，每个方向一张；不能把三视图拼图作为三个方向，也不能把同一图重复标记。左右指对象自身方向。3.0 支持 front/left/right/back；3.1 另支持 top/bottom/left_front/right_front。先核对各图对象、比例、姿态与构造一致性，侧面遮挡可以保留真实投影。

普通图生模式不同时接受 Prompt。传入图片和 Prompt 会明确报错，绝不静默丢弃。文生模式可以发送 Prompt；本地 `brief` 是独立说明，仅供人工审阅。当前仅 3.0 的单图 Sketch 路径允许图片与 Prompt 并用，不能为发送文字擅自改用该模式。不得把未知的 negative_prompt、尺寸 JSON 或骨架文件冒充云端支持的参数。

看板可选择文生 / 多视图方式，逐方向选择图片并预览，设置模型、目标面数和 PBR；详情显示实际输入及 Prompt 是否发送。方向、图片摘要和本地说明绑定到单次授权，重试保留它们。实际提交前保存脱敏 `transmission.json`，取得云任务号后标为 accepted；只通过离线检查不代表具体账户的云端多视图已经通过。

字段依据：[腾讯混元专业接口](https://cloud.tencent.com/document/api/1804/123447)。不要把某一次角色造型或固定视图数量写成所有资产的默认设计。

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider tripo --request production/asset-request.json
python tools/settings_server.py --project "MyGame" --approve-job A实际编号
```

用户在浏览器核对服务、提示词、输入文件以及可能的费用后，亲自确认本次生成。授权有效一小时，仅绑定这一个请求和当前账户，使用一次后失效。已有有效授权不再重复确认；保存密钥、任务排队或 Agent 写下“已同意”都不等于生成授权。用户确认后执行：

```sh
python tools/asset_workflow.py --project "MyGame" run --job A实际编号 --timeout 900
python tools/asset_workflow.py --project "MyGame" status --job A实际编号
```

混元将 provider 改为 `hunyuan3d`。submit 建立本地队列；run 和 API worker 都检查授权后才可能发送生成请求。未授权时不启动生成进程，任务仍为 queued。参数、输入摘要、项目/任务身份或密钥改变都需重新确认，不因失败自动换服务重做。

当前没有实时价格报价或服务端费用上限控制，确认页明确提示可能收费；需要预算硬限制时使用提供方账户/项目额度。该门槛覆盖本工具包正常入口，不是隔离拥有本机任意代码执行权限的程序；自定义本地 wrapper 或直接调用第三方 SDK 不在这条 API 授权检查内。

输入快照、各次执行日志、`remote.json`、结果及文件保存在 `.openaigame/asset-jobs/<任务编号>/`。结果提供非空检查、文件大小和 SHA-256；ZIP 模型保持材质/贴图相对路径，拒绝越界与代码文件解压。无法确定格式的返回文件保留为失败，不能宣称已获得合格模型。

## 中断恢复

云任务 ID 在轮询和下载之前持久化。超时、网络失败或本地取消后：

```sh
python tools/asset_workflow.py --project "MyGame" resume --job A实际编号 --timeout 900
```

resume 查询同一个云任务，下载到新的 attempt 目录，不重新提交生成。若进程意外退出而记录仍为 running，先确认执行者确已停止，再 `mark-interrupted --job A实际编号 --confirm-stopped`。若提交响应丢失且没有编号，先从服务控制台查找本次任务，再 `resume --job A实际编号 --remote-job 真实云任务编号`；无法定位时不要自动重发 POST。

`cancel` 只停止本地等待/下载，**不取消云端生成或保证退还额度**。云结果有有效期，应及时恢复；过期、失败且确需重新生成时，显式 `retry --job A实际编号 --new-generation`，再运行返回的新本地任务。调整参数则重新 submit。

新的生成任务需要新的确认。resume 只查询/下载既有云任务，不消费新的生成授权。授权已消费但提交响应丢失时，优先从服务控制台恢复真实任务编号；不能重新使用同一份授权再次提交。

完成后按 [资产获取与登记](asset-sources.md) 的 from-job 入口登记来源和许可，继续模型检查、动作/骨骼适配以及目标引擎导入。生成 3D 文件不会自动得到可用角色控制器或动作模组。

接口依据：[Tripo OpenAPI](https://platform.tripo3d.ai/docs/schema)、[混元提交](https://cloud.tencent.com/document/product/1804/123447)、[混元查询](https://cloud.tencent.com/document/product/1804/123448)、[混元 API Key 入口](https://cloud.tencent.com/document/product/1804/126189)。


### Tripo 多视图

使用 parameters.type=multiview_to_model，inputs 为带 view 的项目图片对象；必须包含 front，再提供 left/back/right 中的至少一项。每个方向独立文件，2–4 张，不接受重复图片。适配器按官方固定顺序 [front,left,back,right] 上传文件，缺失方向使用空对象，不镜像或复制其他视图。所有输入先做文件和哈希核验，再消费已有单次授权。

当前 v2 OpenAPI 文档列出 v3.1-20260211，可显式设置 geometry_quality、texture_quality、pbr 与 face_limit。图片模式不发送 prompt/negative_prompt；brief 只供本地审阅。尺寸与原骨架仍在生成后校准。看板任务详情展示实际图片方向和文字传输状态；新任务目前由 CLI/结构化请求建立，页面原有创建表单不自动变成 Tripo 多视图编辑器。

参数以 https://platform.tripo3d.ai/docs/generation 为准。工具新增传输支持的离线测试不代表真实账户成功；取得任务号与实际模型后分别记录。


## 3D 约束 Prompt 与联合输入要求

每次准备 3D 生成任务都写出约束 Prompt，覆盖对象、风格、前后结构、姿态、关键比例与材质。将用户明确的“即使有参考图也必须实际发送 Prompt”保存为个人或项目要求，而不是把某个项目的角色造型固化为默认内容。

配置文件：个人为 `%LOCALAPPDATA%/OpenAIGamesDesigner/generation-policy.json`（其他平台使用 `~/.local/share/OpenAIGamesDesigner/generation-policy.json`）；项目为 `.openaigame/generation-policy.json`。内容为 `{"version":1,"require_3d_prompt":true}`。项目不能用 false 静默覆盖个人的 true；只有用户明确改变偏好时才修改配置。未配置的其他用户保留兼容行为。

启用后，创建、授权及执行新的 Tripo/混元任务均检查真实 `parameters.prompt` / `parameters.Prompt` 与该模式的联合输入能力。`brief` 不满足这项要求。普通图片模式未确认支持文本时直接解释并拦截；不能添加服务不支持的字段、默默转存文字、舍弃参考图或自动换模型。查询和恢复下载旧云任务不重新生成，可继续；历史记录不改写。

目前本地支持的明确联合输入路线是混元 `Model=3.0, GenerateType=Sketch` 加一张正面草图和 `Prompt`。看板有独立 Sketch 选项，用户必须明确选择 3.0；不自动把多视图改成草图。当前 Tripo v2 多视图、混元 Normal/Geometry 图片路线没有确认的图片＋Prompt 支持，因此在严格要求下不可提交。新版本 SDK 的任意字段透传不证明云端会消费 Prompt；增加模式需要官方接口依据、实际 payload 测试及输出检查。

看板显示 Prompt 原文、图片、接口兼容原因及已保存的 transmission 状态。待发送、请求获接受和结果遵守约束是不同证据；保留实际发送记录，输出先做前后结构、姿态、体积检查，再加工绑定。直接绕过工具包调用 SDK 不在提交门槛覆盖范围，Agent 仍须遵守同一用户要求。


## 检查当前设置和未完成原因

看板的 Tripo、混元服务卡片提供“检查当前设置”。它显示项目设置或本机默认设置、实际认证方式、密钥来自环境变量还是本机加密保存，以及密钥管理页面和生成、查询请求地址。密钥管理页面用于取得密钥，不是接收生成请求的地址。命令行 `doctor` 也返回对应信息；密钥内容不显示。

该检查只读取本机设置，不验证账户权限或额度，不提交生成任务。任务已实际失败时，详情按现有错误编号说明认证、权限、参数、额度、请求频率、云任务或结果文件问题；证据不足时显示原因待查，不把所有错误都归因于密钥。

已有云任务编号时优先继续查询和下载。没有编号且提交是否成功不明时，先查服务控制台，不自动重新生成。仍使用原有单次生成确认，不增加重复确认步骤。

修改生成方式、认证方式或图片字段后，先运行对应的离线测试，核对发出的字段、图片方向、错误分类和恢复行为。离线测试通过不代表真实账户或生成品质通过。

更新能力说明后，用 `python tools/generation_capabilities.py` 重新生成 `adapters/assets/generation-capabilities.md`，随代码一起保存，避免文档与看板说明不同。
