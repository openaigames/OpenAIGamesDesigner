# 资产输入示例

[English](README.md) | [简体中文](README.zh-CN.md)

复制一组要求和方案到游戏项目，按真实需求修改，再使用[输入准备工具](../../adapters/assets/input-preparation.zh-CN.md)。示例是可编辑起点，不是已批准请求；核对项故意保留为 false。

| 文件组 | 示例内容 |
| --- | --- |
| [crate.spec.json](crate.spec.json)、[crate.plan.json](crate.plan.json) | 文生模型要求与明确排除项 |
| [door.spec.json](door.spec.json)、[door.plan.json](door.plan.json) | 外观要求与待验收的尺寸、转轴和碰撞 |
| [icon.spec.json](icon.spec.json)、[icon.plan.json](icon.plan.json) | 图像输入与小尺寸 UI 检查 |
| [impact.spec.json](impact.spec.json)、[impact.plan.json](impact.plan.json) | 音效描述与独立的游戏内时序检查 |
| [speech.spec.json](speech.spec.json)、[speech.plan.json](speech.plan.json) | 台词逐字保留，voice_id 须改为有权使用的声音 |
| [video.spec.json](video.spec.json)、[video.plan.json](video.plan.json) | 镜头、光照和排除项 |

参考文件必须真实存在于项目。要求文件记录路径和职责，方案明确是否发送，reference 路径的要求记录实际观察。不要虚构图片依据，也不要把生成视图当成已经验证的几何。
