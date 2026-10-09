# 动画证据 /2：三种入口与显式绑定

`scripts/anim_pipeline.py` 通过同一 CLI 分派 /2，并保留 /1 原有外部回传要求。模式由真实来源决定，不能通过切换模式消除失败。

| mode | mode_basis.source_type | evidence_dependencies 必要角色 | 实际采样 |
|---|---|---|---|
| external | dcc_export | source_export、engine_import、runtime_consumer | 源求值与引擎 unreal_roundtrip 对照 |
| native_reuse | engine_native | native_source、binding_readback、runtime_consumer | 当前使用方 runtime_consumer，不要求虚构 FBX |
| local_change | existing_consumer | before_config、after_config、runtime_consumer | 改前/改后与受影响使用方，不要求无关 DCC 往返 |

每个依赖角色为实际工作区文件路径数组，包括原生资产、配置、真实会话、绑定采样和播放证据。检查文件身份不能替代评审其内容。mode_basis 另有 reason，说明实际来源和范围。

manifest /2 保留 clips、weapons、space、root_motion_owner。空间声明厘米和轴向。每招有 id/source_ref/duration_s；外部模式另有实际 fbx。无武器用 weapon:null，无接触不填 contact，没有脚部着地窗口标未测。

武器 attachment 明确 parent、kind（bone/socket/component）、配置 source 与相对变换 `{p,q,s}`。骨名从资源读取，手部测量骨、附件插槽和握柄标记各有用途；允许有依据的非零偏移，不默认 hand_r、weapon_r 或零旋转。q 为 x/y/z/w。

grips 以项目自定名称记录 bone、hand_marker、weapon_marker；两个 marker 均为局部 `{p,q,s}`，分别比较位置和方向。每招 grip_intervals 以握持名对应 `[开始秒,结束秒]` 数组；辅助手离柄不约束，重新握持有新窗口。未声明窗口标未测；声明窗口没有样本产生缺口。

foot_contacts 保留 bone/start_s/end_s。可选 contact 指定 time_s、bone、实际 target_marker，只比较同帧实测标记。tolerances 包含 binding_position_cm、binding_rotation_deg、grip_position_cm、grip_rotation_deg、comparison_position_cm、comparison_rotation_deg、sample_time_s、foot_slide_cm、contact_gap_cm，并有 tolerance_basis 说明项目校准。这些是定位阈值，不是统一艺术标准。

capture /2 的 context 记录 engine_version/execution_ref/method/sampling/conditions，execution_ref 指向实际会话文件。bones 保留真实名称和层级；每招 frames 有递增秒时钟、同一空间求值后的 pose，以及按需 weapon、attachment、markers。attachment 记录实际 parent/kind/exists/relative。缺附件、错误父级、纯旋转偏差、缩放偏差独立定位，不能把声明配置当运行采样。

```text
python anim_pipeline.py validate --manifest manifest.json
python anim_pipeline.py audit --manifest manifest.json --capture current.json --compare baseline.json --out reports/audit.json
python anim_pipeline.py gate --manifest manifest.json --report reports/audit.json --review review.json --out handoff.json
```

native_reuse 可省略 compare，其余需要真实对照。review /2 使用新清单/报告哈希、观察者、每招决定、播放文件及哈希、逐问题豁免。gate 仅核对声明范围的交接，不安装资产，不代表用户认可手感。手指变形、蒙皮接触与主观体验仍需实际播放评审。

升级 /1：根据实际绑定与区间写完整 /2 外部模式计划，运行 `migrate-v1 --manifest old.json --plan migration.json --out manifest-v2.json`。保留原件，新 review 清空为需重验；历史通过不能自动升级。来源或范围变化在任务中明确修订并保留旧失败。

旧 `assets/unreal/AnimationLab` 为 /1 程序武器样例，明确拒绝 /2；缺显式绑定时隐藏武器并拒绝采样。/2 接入实际项目使用方，复用 `engine_workflow.py` 的 Playback、事件与组件读回，不能将样例角色冒充指定角色。
