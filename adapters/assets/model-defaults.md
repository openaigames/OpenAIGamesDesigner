# 最新旗舰模型默认策略

新生成任务采用工具包中明确配置的质量优先模型。默认值的来源记录日期为 2026-10-09，具体 ID 由 `model_defaults.py` 统一维护；它们不会随服务端默认值自动变化。

| 服务 / 产品 | 当前默认模型 | 官方依据 |
| --- | --- | --- |
| ElevenLabs 语音 | `eleven_v4` | [质量优先模型指南](https://elevenlabs.io/docs/eleven-api/choosing-the-right-model)、[单人语音 API 示例](https://elevenlabs.io/docs/eleven-api/guides/cookbooks/text-to-speech) |
| ElevenLabs 配乐 | `music_v2_5` | [音乐产品](https://elevenlabs.io/docs/eleven-creative/products/music)、[Compose API](https://elevenlabs.io/docs/api-reference/music/compose) |
| ElevenLabs 音效 | `eleven_text_to_sound_v2` | [官方模型列表](https://elevenlabs.io/docs/overview/models) |
| Tripo 3D | H3.1 / `v3.1-20260211` | [文生模型](https://docs.tripo3d.ai/model-generation/text-to-model-v3-0-v3-1.html)、[图生模型](https://docs.tripo3d.ai/model-generation/image-to-model-v3-0-v3-1.html)、[多视图模型](https://docs.tripo3d.ai/model-generation/multiview-to-model-v3-0-v3-1.html) |
| 腾讯混元 3D | `3.1` | [专业版 API](https://cloud.tencent.com/document/api/1804/123447)、[模式兼容性](https://intl.cloud.tencent.com/zh/document/product/1284/75540) |
| Seedream 图像 | 5.0 Pro / `doubao-seedream-5-0-pro-260628` | [方舟模型列表](https://docs.volcengine.com/docs/ark/model-list?lang=zh)、[发布记录](https://docs.volcengine.com/docs/ark/model-release-announcement?lang=zh) |
| Seedance 视频 | 2.5 / `doubao-seedance-2-5-260628` | [方舟模型列表](https://docs.volcengine.com/docs/ark/model-list?lang=zh)、[发布记录](https://docs.volcengine.com/docs/ark/model-release-announcement?lang=zh) |

## 选择与更新

准备新一批生成前，对照官方模型清单和对应 API 核实本表是否仍是最新旗舰；版本已更新时同时修订代码默认值、参数校验、界面默认值、示例和请求测试，并记录核验日期与来源。不要仅按发布时间或版本号排序：Flash、Turbo、Lite、极速与质量旗舰是不同定位。用户明确要求速度、成本、兼容模式或旧版复现时，保留该选择。

复制历史制作请求时，保留有意选择的声音、内容与其他参数；不要把旧脚本中的型号当成用户当前任务的明确版本要求。新任务未指定版本时，`asset_workflow.new_job` 在建立队列及授权摘要之前填入本表的实际 ID，任务建立后不随默认值更新而漂移。显式版本不会被强行覆盖。

旧任务、旧结果和已生成资产不批量改写。授权摘要包含实际解析出的模型，旧队列若未固定型号，默认值改变后原授权不能用于另一型号。恢复已有云任务继续查询原任务，不创建替代生成。账户未开通旗舰或接口不兼容时报告具体问题，不自动降级、换服务或重复收费生成。

混元 Sketch / LowPoly 仍需明确选择兼容的 3.0；默认 3.1 不会静默退回 3.0。Tripo 单图生成多视图图片接口不提供模型版本参数，不添加虚构型号。

## 无可选模型的入口

内置生图的模型由 Agent 提供的工具控制，当前调用参数没有模型选择项；使用 Agent 运行环境实际提供的能力，不把它标成某个未经确认的旗舰。通用 image / audio / 本地 Hunyuan 命令包装器由用户配置外部工具，本工具包没有可验证的通用型号，不能给任意命令强塞模型参数。Blender 是本地制作工具；Poly Haven、Kenney、Mixamo、Freesound 等是资源或制作服务，不属于生成模型默认值。

这些默认值是固定配置，不会在后台自动更新。账户权限和最终生成效果需在实际获授权的任务中验证；离线测试不等于真实服务生成成功。
