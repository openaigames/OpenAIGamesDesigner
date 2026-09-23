# Godot 执行配置

```json
{
  "godot": {"export_filename": "MyGame.exe", "export_mode": "debug"}
}
```

build / export 都需要 `--preset`，使用已有 `export_presets.cfg`；export_mode 支持 debug / release。输出名按目标平台填写（如 Linux 的 `MyGame.x86_64`、Web 的 `index.html`）。导出模板和平台 SDK 必须与工程匹配；输出文件存在不代表已独立试玩。


通用命令、状态与证据约定见 [执行总览](../execution.md)。


## 项目自己的命令

在 `.openaigame/project.json` 的 commands 中配置 prepare / smoke / test / play / build / export，可覆盖默认 Godot 动作；执行前仍核对实际 Godot 版本。doctor 保持内置检查。命令以参数数组传入，使用 `{project}`、`{run}`、`{output}`，不经 shell 拼接。

自定义 test 不要求 `--script` 或 GDScript 标记，须提供实际的 `{run}/test-results.json`（tests>0、failed=0、errors=0），并保留原始测试依据。自定义 build/export 不要求导出预设，须在 `{output}` 目录生成非空产物。非零退出、错误或缺少报告/产物不能通过；原生 GDScript 路线仍使用原来的断言标记。
