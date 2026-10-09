# 原生参数与曲线读写

使用现有 `engine_workflow execute` 和会话检查点。原生 DataAsset/CurveFloat 继续作为编辑主源；请求与结果 JSON 是交换和证据，不要求把游戏改成 JSON 驱动。

`inspect` 请求可加 `native_reads`，每项给出 id、path 和需要读取的 properties。CurveFloat 使用 `curve_times` 取得指定时间的原生求值，不宣称这些样本等于完整曲线键或实际运行值。

```json
{"engine":"unreal","mode":"inspect","native_reads":[
  {"id":"hero","path":"/Game/Data/Hero","properties":["move_speed","commit_delay"]},
  {"id":"damage","path":"/Game/Data/DamageCurve","curve_times":[0,0.1,0.2,0.3]}
]}
```

已授权修改使用 edit 的 `native_patch`，expected 取刚读回的原值，values 只包含当前任务需修改字段：

```json
{"engine":"unreal","mode":"edit","operations":[
  {"op":"native_patch","path":"/Game/Data/Hero",
   "expected":{"move_speed":500.0},"values":{"move_speed":550.0}}
]}
```

工具在写前做精确基线比较；保存前读回并按原生浮点精度核对当前任务字段。复杂数据和曲线键通过项目自己的 UFunction 导出/导入：读取项使用 `read_method`；写入项同时给出 `read_method`、`write_method`。只读方法返回完整 JSON 对象字符串，写方法接受当前任务变化的 JSON 字符串并返回 bool，项目负责字段范围、曲线键、插值和事务。不得把任意未知方法当安全导入器。

expected 必须等于整个项目导出快照；values 是其中被授权改变的字段子集，写后导出需包含对应结果。失败不自动重放：查看会话副作用和检查点，必要时用原有恢复入口。导出器不能偷偷修复、保存或创建资源。

保存执行记录为 `native_asset_saved`。随后必须启动**另一次 inspect 会话**，从磁盘重新加载并核对；再让真实游戏使用方运行，使用共享观察记录最终生效值和覆盖条件。单次 UObject 读回不叫磁盘重载，作者值正确也不证明运行实例正确或手感达标。

引擎版本/插件差异可能使某些属性不可反射；此时显示具体读取失败，改用项目已验证的只读接口，不强行替换原生资源格式。
