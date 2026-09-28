# v0.2.1 验证材料

这些材料保存实际执行结果及其适用范围，随源码和共享 runtime 分发。它们是验证归档，不是当前安装的文件清单；当前包的版本和完整性以 `game-preproduction/runtime/bundle-manifest.json` 为准。

| 材料 | 对应范围 |
| --- | --- |
| [完整回归日志](integration-tests.log) | 初始整合提交 `a7ad9a9845a32338a979304e52e2d4b01d577dc5`：289 项 Python、4 个 Node 脚本；不代表所有后续修订自动通过 |
| [Blender 日志](blender-tests.log) | 初始整合使用 Blender 4.5.9 的 6 项回归，包含 3 项真实工具往返 |
| [Skill 格式检查](skill-format-validation.log) | 初始整合的十五个 Skill 入口格式检查 |
| [独立行为推演](skill-forward-evaluation.md) | 16 个专业情境；包含输入哈希、发现、修正记录与非盲测限制 |
| [分发验证摘要](portable-summary.json) | 初始整合包的独立 CLI、完整性及兼容读取结果；省略个人机器路径，保留原记录哈希 |
| [文档修订回归](documentation-tests.log) | 2026-09-28 文档修订：295 项 Python、4 个 Node 脚本，包含完整安装、章节锚点及旧测试场模块保护 |
| [修订后的 Skill 格式](documentation-skill-format.log) | 同次修订的十五个 Skill 入口格式检查 |

详细输入、实施范围、浏览器人工操作结果和未覆盖项见 [版本验证记录](../../validation-v0.2.1.md)。浏览器操作结论为维护者观察记录；自制夹具可重建，但文件生成不等于重新执行了界面观察。

当前数值策划拆分及十六职业检查见 [数值策划验证](numerical-design-validation.md)，其针对性回归与行为检查单独记录。
