# Godot 原生制作与观察夹具

这是工具包自制的工程验证场景，使用原创几何和可编辑的合成音配方；许可沿用仓库 LICENSE。不代表动作游戏成品美术或已经获得听感认可。

把本目录复制到隔离项目，再复制 `adapters/engines/godot/OAGDObservation.gd` 到项目根。Godot 4.7.2 实测；其他版本先运行导入与测试。方向键移动、空格攻击、Esc 取消、Restart 按钮重试。场景使用实际 CharacterBody2D、碰撞形状、射线命中、Camera2D、Control 和 AudioStreamPlayer。攻击弧线的半径与射线范围相同。

自动模式使用真实游戏处理函数驱动移动/攻击/取消，并通过 InputEventAction 操作已聚焦的重试按钮；不冒充人类试玩或物理键盘延迟。依次验证移动、命中、取消、再次攻击、目标清除、碰撞约束和重试恢复。输出 `capture.json` 与包含实际断言的 `test-results.json`。

```powershell
Godot.exe --headless --path <隔离项目> -- --automated --cleanup-delay=0 --output=<隔离项目>/runs/test/capture.json
Godot.exe --path <隔离项目> -- --automated --cleanup-delay=0 --capture-media --output=<隔离项目>/runs/media/capture.json
```

先创建对应输出目录，每次使用新目录。共享 `game_workflow run` 自动建立运行目录及版本记录，可把以上 argv 配置为项目 commands 的 test/play。默认 cleanup_delay=.075 故意保留短暂特效/持续音，用于对照；`--cleanup-delay=0` 立即清理。记录实际游戏时钟差值，不把设定值当作测量值。

可视模式生成带实际游戏时间锚点的 PNG 和主音频总线 mix.wav。音频开始锚点是开启录制时的估计，非硬件同步测量；截图读回有性能开销。声音包含命中主体与持续状态两层，必须实际监听后单独记录听感，不能依据 wav 存在、播放状态或自动断言批准品质。

连续动作的独立场景为 `continuity.tscn`：原生移动/停步→攻击→后闪取消→受击中断→恢复→缓存后续攻击→清理。用 `Godot.exe --path <项目> res://continuity.tscn -- --cleanup-delay=0 --capture-media --output=<新目录>/capture.json` 运行，**不传 --automated**（避免同时启动主场景的短流程）。该场景调用实际处理函数、保留碰撞移动和逐帧图，四项原生断言检查动作链；几何角色验证运动/状态衔接，不证明人形骨骼动画自然。短音频监听仍使用主场景的独立采集与评审。
