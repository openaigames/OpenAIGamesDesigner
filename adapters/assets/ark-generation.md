# Seedream 图像与 Seedance 视频

两个提供器通过火山方舟官方 API 生成文件，接入同一套本机密钥、项目任务、逐次授权、结果下载与资产登记流程。无需额外安装 SDK；网络沿用工具包的主机代理设置。

## 配置与账户

在看板“资产生成模型配置”的 Seedream 或 Seedance 卡片保存一次火山方舟 API Key，两张卡片共用 `ARK_API_KEY`。更新或移除任一卡片都会影响另一张；环境变量优先于本机加密存储。配置状态不代表模型权限或余额已验证。

- [方舟 API Key 管理](https://ark.volcengine.com/region:cn-beijing/apiKey)
- [火山引擎账户充值](https://console.volcengine.com/finance/fund/recharge)
- [模型价格](https://docs.volcengine.com/docs/ark/model-pricing?lang=zh)

密钥管理网页不是模型调用 URL。适配器使用 `https://ark.cn-beijing.volces.com/api/v3`，不会把凭据发送到任意自定义地址。已有项目可以显式配置命名环境变量：

```json
{
  "seedream": {"mode": "api", "api_key_env": "ARK_API_KEY"},
  "seedance": {"mode": "api", "api_key_env": "ARK_API_KEY", "poll_seconds": 5}
}
```

以上内容保存在项目 `.openaigame/asset-providers.json`；不要填入真实密钥。项目配置优先于本机默认，因此显式指定不同环境变量时，实际使用的账户可能不同于卡片共用密钥。

## 支持范围

| 提供器 | 当前输入与输出 | 主要参数 |
| --- | --- | --- |
| Seedream | 文生单图；一张本地参考图改绘；下载 PNG / JPEG / WebP 并按真实文件头命名 | Model ID、尺寸档位、水印、提示词 |
| Seedance | 文生视频；一张本地首帧图生视频；异步查询并下载 MP4 | Model ID、整数秒时长、分辨率、比例、是否有声、水印、提示词 |

默认 Model ID 为 `doubao-seedream-5-0-pro-260628`、`doubao-seedance-2-5-260628`，使用前需在账户开通。支持的模型族：Seedream 4.0 / 4.5 / 5.0 Pro / Flash / Lite，Seedance 2.0 / Fast / Mini / 2.5。当前填写 Model ID，不接受未注明能力的 Endpoint ID。参数按模型族检查：Seedream 5.0 Pro / Flash 为 1K、1.5K、2K；4.5 为 2K、4K；5.0 Lite 为 2K、3K、4K；4.0 为 1K、2K、4K。Seedance 2.5 为 4–30 秒，2.0 系列为 4–15 秒；Fast / Mini 使用 480p 或 720p，其余支持至 1080p。

输入图限项目内一张 PNG / JPEG / WebP，最大 10 MiB；保存任务时复制快照并记录 SHA-256，提交前重新校验。Seedance 2.5 首帧任务要求 `ratio: adaptive`，界面选图后自动切换。参考图更细的分辨率、内容限制由官方接口判断。当前没有多参考图、视频编辑、图层拆分、组图和自动重提交。视频是渲染成片，不能替代角色骨骼动画。

## 看板与命令行

看板“生成任务 → 新建任务”可选择两个服务，填写上述参数及可选参考图。保存仅建立待确认任务；用户核对提示词、输入快照及费用后授权，助手再执行。支持的默认尺寸与时长写入任务记录，避免隐藏的参数影响请求。文件生成后可在资产库打开，也可通过 `asset_library.py from-job` 登记来源。

Seedream 请求示例：

```json
{
  "parameters": {"prompt": "游戏用的风格化石门概念图，正面构图", "model": "doubao-seedream-5-0-pro-260628", "size": "2K", "watermark": true},
  "inputs": []
}
```

Seedance 请求示例：

```json
{
  "parameters": {"prompt": "镜头缓慢推进，城堡庭院的旗帜随风摆动", "model": "doubao-seedance-2-5-260628", "duration": 5, "resolution": "720p", "ratio": "16:9", "generate_audio": true, "watermark": true},
  "inputs": []
}
```

```sh
python tools/asset_workflow.py --project "MyGame" doctor --provider seedream
python tools/asset_workflow.py --project "MyGame" submit --provider seedream --request production/image-request.json
python tools/settings_server.py --project "MyGame" --approve-job A实际编号
# 用户在页面授权后：
python tools/asset_workflow.py --project "MyGame" run --job A实际编号 --timeout 600
```

视频换成 `--provider seedance` 和相应请求文件；运行超时可按任务需要设置，例如 1800 秒。`doctor` 仅检查配置，不访问生成 API、不消耗额度。单次授权绑定项目、提供器、参数、输入哈希和实际密钥；替换共用密钥后旧授权失效。

## 中断、下载与验收

- Seedance 在提交后立即保存任务 ID。停止本地进程不等于取消云端生成；任务失败、中断或下载失败后用 `resume --job A实际编号` 查询并下载原任务，不再 POST 新任务。仅在用户明确要求重新生成时准备新任务并重新授权。
- Seedream 是同步生成接口，没有可恢复的云任务 ID。响应丢失或下载失败时检查本地 `remote.json` 和平台记录；不要把请求 ID 当任务 ID，也不要自动重发。明确重新生成时使用 `retry --new-generation` 并重新授权。已落盘文件可检查后单独登记。
- 下载使用受限 HTTPS 通道，不携带 API Key；临时签名 URL 不进入日志或任务 JSON。输出写入任务的 `attempt-N/output`，记录路径、大小、哈希和来源。
- 文件头及容器检查只确认基本格式。模型返回的尺寸／时长、真实播放、画面质量与游戏导入分别验收；部分 1080p 视频采用 HEVC，浏览器能否播放取决于实际解码环境。

接口依据核对于 2026-09-30：[图像生成](https://docs.volcengine.com/docs/ark/image-generation-api?lang=zh)、[创建视频任务](https://docs.volcengine.com/docs/ark/create-video-generation-task-api?lang=zh)、[查询视频任务](https://docs.volcengine.com/docs/ark/get-video-generation-task-api?lang=zh)、[Base URL 与鉴权](https://docs.volcengine.com/docs/ark/base-url-and-authentication?lang=en)。具体开通权限、地区、计费和新版本能力以账户与官方文档为准。
