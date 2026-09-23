# Tripo 与 Hunyuan3D API

两个提供器均支持文生 3D、单图生 3D、任务查询、下载与中断恢复。使用 Python 3.10+ 标准库，不要求本地 GPU、模型权重或第三方 SDK。绑定、动作生成、自动拓扑优化及引擎导入是后续独立任务。

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

Tripo 在 [API 平台](https://platform.tripo3d.ai/) 创建密钥。混元默认使用腾讯云专业版 API，需要已开通的服务、SecretId/SecretKey 和账户支持的地域；示例地域须按账户实际配置。临时凭据可增加 `token_env`，默认读取 `TENCENTCLOUD_TOKEN`。

如账户使用混元 API Key 接口，将混元配置替换为：

```json
{"mode": "api", "auth": "api_key", "api_key_env": "HUNYUAN3D_API_KEY"}
```

这一路径针对腾讯官方 `api.ai3d.cloud.tencent.com/v1/ai3d`，不代表所有第三方 Hunyuan 托管服务都兼容。腾讯已说明该平台逐步迁移，新账户应核对实际开通的接口；TokenHub 或其他提供方使用不同协议时需要另外接入。

Tripo / 混元 API Key 可在设置页加密保存；也可将密钥值放在运行工具的进程环境中。Windows 环境变量方式需要重启运行工具的终端或宿主，设置页保存则即时供后续调用读取。TC3 凭据继续使用环境变量。配置文件只存变量名，环境变量优先于本机存储。不要把密钥放进聊天、请求参数、版本库或命令参数。只检查本地配置、不发起收费任务：

```sh
python tools/asset_workflow.py --project "MyGame" doctor --provider tripo
python tools/asset_workflow.py --project "MyGame" doctor --provider hunyuan3d
```

`ready_to_attempt` 只证明本地配置与凭据存在，不证明账户额度、权限或网络可用。

## 提交与下载

先保存游戏项目中的 `production/asset-request.json`。Tripo 文生模型：

```json
{"parameters": {"prompt": "A stylized wooden supply crate", "pbr": true}, "inputs": []}
```

混元文生模型：

```json
{"parameters": {"Prompt": "风格化木质补给箱", "EnablePBR": true}, "inputs": []}
```

单图生模型时删除 prompt/Prompt，使用 `"inputs": ["assets-source/reference.png"]`。只读输入快照；Tripo 接受最多 20 MiB 单图，混元保守限制原图 4 MiB，均支持 PNG/JPEG/WebP。模型版本等参数在 `parameters` 指定，以所选服务实际支持范围为准，不自动替换服务或模型。参数校验拒绝未知字段；扩展参数时同时更新适配器和测试。

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider tripo --request production/asset-request.json
python tools/settings_server.py --project "MyGame" --approve-job A实际编号
```

用户在浏览器核对服务、提示词、输入文件以及可能的费用后，亲自确认本次生成。授权有效一小时，仅绑定这一个请求和当前账户，使用一次后失效。已有有效授权不再重复确认；保存密钥、任务排队或助手写下“已同意”都不等于生成授权。用户确认后执行：

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
