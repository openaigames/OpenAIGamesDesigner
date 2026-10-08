# 本地已接入的 3D 生成方式

本表由 `tools/generation_capabilities.py` 根据程序中的能力说明生成。它说明当前安装版本接入了什么，不代表账户已开通、网络可用或生成质量已通过检查。

| 服务 | 模型版本 | 方式 | 图片数 | 文字 | 输出 |
| --- | --- | --- | --- | --- | --- |
| tripo | 由服务选择 | 文字生成模型 / text_to_model | 0 | 需要 | 模型 |
| tripo | 由服务选择 | 单图生成模型 / image_to_model | 1 | 不发送 | 模型 |
| tripo | 由服务选择 | 多视图生成模型 / multiview_to_model | 2–4 | 不发送 | 模型 |
| tripo | 此接口不接收模型版本 | 单图生成多视图图片 / generate_multiview_image | 1 | 不发送 | 多视图图片 |
| hunyuan3d | 3.0 | 文字生成模型 / Normal | 0 | 需要 | 模型 |
| hunyuan3d | 3.0 | 单图生成模型 / Normal | 1–4 | 不发送 | 模型 |
| hunyuan3d | 3.0 | 多视图生成模型 / Normal | 1–4 | 不发送 | 模型 |
| hunyuan3d | 3.0 | 文字生成模型 / Geometry | 0 | 需要 | 模型 |
| hunyuan3d | 3.0 | 单图生成模型 / Geometry | 1–4 | 不发送 | 模型 |
| hunyuan3d | 3.0 | 多视图生成模型 / Geometry | 1–4 | 不发送 | 模型 |
| hunyuan3d | 3.0 | 文字生成模型 / LowPoly | 0 | 需要 | 模型 |
| hunyuan3d | 3.0 | 单图生成模型 / LowPoly | 1–4 | 不发送 | 模型 |
| hunyuan3d | 3.0 | 多视图生成模型 / LowPoly | 1–4 | 不发送 | 模型 |
| hunyuan3d | 3.0 | 草图与文字生成模型 / Sketch | 1 | 可与草图一起发送 | 模型 |
| hunyuan3d | 3.1 | 文字生成模型 / Normal | 0 | 需要 | 模型 |
| hunyuan3d | 3.1 | 单图生成模型 / Normal | 1–8 | 不发送 | 模型 |
| hunyuan3d | 3.1 | 多视图生成模型 / Normal | 1–8 | 不发送 | 模型 |
| hunyuan3d | 3.1 | 文字生成模型 / Geometry | 0 | 需要 | 模型 |
| hunyuan3d | 3.1 | 单图生成模型 / Geometry | 1–8 | 不发送 | 模型 |
| hunyuan3d | 3.1 | 多视图生成模型 / Geometry | 1–8 | 不发送 | 模型 |

图片方向、格式、大小及具体参数仍由提交检查核对。多视图图片须先检查同一对象的比例和构造，再作为下一次模型生成的输入。

填写本地制作说明不等于发送了约束文字。发送记录与结果是否遵守要求分别检查。
