# 本地资产工具接入

先按 [环境清单](../environment-setup.md#需要准备什么) 选择实际工具。生成服务的安装目录 / Python 环境与游戏项目中的 `asset-providers.json` 是两处配置；写入命令并不自动安装服务、模型或权重。Blender 在本机安装后登记可执行文件即可进入本页的转换路线。

当前实现可配置的本地命令协议。Hunyuan3D、图像、音频通过项目提供的包装脚本运行；Blender 提供内置转换脚本。没有预选云服务、自动下载模型或凭空生成占位图冒充服务产物。后续可替换包装脚本，不改变管理文件与任务关联。

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

图像接受 PNG/JPEG/WebP/TGA/EXR/SVG，音频接受 WAV/FLAC/OGG/MP3/AIFF。Hunyuan3D 接受常见模型和贴图/材质依赖，至少有一个主模型。当前检查非空、路径、扩展名与哈希，不进行解码或质量验收。SVG 等输出也不会被自动打开或执行。

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

submit 只建立 queued 记录；run 前台等待本地进程，另一个终端可查询或取消。取消运行中的任务是发出信号，执行者终止进程树后写 cancelled；因此查询时可能短暂仍为 running。超时记 failed 并注明 timeout。失败保留日志和部分文件，但不当成合格产物；retry 复制原输入快照和配置形成新编号，不覆盖旧任务，不自动运行。要换参数或工具配置应重新 submit。

若系统关机等导致记录滞留 running，确认实际工作进程已停止后使用 `mark-interrupted --job A编号 --confirm-stopped`，再 retry。它是人工确认后的记录恢复，不负责检测外部服务，也不能恢复丢失工程。

已由人工或其他工具生成的文件可登记：准备 result JSON，artifacts 路径此时相对游戏项目根，再调用 `register --job A编号 --result production/external-result.json`。只允许 queued 任务；结果状态 registered 明确表示没有由本工具执行生成。原文件仍须在项目内。

## Blender 处理

用同一 submit/run 入口选择 `--provider blender`。请求参数 `{"format":"glb"}` 或 `{"format":"blend"}`；inputs 第一项是 GLB/glTF/FBX/OBJ 主文件。内置脚本后台导入并输出 processed 文件，记录网格数、顶点数。它不进行自动拓扑优化、绑定、烘焙或游戏内验收；需要这类工作时由技术/美术方法规划并扩展处理脚本。该版本脚本面向具有 `bpy.ops.wm.obj_import` 的 Blender，实际版本兼容须联调。

生成 → 处理 → 工程导入是三个可追踪步骤。每个后续任务使用明确选定的上游文件，资产规格记录来源链和许可；产物登记不替代资产库搜索、缩略图或引擎引用扫描。

API 依据：[Blender 导入](https://docs.blender.org/api/5.2/bpy.ops.import_scene.html)、[导出](https://docs.blender.org/api/main/bpy.ops.export_scene.html)、[OBJ 接口迁移](https://developer.blender.org/docs/release_notes/4.0/python_api/)。
