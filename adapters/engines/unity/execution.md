# Unity 执行配置

明确安装辅助脚本（安装两个 Editor 辅助文件，已有不同内容会拒绝覆盖）：

```sh
python tools/engine_setup.py --project "MyGame"
```

安装 `OAGDEngineBridge.cs` 与其共用构建依赖 `OAGDBuild.cs`。两份文件全部检查后才写入；已有不同版本或用户修改会拒绝覆盖，需要先比较、备份并明确升级。运行前也检查依赖是否齐全且匹配当前工具包。

```json
{
  "unity": {
    "smoke_scene": "Assets/Scenes/Prototype.unity",
    "smoke_seconds": 3,
    "test_platform": "EditMode",
    "test_filter": "MyGame.Tests",
    "build_target": "StandaloneWindows64",
    "build_scenes": ["Assets/Scenes/Prototype.unity"],
    "build_name": "MyGame.exe",
    "development": true
  }
}
```

`test_platform` 可选 EditMode / PlayMode，需要项目安装对应 Unity Test Framework 并包含实际测试。输出原始 `unity-tests.xml` 和标准化 `test-results.json`；零测试、失败及未知状态不能通过。异步测试不使用会提前退出的 `-quit`。

smoke / build / export 使用随包提供的 [辅助脚本](OAGDEngineBridge.cs)，记录实际工程、编辑器版本、错误与结果。smoke 检查进入并完成指定时长的 Play Mode，保存实际帧变化；不会保存或修改测试场景。运行前关闭同一工程的其他编辑器实例，避免工程锁；不会替用户强关编辑器。

Play Mode 检查后仍须确认编辑器进程正常结束。若进程持续挂起，运行器记录 timeout；即使辅助脚本报告成功，也不能将整轮执行记为通过。核查编辑器日志、版本与项目退出逻辑后重新验证。


通用命令、状态与证据约定见 [执行总览](../execution.md)。
