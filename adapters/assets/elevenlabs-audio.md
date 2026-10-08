# ElevenLabs 游戏音频

通过现有的服务配置、制作任务和资产库生成音效、配乐与台词。`elevenlabs` 是云服务适配器；`audio` 仍是已有的本地音频工具包装入口。生成文件先作为候补，按项目内容根接入游戏后归入游戏应用，不增加新的看板阶段。

## 配置与运行

在看板「资产生成模型配置」或独立设置页保存 ElevenLabs API Key。Windows 使用当前用户 DPAPI；其他系统设置 `ELEVENLABS_API_KEY`。项目可选配置如下，只保存变量名：

```json
{"elevenlabs":{"mode":"api","api_key_env":"ELEVENLABS_API_KEY"}}
```

MP3 解码需要 FFmpeg，可使用 PATH 中的 `ffmpeg`、环境变量 `OAGD_FFMPEG` 指定的绝对程序路径，或在执行工具的 Python 中安装 `imageio-ffmpeg`。这些是本机依赖，工具包不附带 FFmpeg 二进制。缺少解码器会在生成前停止。Python 示例：`python -m pip install imageio-ffmpeg`。

```sh
python tools/asset_workflow.py --project MyGame doctor --provider elevenlabs
python tools/asset_workflow.py --project MyGame submit --provider elevenlabs --request production/sword-audio.json
python tools/project_workbench.py --project MyGame --approve-job A编号
python tools/asset_workflow.py --project MyGame run --job A编号 --timeout 900
```

也可在看板「制作任务 → 新建」选择 ElevenLabs，填写需求。保存只建立任务；核对生成内容、时长、来源和可能费用并授权后，由助手执行。`doctor` 只检查凭据与解码器存在，不联网验证权限、额度或音质。

## 根据游戏窗口准备音效

优先读游戏里的动作事件、Notify 或配置数据，明确窗口时基与实际播放倍率。UE 原生资源需先从引擎导出相应配置；工具不会声称直接解析 `.uasset`。例如 `Config/combat.json`：

```json
{"actions":{"light01":{"swing_window":{"start_seconds":0.12,"end_seconds":0.36,"play_rate":1.2}}}}
```

请求 `production/sword-audio.json`：

```json
{
  "parameters": {
    "kind": "sound_effect",
    "text": "A single crisp light sword whoosh, dry and close, no impact or background sound",
    "timing": {
      "event": "player.sword.light01.swing",
      "source": {"path":"Config/combat.json","pointer":"/actions/light01/swing_window"},
      "tail_seconds": 0.04,
      "trim_start_seconds": 0,
      "fade_in_seconds": 0.002,
      "fade_out_seconds": 0.008,
      "fit": true
    }
  },
  "inputs": []
}
```

主体时长 = `(窗口结束 - 窗口开始) / 固定播放倍率`；尾音按实际秒额外计算。上例主体 0.20 秒、尾音 0.04 秒，成品副本为 0.24 秒。官方音效接口接受 0.5–30 秒，因此请求生成 0.5 秒并保留原件，再制作 0.24 秒副本。生成器不保证声音的起音或峰值精确落点，默认从原件 0 秒开始裁剪；必须试听后选择合适的 `trim_start_seconds`。不把完整动作时长当作挥动窗口，不把挥剑与命中合在一次固定播放中。

`source` 使用项目相对路径和 JSON Pointer，目标对象包含上述三个字段。提交自动保存配置快照；授权及运行前对照当前文件哈希和窗口，变化后要求重新准备请求。看板也显示已有产物对应的来源是否改变。整个 JSON 的修改都会使该来源失效；时序配置与凭据分开保存。该配置文件留在本地，向服务只发送音效描述、模型、生成时长及音效选项。

尚无导出配置时可将 `source` 替换为 `window`，手填三个字段；看板明确显示尚未核对引擎。此公式只支持固定倍率；变速曲线、hit stop、时间膨胀、暂停和取消行为需以实际运行验证，不伪装为已绑定的动态时长。

