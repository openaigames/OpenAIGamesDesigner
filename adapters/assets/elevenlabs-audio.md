# ElevenLabs Game Audio

[English](elevenlabs-audio.md) | [简体中文](elevenlabs-audio.zh-CN.md)

Generate effects, music, and dialogue through existing service settings, jobs, and the asset library. elevenlabs is a cloud adapter; audio remains the local wrapper entry. Generated files start as candidates and become game-applied assets after integration into project content roots, without extra workflow stages.

## Configuration and Execution

Save an ElevenLabs key in the workbench or settings page. Windows uses current-user DPAPI; other platforms use ELEVENLABS_API_KEY. Optional project configuration stores variable names only:

```json
{"elevenlabs":{"mode":"api","api_key_env":"ELEVENLABS_API_KEY"}}
```

MP3 decoding requires FFmpeg through PATH, absolute OAGD_FFMPEG, or imageio-ffmpeg installed in the executing Python. Binaries are not bundled. Missing decoders stop before generation. Example: python -m pip install imageio-ffmpeg.

```sh
python tools/asset_workflow.py --project MyGame doctor --provider elevenlabs
python tools/asset_workflow.py --project MyGame submit --provider elevenlabs --request production/sword-audio.json
python tools/project_workbench.py --project MyGame --approve-job JOB_ID
python tools/asset_workflow.py --project MyGame run --job JOB_ID --timeout 900
```

Alternatively choose ElevenLabs when creating a workbench job. Saving queues only. Review content, duration, source, and fees, authorize, then have the agent run it. doctor checks local credentials/decoder presence, not online permissions, quota, or quality.

## Prepare Effects from Gameplay Windows

Read action events, Notifies, or configuration first and identify timebase/rate. Export native UE configuration through the engine; the tool does not directly parse .uasset. Example Config/combat.json:

```json
{"actions":{"light01":{"swing_window":{"start_seconds":0.12,"end_seconds":0.36,"play_rate":1.2}}}}
```

Request production/sword-audio.json:

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

Body duration = (window end - window start) / fixed playback rate, with tail seconds added separately. The example has 0.20-second body plus 0.04-second tail. Because generation accepts 0.5–30 seconds, generate/preserve 0.5 seconds, then derive a 0.24-second copy. Onset/peak timing is not guaranteed. Cropping defaults to zero; listen and choose trim_start_seconds. Do not use the entire action duration for a swing window or combine swing/hit into one fixed trigger.

source uses a project-relative path and JSON Pointer to the three fields. Submission snapshots configuration; authorization/execution recheck hashes/window and require a new request after changes. Workbench also shows stale artifact sources. Any source-JSON edit invalidates it; keep timing separate from credentials. Configuration remains local; only description/model/generation duration/options are sent.

Without exported configuration, use window with manual fields; workbench marks it unverified against the engine. The formula supports fixed rates only. Rate curves, hit stop, time dilation, pause, and cancellation require runtime checks rather than claimed dynamic binding.

Independent effects can omit timing and use duration_seconds (0.5–30), loop (false default), and prompt_influence (0–1). Window mode cannot also specify independent duration/looping. fit:false generates/measures without cropping. Check environmental-loop seams separately; one-shot fade rules are inappropriate.

## Music and Dialogue

```json
{"parameters":{"kind":"music","text":"Tense orchestral boss encounter, low strings and driving percussion","music_length_ms":30000,"force_instrumental":true},"inputs":[]}
```

Music supports 3000–600000 ms and instrumental-only options. Default music_v2_5 can be explicitly replaced by music_v2/music_v1 for reproduction. This prompt-based entry does not accept composition plans, stems, or voice cloning. Audio design/engine mixing implement loops, transitions, and combat phases; one generation does not deliver adaptive music.

```json
{"parameters":{"kind":"speech","text":"You have nowhere left to run.","voice_id":"VOICE_ID_AVAILABLE_TO_YOUR_ACCOUNT","model_id":"eleven_v4"},"inputs":[]}
```

Speech defaults to eleven_v4, with explicit eleven_v3, eleven_multilingual_v2, eleven_flash_v2_5, or eleven_turbo_v2_5 available. Adjust text/performance from measured duration rather than truncating words automatically. Account responses determine voice/model access.

## Outputs, Calibration, and Recovery

Outputs include original.mp3 and decoded.wav preserving sample rate/channels, plus window.wav in window mode. Copies only crop, pad final silence, and apply short fades; no pitch change or time stretch. Originals remain unchanged. Results retain hashes, parameters, available cost/request IDs, measured rate/channels/duration/peak/RMS/threshold onset-tail, and crop recipe. Request IDs are not resumable jobs.

Insufficient source length records padded silence frames. Silence/full-scale samples/-60 dBFS thresholds are diagnostic only. Review listening quality, gameplay timing, and licensing separately; matching duration alone does not make an asset ready for the game. Compare original/copy, onset, impact, tail, hit confirmation, concurrency, and cancellation, then validate in-engine.

Adjust local crop starts without another service call:

```sh
python tools/audio_workflow.py --project MyGame inspect --input assets-source/audio/decoded.wav
python tools/audio_workflow.py --project MyGame fit --input assets-source/audio/decoded.wav --request production/sword-audio.json --output assets-source/audio/sword-r2.wav
```

This writes new WAV/.timing.json without overwriting revisions. fit makes no cloud request or game-config change. Decode MP3 first with decode --input PATH/original.mp3 --output PATH/decoded-r2.wav; job-directory paths work too.

ElevenLabs returns synchronous audio without remote resume/cancel by request ID. Timeout/disconnection/cancel/process exit never automatically resubmits; local cancellation does not guarantee no charge. Inspect attempt remote.json: submitting means unknown outcome; response_saved means originals exist for local decode/fit. Preserve them instead of paying to regenerate. resume explicitly rejects. If regeneration is required, retry --new-generation creates a new job requiring authorization. Changed sources need updated requests.

## Official References and Usage

- [Sound effects](https://elevenlabs.io/docs/api-reference/text-to-sound-effects/convert), [music](https://elevenlabs.io/docs/api-reference/music/compose), [speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert), [authentication](https://elevenlabs.io/docs/api-reference/authentication). The adapter requests mp3_44100_128 and decodes to PCM16 WAV; WAV does not improve source MP3 quality.
- Check fees, permissions, and output rights against the selected service/plan and retain provenance. The [music-specific terms](https://elevenlabs.io/eleven-music-model-specific-terms) distinguish commercial multi-platform Studio Games from ordinary self-service coverage. Payment alone does not establish commercial-game licensing. The toolkit neither redistributes generated audio nor certifies licenses.
