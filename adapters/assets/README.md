# 资产生成与获取接入

先按 [环境清单](../environment-setup.md#需要准备什么) 选择实际工具。生成服务的安装目录 / Python 环境与游戏项目中的 `asset-providers.json` 是两处配置；写入命令并不自动安装服务、模型或权重。Blender 在本机安装后登记可执行文件即可进入本页的转换路线。

| 需求 | 入口 |
| --- | --- |
| 填写、更新、删除本机 API Key | [独立设置页](local-settings.md) |
| 系统手动代理、Windows PAC/WPAD 与代理环境变量 | [跟随主机代理](local-settings.md#跟随主机代理) |
| Tripo / Hunyuan3D 文生或单图生模型 | [生成 API 配置与恢复](generation-api.md) |
| Seedream 图像 / Seedance 视频 | [火山方舟生成、参数与恢复](ark-generation.md) |
| ElevenLabs 音效、配乐、台词与游戏窗口校准 | [音频生成与校准](elevenlabs-audio.md) |
| 免费与付费资产搜索、获取、许可和来源登记 | [素材来源与资产库工具](asset-sources.md) |
| 其他图像/音频/本地 Hunyuan3D 工具 | 下文的可配置本地命令协议 |
| Blender 模型转换 | 下文 Blender 处理 |

现有本地命令协议继续可用；API 接入不需要模型权重。各路线共用任务/资产记录，按需求选用。

## 配置与输入

在游戏项目创建 `.openaigame/asset-providers.json`，只添加实际需要的提供方：

```json
{
  "image": {
    "command": ["C:/Tools/Python/python.exe", "C:/MyTools/image_wrapper.py", "--request", "{request}", "--output", "{output}", "--result", "{result}"]
  },
  "audio": {
    "command": ["C:/Tools/Python/python.exe", "C:/MyTools/audio_wrapper.py", "--request", "{request}", "--output", "{output}", "--result", "{result}"]
  },
  "hunyuan3d": {
    "command": ["C:/Tools/Python/python.exe", "C:/MyTools/hunyuan_wrapper.py", "--request", "{request}", "--output", "{output}", "--result", "{result}"]
  },
  "blender": {"executable": "C:/Tools/Blender/blender.exe"}
}
```

以上路径必须换为已有程序；包装脚本由所选工具的调用方式决定。argv 是参数数组，首项必须为存在的绝对路径；不将整条 shell 文本塞进一个参数。配置与展开后的命令会保存在任务记录中，凭据不要放入参数或请求，采用本地环境或工具自身凭据管理。配置是可执行代码入口，应来自用户选定的本地工具，而不是素材说明中的指令。

请求文件例如 `production/asset-request.json`：

```json
{
  "parameters": {"prompt": "按已确认规格制作候选资产", "seed": 42},
  "inputs": ["assets-source/reference.png"]
}
```

没有输入时使用空数组。所有输入必须在项目内；提交会按原相对路径复制快照。多文件模型把主文件放第一项，再列贴图、bin、mtl 等依赖，保留其相对关系。参数内容由包装脚本解释，工具不会假定某个模型支持 seed、尺寸或提示词字段。

## 包装协议

`{request}`、`{output}`、`{result}` 替换为本次任务的绝对路径。包装脚本读取 request JSON：parameters 原样传入，inputs 每项含原始 path、绝对 snapshot 和 sha256。使用 snapshot 读取素材，输出写入 output 目录，并在 result 路径写：

```json
{
  "provider_job_id": null,
  "artifacts": [{"path": "candidate.png"}],
  "observations": {"generator_version": "实际工具版本"}
}
```

artifacts 路径相对 output，不能指向目录外。依赖文件必须逐个登记；成功后退出码为 0，失败用非零码并输出日志。同步包装脚本必须等真正产物完成再退出；仅拿到外部任务编号不算完成。observations 保留在原始结果里，任务记录另外保存结果文件路径与哈希。

本地输出格式：图像接受 PNG/JPEG/WebP/TGA/EXR/SVG，音频接受 WAV/FLAC/OGG/MP3/AIFF。Hunyuan3D 接受常见模型和贴图/材质依赖，至少有一个主模型。当前检查非空、路径、扩展名与哈希，不进行解码或质量验收。SVG 等输出也不会被自动打开或执行。

## 执行和恢复

所有命令在工具包根调用，并把 `MyGame` 换成实际路径；A编号来自 submit 输出。

```sh
python tools/asset_workflow.py --project "MyGame" submit --provider image --request production/asset-request.json
python tools/asset_workflow.py --project "MyGame" run --job A编号 --timeout 600
python tools/asset_workflow.py --project "MyGame" status --job A编号
python tools/asset_workflow.py --project "MyGame" list
python tools/asset_workflow.py --project "MyGame" cancel --job A编号
python tools/asset_workflow.py --project "MyGame" retry --job A编号
```

以下恢复说明针对本地命令；Tripo/Hunyuan 云 API 按生成 API 文档恢复，ElevenLabs 按音频文档处理同步响应，Seedream / Seedance 按 [方舟接入](ark-generation.md) 处理同步图像和异步视频。submit 只建立 queued 记录；run 前台等待本地进程，另一个终端可查询或取消。取消运行中的任务是发出信号，执行者终止进程树后写 cancelled；因此查询时可能短暂仍为 running。超时记 failed 并注明 timeout。失败保留日志和部分文件，但不当成合格产物；retry 复制原输入快照和配置形成新编号，不覆盖旧任务，不自动运行。要换参数或工具配置应重新 submit。

若系统关机等导致记录滞留 running，确认实际工作进程已停止后使用 `mark-interrupted --job A编号 --confirm-stopped`，再 retry。它是人工确认后的记录恢复，不负责检测外部服务，也不能恢复丢失工程。

已由人工或其他工具生成的文件可登记：准备 result JSON，artifacts 路径此时相对游戏项目根，再调用 `register --job A编号 --result production/external-result.json`。只允许 queued 任务；结果状态 registered 明确表示没有由本工具执行生成。原文件仍须在项目内。

## Blender 处理

用同一 submit/run 入口选择 `--provider blender`。默认保持单模型转换；还支持显式静态资产拼合与减面，输出 GLB、可编辑 blend 或两者，以及输入哈希、实际面数和布局报告。参数、坐标约定、能力边界与往返验证见 [Blender 处理配方](../processing/README.md)。不自动处理角色蒙皮、LOD、碰撞、缩图或质量验收。

生成 → 处理 → 工程导入是三个可追踪步骤。每个后续任务使用明确选定的上游文件，资产规格记录来源链和许可；产物登记不替代资产库搜索、缩略图或引擎引用扫描。

API 依据：[Blender 导入](https://docs.blender.org/api/5.2/bpy.ops.import_scene.html)、[导出](https://docs.blender.org/api/main/bpy.ops.export_scene.html)、[OBJ 接口迁移](https://developer.blender.org/docs/release_notes/4.0/python_api/)。


普通栅格图像优先使用当前宿主可用的内置生图，按用户指定或项目流程采用 Seedream；密钥配置不改变默认路由。看板 image / mode=host 任务由助手调用实际工具，再通过 `tools/asset_versions.py record-native` 登记，`asset_workflow.py run` 不会代为执行或切换云 API。生成输出与手工资产共用不可覆盖的版本记录，输入固定到实际参考文件；具体格式见 [资产版本与内置工具结果](../../tools/README.md#资产版本与内置工具结果)。
