# 动作配置与调度接口

本页面向接入工具的开发者。共享看板提供资产库、生成服务和生成任务，不提供片段编辑页面。动作配置、草案校验及应用接口保留，实际动作检查使用引擎原生工具和 [动作记录 CLI](README.md)。

## 接入顺序

1. 读取实际素材长度、轨道绑定和游戏参数，让项目组件消费同一份 `action-sequence/1` 配置。
2. 在登记文件中列出已实现的可编辑字段。通过 `GET /api/action-editor` 读取配置，通过 `POST /api/action-draft` 保存草案，通过 `POST /api/action-apply` 应用；调用者须沿用当前会话、同源与 CSRF 校验。
3. 核对草案和正式配置的版本。应用前的配置保留在项目历史中；冲突时重新读取并比较，不能自动覆盖。
4. 在引擎重新执行动作，检查连续输入、中断、声音和限制解除，用新录制的实际结果比较。旧录像不会随配置修改而更新。

## 项目接入

项目登记文件：`.openaigame/action-editor.json`。

```json
{
  "schema":"action-editor/1",
  "actions":[{
    "id":"landing",
    "title":"落地动作",
    "engine":"godot",
    "file":"game/config/landing.json",
    "editable":{"pose":["start_s","source_in_s","source_out_s","rate","blend_in_s","blend_out_s"],"footstep":["start_s","volume"],"recover":["time_s"]},
    "consumer_note":"落地组件读取这份配置。",
    "references":[{"label":"原版实录","run":"已导入的记录编号","start_s":2.1}]
  }]
}
```

`editable` 只列出当前消费者确实使用的字段。引擎枚举为 `unreal`、`unity`、`godot`、`threejs`、`phaser`、`web`。看板不执行登记文件中的命令，不提供任意脚本执行接口。

配置示例见 [landing-sequence.json](landing-sequence.json)。时间单位为秒。每个片段引用一个素材；素材登记实际时长、类型和项目绑定名。声音额外提供项目内 WAV 路径 `preview` 和 SHA-256。配置接口不能把已登记的绑定换成任意资源或更换骨架。

片段时长为 `(source_out_s - source_in_s) / rate`。`blend_in_s` 从片段开始计算，`blend_out_s` 是片段结束前的退出过渡区间。两者之和不能超过片段长度。声音的速度参数同时改变音高；调度接口没有变速保调处理。

窗口与事件由项目解释。例如交互允许区间、受击取消区间、落地恢复、弹药提交都可以使用同一格式，不预设武器或玩法类型。窗口结束和提交事件独立修改，项目需检查它们之间的约束。

## 各引擎如何读取

| 引擎 | 配置调度接口 | 项目需要绑定 |
|---|---|---|
| UE5 | `FActionSequenceRuntime::Load/Start/Advance/Stop` | 动画实例、音频组件、规则；可在 C++ 中调用，再向蓝图提供项目接口 |
| Unity | `ActionSequencePlayer` | Animator 或 Playables、AudioSource、规则；在 Update 中传入动作经过的游戏时间 |
| Godot | `ActionSequencePlayer` | AnimationPlayer 或 AnimationTree、AudioStreamPlayer、规则；在 `_process` 或项目固定更新中推进 |
| Three.js | `ActionSequence` / `bindSequence` | AnimationMixer/Action、声音、规则 |
| Phaser | 同一网页接口 | Sprite 动画、声音、规则。二维帧动画未实现骨骼混合时，不应开放骨骼过渡字段 |
| 其他网页框架 | 同一网页接口 | 当前框架的动画、声音和规则对象 |

调度器发出 `clip_start`、`clip_exit`、`clip_end`、`clip_cancel`，以及窗口和瞬时事件。开始动画时使用素材入点和播放速度；进入/退出过渡由项目的动画混合实现。声音使用入点、速度与音量，在过渡区间设置增益并在结束或取消时停止。不能把调度器回调本身当成画面已正确混合。

同一个游戏时刻只推进一次。跳过一帧时会按时间顺序发出经过的事件，倒退时间不会重放；重新开始或寻址需要停止并重新初始化。取消会停止活动片段并发出 `window_cancel`，项目必须解除相应限制。取消与完成不同。事件回调可以停止动作；不要在回调内再次开始同一调度器，下一次游戏更新再开始。

动画覆盖、混合层、根运动、武器接触和网络预测继续由引擎控制。登记前验证这些绑定，再决定开放哪些参数。多个动画在同一轨道重叠需要消费者明确支持混合，配置接口只修改已登记片段，不自动添加动画层或重写原生动画资源。

## 验证范围

配置检查与调度接口覆盖表中所列引擎。调度接口提供读取和回调，不是适配所有项目的完整角色控制器。跨引擎测试应分别记录：配置调度测试、真实动画/音频绑定测试、实机录像和实际听音。单个项目的实测不能替代其他项目或引擎的接入验收。

浏览器试听使用导出的声音文件；最终混音、引擎音频延迟、空间化和并发效果必须在游戏中检查。同步记录显示的是实际采样时刻，不能据此声称逐采样同步或联机验收完成。

原生测试场景可通过 [实时预览接口](PREVIEW.md) 接收草案并回传实际画面、版本和事件。随包提供 Godot 桥接，须由自定义客户端连接已登记且在线的测试场景。预览与保存正式配置分开；其他引擎需实现对应桥接或使用录像与重跑流程。
