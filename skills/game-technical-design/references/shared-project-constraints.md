# 项目制作标准与实际使用方

共用尺度、移动和时序依据。角色碰撞尺寸、门洞净空、镜头视点、动作位移和关键事件不应由每个职业各填一份新数值。作者源仍是项目配置、原生数据资产或已有规格；使用时引用具体位置，区分目标、素材默认、暂定估计和工程实测。

需要跨专业查询时，在已有 `design/` 中建立轻量引用表（例如 `design/project-links.json`），并在 `.openaigame/project.json` 的 `links_spec` 中指向它。字段按 runtime `schemas/project-links.schema.json`：对象 ID 与规则、引擎对象、动画、VFX/音频事件、空间和问题之间使用显式链接；每条约束指向源文件/定位符、单位、来源性质和确实消费它的对象/代码/检查。

源码工具在 `tools/project_links.py`，安装版在 `game-preproduction/runtime/tools/project_links.py`：

```sh
python tools/project_links.py --project MyGame inspect --spec design/project-links.json
python tools/project_links.py --project MyGame snapshot --spec design/project-links.json --id before-move-change
python tools/project_links.py --project MyGame impact --id before-move-change
```

JSON 主源用精确 JSON Pointer 定位，不因同文件中的无关字段变更废弃全部结论。原生资产或文档按文件版本提示待核查，不解码猜值；原生参数另用引擎读回证明。比较快照只是历史依据，不是新的编辑主源。使用方必须有存在的文件、明确对象和检查名称，不从文件名或职业名称猜依赖。

制作时沿三个关系检查：

- 尺度：门框外观替换后核对真正碰撞净空、角色胶囊、视点高度和对应通行路线；网格包围盒不能证明可通行。
- 移动：速度或加速度改变后，检查实际路线时间、停距、视角变化和追击窗口。保留正常输入与传送辅助的区别。
- 时序：动作提交/取消窗口改变后，复核判定、武器轨迹、音效/VFX/UI 的开始和清理，按事件 ID 关联同次运行，而不是各职业各选一段视频。

把影响结果关联原任务的对象和检查，保留不受影响的构建证据。新值必须从实际运行使用方读回；链接表不能自动证明绑定有效或数值合适。