独立音效可不用 `timing`，改用 `duration_seconds`（0.5–30）、`loop`（默认 false）及 `prompt_influence`（0–1）。窗口模式不能同时指定独立时长或循环。`fit:false` 仅生成和测量，不裁剪；环境循环需检查接缝，不能套用单发淡入淡出的裁剪规则。

## 配乐和台词

```json
{"parameters":{"kind":"music","text":"Tense orchestral boss encounter, low strings and driving percussion","music_length_ms":30000,"force_instrumental":true},"inputs":[]}
```

配乐支持明确长度（3000–600000 毫秒）和纯器乐选项；默认 `music_v1`，也可指定 `music_v2` 或 `music_v2_5`。此入口使用描述生成，不接收 composition plan、分轨或克隆声音请求。循环、段落切换和战斗阶段衔接由音频设计及引擎混音实现，不宣称生成一次即可完成自适应音乐。

```json
{"parameters":{"kind":"speech","text":"你已经无路可退了。","voice_id":"替换为账户可用的声音ID","model_id":"eleven_multilingual_v2"},"inputs":[]}
```

台词可用 `eleven_multilingual_v2`、`eleven_flash_v2_5`、`eleven_turbo_v2_5` 或 `eleven_v3`。按实测时长调整文本和表演，不自动裁掉字句。访问声音和模型的权限以账户实际响应为准。

## 产物、校准与恢复

产物包括 `original.mp3`、解码保留声道与采样率的 `decoded.wav`，窗口模式还提供 `window.wav`。副本只裁剪、末尾补静音和短淡入淡出，不改变音高、不时间拉伸；原件不覆盖。结果记录原件哈希、请求参数、返回的成本/请求标识（若服务提供）、实际采样率、声道、时长、峰值、RMS、阈值起音/尾部和裁剪配方。请求标识不等于可恢复云任务。

裁剪不足会记录补静音帧数；静音、满幅样本和 -60 dBFS 阈值起止仅供诊断。所有结果的听感、游戏时序与许可均保持未验收，文件时长匹配不自动成为游戏应用资产。试听副本与原件，检查起音、力度、尾音、命中确认、并发和取消清理，再接引擎校对。

对本地原件调整截取起点后，无需再次调用服务：

```sh
python tools/audio_workflow.py --project MyGame inspect --input assets-source/audio/decoded.wav
python tools/audio_workflow.py --project MyGame fit --input assets-source/audio/decoded.wav --request production/sword-audio.json --output assets-source/audio/sword-r2.wav
```

输出新的 WAV 与 `.timing.json` 配方，拒绝覆盖已有修订。`fit` 不向云发送请求，也不修改游戏配置。MP3 需要先使用 `decode --input 路径/original.mp3 --output 路径/decoded-r2.wav`；生成任务目录中的路径同样可用。

ElevenLabs 返回同步音频，工具没有按 request-id 恢复或取消远端生成的接口。超时、断网、取消和进程退出都不会自动重发；本地取消不保证免计费。检查任务 attempt 目录中的 `remote.json`：`submitting` 表示结果未知，`response_saved` 表示已保存原件，可用本地 decode/fit 恢复加工；不要丢掉原件重新收费生成。`resume` 会明确拒绝；确需重新生成，显式 `retry --new-generation` 创建新任务并重新核对授权。来源改变时应新建参数更新后的请求。

## 官方依据与使用范围

- [音效接口](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert)、[音乐接口](https://elevenlabs.io/docs/api-reference/music/compose)、[语音接口](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)、[API 认证](https://elevenlabs.io/docs/api-reference/authentication)。本接入固定请求 `mp3_44100_128`，生成后解码为 PCM16 WAV；WAV 不会提升原始 MP3 的质量。
- 费用、账户权限和输出权利依所用服务与套餐核对并记入项目来源记录。按 [音乐模型条款](https://elevenlabs.io/eleven-music-model-specific-terms)，商业化且跨多个平台发行的游戏属于 Studio Games，普通自助订阅并不覆盖该用途；不要把“已付费”记录成游戏商业发行已获许可。工具包不分发生成音频或替用户认定许可合格。
