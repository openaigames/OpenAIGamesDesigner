# 配置和扩展适配器

优先使用已有项目工具，通过配置接入；只有格式或执行语义不同才新增适配器。workflow 保持通用，GAS、Lyra、具体玩法和引擎版本的方法留在相关 Skill 参考里。

## 引擎命令

网页游戏使用 Three.js（3D）或 Phaser（2D），支持空工程初始化、依赖安装、本地 Vite 服务与构建导出；接入、测试和持续进程说明见 [网页游戏](engines/web.md)。网页浏览器验证需要真实项目命令或实际试玩，构建不会自动批准体验。

Godot 保留专用命令实现。Unity/Unreal 通过 `.openaigame/project.json` 的 commands 接入项目实际脚本。例如已初始化的 Unity 项目可以补充：

```json
{
  "schema_version": 1,
  "engine": "unity",
  "engine_root": "game",
  "editor_executable": "C:/Tools/Unity/Editor/Unity.exe",
  "commands": {
    "test": ["C:/Tools/Python/python.exe", "C:/MyTools/unity_tests.py", "--project", "{project}", "--run", "{run}"],
    "export": ["C:/Tools/Python/python.exe", "C:/MyTools/unity_build.py", "--project", "{project}", "--output", "{output}"]
  }
}
```

包装脚本需由项目实际提供；示例不是可直接运行的 Unity 构建器。Unreal 配置 engine 为 unreal，并加相对 engine_root 的 `project_file`，如 `MyGame.uproject`。`expected_version` 可检查工程声明的版本，Unity/UE 不由此证明编辑器实际版本一致。

只展开 `{project}`（原生工程根）、`{run}`（本次记录目录）、`{output}`（本次导出目录），其他参数原样保留。首项是绝对可执行文件，进程 cwd 是原生工程根，shell=False。传入 .uproject 时使用真实文件名，不把 `{project}` 当文件路径。命令来自已配置的项目，不解析 Markdown 来执行。

| 动作 | Godot | Unity | Unreal |
| --- | --- | --- | --- |
| doctor | 调用二进制版本 | 工程结构及声明版本 | uproject 及声明版本 |
| prepare | 导入 | 编辑器批处理导入 | 项目配置命令 |
| smoke | 有限帧无画面启动 | 项目配置命令 | 项目配置命令 |
| test | Godot 测试脚本 | 项目测试包装命令 | 项目测试包装命令 |
| play | 运行工程 | 打开编辑器，不自动 Play | 编辑器 -game 启动 |
| build | 使用 export | 项目构建命令 | 项目构建命令 |
| export | Windows debug 导出 | 项目打包命令 | 项目打包命令 |

命令未配置时输出 blocked 记录，不能模拟成功。build 只检查命令条件；要登记完整交付文件使用 export。Unity 的批处理不自动拥有项目构建方法，通常需要项目侧的 executeMethod；UE 构建与打包需按项目版本选用实际 UBT/UAT 路线。

test 包装脚本应执行实际测试、保留引擎原始报告，并在 `{run}/test-results.json` 写 `{"tests":3,"failed":0,"errors":0}`。三个值必须是整数，tests > 0、失败和错误都为 0 才通过技术检查。退出码为 0 但没有结果、零测试或格式错误都不通过。不能为了通过运行器手写一个虚构结果。

export 必须在 output 内真正生成非空交付文件；运行器登记文件哈希。项目包装脚本负责完整性检查和将引擎失败转换为非零码，日志识别只是补充。所有动作有超时和日志；玩法与视觉验证始终另记，不因 exit 0 自动通过。

## 新的提供方与记录

资产命令协议见 [资产接入](assets/README.md)。新增原生服务适配器时实现 command/validate，注册到工具中，并更新 provider 枚举、能力文档和失败场景测试；不要只加一个不能调用的空文件。Blender 处理器同样走资产任务记录。

schema 文件是记录格式的维护来源。`validate_records.py` 使用标准库解释这些 schema 用到的有限关键字，遇到不支持的关键字报错；它不是通用 JSON Schema 实现。扩展契约时同时更新解释器和测试，保留版本兼容与迁移说明。记录检查覆盖文件存在性、路径范围和已有哈希，不执行工具或核实专业结论。

源码的 `tests/adapters/` 保存适配器合同样例；根级测试入口统一运行它们。新增能力先用可控本地进程检查缺配置、非零退出、错误输出、超时和产物缺失，再按 [验证计划](../tests/README.md) 接真实工具。打包后在无源码依赖的目录再次调用 CLI。

依据：[Unity 编辑器命令行](https://docs.unity.com/en-us/engine/6000.7/manual/unity-editor/command-line-arguments/editor)、[Unity 项目构建方法](https://docs.unity.com/en-us/engine/6000.6/manual/building-and-publishing/build-customize-build-pipeline/build-command-line)、[Unreal 构建与打包](https://dev.epicgames.com/documentation/unreal-engine/build-operations-cooking-packaging-deploying-and-running-projects-in-unreal-engine)。实际命令以项目安装版本为准。
