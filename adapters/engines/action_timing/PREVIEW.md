# 原生动作预览开发接口

本页描述 `action-preview/1` 协议，供开发者接入自定义客户端。共享看板没有原生动作预览页面。正式配置、预览草案和历史记录分别保存；画面必须来自引擎实际渲染。

随包提供 Godot 4 的 `godot/action_preview_bridge.gd` 和可选的 `godot/action_preview_consumer.gd`。UE、Unity 与网页项目需自行实现并验证对应桥接，或使用应用配置、重跑和录像检查。

## 接入流程

1. 建立独立测试场景，引用项目角色、武器、动画驱动、音频与挂点，隔离正式对局、AI 与伤害提交。
2. 启动场景后，客户端通过 `GET /api/action-preview-status?id=<动作ID>` 查询连接，通过 `POST /api/action-preview-command` 发送草案和控制请求。请求使用看板会话、同源与 CSRF 校验。
3. 等待引擎确认运行编号和配置摘要，再显示对应画面与事件。“已发送”不代表引擎已应用。暂停、速度与机位控制作用于测试场景，不改写正式配置。
4. 通过 `POST /api/action-preview-record` 保存一次实际运行记录。回传图片不自动合成录像；需要回放时由引擎录制并关联文件。
5. 正式应用使用 [配置接口](EDITING.md)，之后重新运行，检查移动、连续输入、打断与状态恢复。

声音由本机 Godot 进程输出，消费者同步处理音频暂停与变速。回传画面约 8 fps，不承诺低延迟音画同步；最终品质须实际观看和监听。

## 登记

在已有 `.openaigame/action-editor.json` 动作条目中增加：

```json
"preview": {"protocol":"action-preview/1", "consumer":"player_lab"}
```

保留 `file`、`engine`、`editable` 等已有字段。`consumer` 是测试场景的稳定 ID，须与桥接组件一致。登记文件没有可执行命令、可执行文件路径或任意脚本入口；看板不负责启动引擎。启动方式由项目现有工具提供。

把桥接组件加入测试场景前设置 `project_root`（包含 `.openaigame` 的项目根）、`consumer_id`、`action_ids`、`views`、`host`，可指定回传用的 `viewport`。不要把桥接组件挂进正式发布场景。

## 消费者接口

| 方法 | 责任 |
| --- | --- |
| `preview_load(sequence) -> Dictionary` | 取消上次动作，实际读取和绑定草案，返回 `{ok:true, sequence:实际读取的配置}`；失败返回 `{ok:false,error:说明}` |
| `preview_advance(delta)` | 推进一次动作时间，驱动实际 AnimationPlayer/AnimationTree、声音和测试规则 |
| `preview_state() -> Dictionary` | 返回实际 `elapsed_s`、`duration_s`、`complete`；可附动画名、位置、音频播放状态、IK 或武器测量结果 |
| `preview_cancel()` | 取消动作，停止声音，解除测试窗口和临时状态 |
| `preview_transport(paused, speed)` | 把暂停、变速传给音频等独立时钟；桥接组件只控制动作推进时间 |
| `preview_view(id) -> bool` | 使用场景提供的真实机位；仅成功时确认 |

在真实播放、声音和规则触发位置调用 `bridge.record_event(track, name)`。确认配置已读取不等于姿态、IK 或混合已通过；桥接组件负责运输和记录，消费者负责实际表现。

可选示例消费者支持每个轨道对应一个 AnimationPlayer，动画绑定为 `轨道ID:动画名`；`animation_players`、`rest_animations`、`audio_streams`、`cameras` 由项目显式设置。同轨重叠片段会拒绝，避免假装支持混合。复杂 AnimationTree、根运动、双手 IK 和玩法事件应接入项目自己的消费者。骨架动作、手指握姿、蒙皮和模型编辑仍在源工具或引擎完成。

## 会话与结果

所有交换文件位于项目 `.openaigame/action-preview/<consumer>/`：

- `ready.json`：引擎实例身份、支持动作、机位和控制能力；超过 4 秒没有更新视为离线。
- `request.json`：带实例、客户端身份、动作、操作、唯一请求与运行编号的最新命令。
- `client.json`：客户端心跳；客户端断开或超过 7 秒没有心跳时，消费者取消预览。
- `status.json`：引擎实际确认的运行编号、配置 SHA-256、执行状态、事件、姿态读回和帧编号。
- `runs/<run>/sequence.json`：该次草案快照；`capture.json` 是原生事件与配置快照；两个 PNG 文件交替保存实时画面。

实例重新启动后旧命令不能生效；旧帧、旧运行和其他动作不能确认当前草案。一个消费者同时由一个客户端控制，其他客户端会得到明确提示。正式配置被别处修改时必须重新载入，旧草案不会直接覆盖新版本。

历史事件使用单调实时时钟，包括暂停和测试变速的影响；暂停、机位与速度等操作另存于 `preview_controls`。不同交互条件不会被自动当作同条件比较。配置快照证明运行版本，不能代替资产来源、视觉与听感验收。

接口服务需在更新后重新启动以加载代码。该协议不改变资产库页面或模型预览控件。
