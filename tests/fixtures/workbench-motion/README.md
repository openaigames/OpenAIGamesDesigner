# 动作看板联调夹具

`generate.py` 在 Blender 内运行，输出到新目录：

```sh
blender --background --factory-startup --disable-autoexec --python-exit-code 1 --python tests/fixtures/workbench-motion/generate.py -- /absolute/new-fixture
python tools/project_workbench.py --project /absolute/new-fixture --view review
```

形状、骨架及动作均为脚本原创，专门检查直接 glTF、同名片段、纯动作 FBX 配角色、角色绑定与关联预览。`mapped-native.uasset` 是明确标注的接口占位文件，不可导入 UE；这项验证只覆盖浏览器映射，不证明 Unreal 原生导出或动作品质。

检查保存、角色/动画/预览角色切换、未保存取消、刷新、导航、导出与双窗口冲突；从原始历史核对实际动作路径及上下文。改源或绑定后，原判断应失效且仍保留备注。不能把测试形状当作推荐游戏资产。
