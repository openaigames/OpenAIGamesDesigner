# UE 网格资源原生测试

使用独立空内容工程和 UE 自带 Sphere，不读取或修改游戏地图。需要本机 Unreal Editor、PythonScriptPlugin 和 EditorScriptingUtilities。先通过 `tools/engine_workflow.py create` 建立独立工程，再运行：

```powershell
python tests/fixtures/unreal-mesh-resources/check_native.py --project "D:/Tests/MeshResources"
```

脚本经现有 runner 执行 baseline inspect → 创建测试地图与两种派生网格 → 新会话重开 inspect。验证三级 LOD 的真实面数、Nanite 设置持久化、源读回不变、场景消费者与实例化候选。结果位于测试工程 `mesh-native-validation-1/verification.json`，原始证据保存在 `runs/engine-*`。

已有证据目录时拒绝覆盖；失败先查看报告及日志。仅在确认尚未产生测试资产时可用 `--attempt 2` 保留新证据；已有资产则使用新的独立项目或明确处理失败现场。不要把该路径指向生产工程。测试不验证真实地图视觉、植被风动、帧时间或完整游戏性能。
