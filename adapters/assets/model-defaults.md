# Generation Model Defaults

[English](model-defaults.md) | [简体中文](model-defaults.zh-CN.md)

New jobs use explicitly configured quality-oriented models. model_defaults.py maintains IDs centrally; provider-side defaults do not change them automatically.

| Service | Configured default | Official reference |
| --- | --- | --- |
| ElevenLabs speech | eleven_v4 | [Model selection](https://elevenlabs.io/docs/eleven-api/choosing-the-right-model), [speech API](https://elevenlabs.io/docs/eleven-api/guides/cookbooks/text-to-speech) |
| ElevenLabs music | music_v2_5 | [Music](https://elevenlabs.io/docs/eleven-creative/products/music), [Compose](https://elevenlabs.io/docs/api-reference/music/compose) |
| ElevenLabs effects | eleven_text_to_sound_v2 | [Models](https://elevenlabs.io/docs/overview/models) |
| Tripo 3D geometry | H3.1 / v3.1-20260211 | [Flagship model](https://developers.tripo3d.ai/en/models/v3-1), [text](https://developers.tripo3d.ai/en/docs/generation-text-to-model/standard), [image](https://developers.tripo3d.ai/en/docs/generation-image-to-model/standard), [multiview](https://developers.tripo3d.ai/en/docs/generation-multiview-to-model/standard) |
| Tripo textures for new H3.1 jobs | v3.5-20260815 | [Independent texture model selection](https://developers.tripo3d.ai/en/docs/generation-text-to-model/standard) |
| Tencent Hunyuan 3D | 3.1 | [Professional API](https://cloud.tencent.com/document/api/1804/123447), [mode compatibility (Chinese)](https://intl.cloud.tencent.com/zh/document/product/1284/75540) |
| Seedream images | 5.0 Pro / doubao-seedream-5-0-pro-260628 | [Ark models (Chinese)](https://docs.volcengine.com/docs/ark/model-list?lang=zh), [announcements (Chinese)](https://docs.volcengine.com/docs/ark/model-release-announcement?lang=zh) |
| Seedance video | 2.5 / doubao-seedance-2-5-260628 | [Ark models (Chinese)](https://docs.volcengine.com/docs/ark/model-list?lang=zh), [announcements (Chinese)](https://docs.volcengine.com/docs/ark/model-release-announcement?lang=zh) |

## Selection and Updates

Before a new generation batch, verify models against official lists/APIs. When updating defaults, update validation, UI defaults, examples, and request tests together, preserving verification evidence in maintenance records. Do not rank solely by date/version: Flash/Turbo/Lite and quality-focused models serve different purposes. Honor explicit speed, cost, compatibility, or reproduction choices.

When copying historical requests, retain deliberate voice/content/parameter choices, but do not assume an old script's model is a new user requirement. For unspecified models, asset_workflow.new_job resolves the actual ID before queuing/authorization. Queued jobs do not drift with later defaults; explicit IDs are not forcibly replaced.

Do not batch-rewrite old jobs/results/assets. Authorization digests include resolved models. If an old queue omitted a model, changed defaults invalidate authorization for a different model. Resume queries the original cloud job, not a replacement generation. Unavailable access/compatibility is reported without automatic downgrades, service changes, or repeat charges.

Hunyuan Sketch/LowPoly require explicit compatible 3.0; default 3.1 never silently falls back. Tripo image-to-multiview accepts no model-version parameter, so none is invented.

Tripo uses the V3 API with separate geometry and texture model IDs. Only newly created H3.1 jobs with textures receive the texture default; explicit texture selections, historical queues, and retries keep their existing settings. Geometry-only jobs omit the texture model. Quality levels such as detailed geometry or 8K textures remain explicit parameters, since they can affect cost and generation time.

## Interfaces without Model Selection

Built-in image generation uses the tool available in the agent host. This toolkit does not expose model selection for that tool. Generic image/audio/local Hunyuan wrappers run user-configured tools with no universal model contract; do not inject model parameters. Blender is a local authoring tool. Poly Haven, Kenney, Mixamo, Freesound, and similar sources are asset/production services, not generation defaults.

These are fixed settings without background updates. Actual authorized jobs verify account access and outputs; offline tests do not establish service-generation success.
