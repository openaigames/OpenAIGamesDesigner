# Unreal 执行配置

```json
{
  "unreal": {
    "smoke_map": "/Game/Maps/Prototype",
    "smoke_seconds": 3,
    "test_filter": "MyGame.Combat",
    "dotnet_executable": "D:/UE/Engine/Binaries/ThirdParty/DotNet/VERSION/win-x64/dotnet.exe",
    "platform": "Win64",
    "configuration": "Development",
    "build_target": "MyGameEditor",
    "export_maps": ["/Game/Maps/Prototype"]
  }
}
```

prepare 临时启用引擎的 PythonScriptPlugin 来执行只读检查脚本，不写入 `.uproject` 插件设置，不保存 Actor。实际工程路径和版本写入 `unreal-result.json`。smoke 使用 `-game -NullRHI`，必须有指定 World 启动与引擎初始化日志；它不验证画面、动画质量或手感。

test 只运行明确的 Automation 过滤范围，保存 `automation/index.json` 并归一化；未执行、执行中、失败或零测试不能当作通过。编译调用匹配引擎的 UnrealBuildTool.dll，导出调用 AutomationTool.dll 的 BuildCookRun；需要匹配的 .NET、编译工具链、SDK、平台支持和可打包的工程。build_target 为实际 Target 名，纯内容工程不要凭空填写 Editor Target。

Automation 报告与整个编辑器进程分开判定：报告通过但启动日志有错误时，仍保留整轮失败及原始报告，排查错误来源后再验收，不自动忽略错误行。

默认导出是游戏客户端路线；服务器、分布式构建、特殊签名/商店发布使用工程自己的命令覆盖。默认 test / smoke 的 NullRHI 不适合 GPU 测试，需要这类测试时覆盖命令并保留实际报告。GAS 是项目技术选择，不是启动或构建的强制依赖。


通用命令、状态与证据约定见 [执行总览](../execution.md)。
