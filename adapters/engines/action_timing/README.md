# 动作时间记录

用于检查输入、规则、动画和声音触发之间的实际关系。交互、移动、攀爬、施法、近战、射击、载具与界面反馈均可使用；这里不预置某类游戏的规则。

| 引擎 | 安装目录（相对引擎工程） | 原生接入 |
| --- | --- | --- |
| UE5 | `Plugins/ActionTiming` | Actor Component、蓝图函数、Anim Notify、Insights Bookmark |
| Unity | `Assets/ActionTiming` | MonoBehaviour、Animation Event、项目规则回调 |
| Godot 4 | `addons/action_timing` | Node、AnimationPlayer 方法轨道、项目规则回调 |
| Three.js | `src/action-timing` | ES Module、AnimationMixer finished / loop |
| Phaser | `src/action-timing` | ES Module、Sprite animationstart / animationcomplete、Scene shutdown |
| 其他网页框架 | 项目脚本目录 | 无渲染依赖的 ES Module；在真实事件回调调用 record |

```text
python tools/action_workflow.py install --engine unreal --out <UE工程>/Plugins/ActionTiming
python tools/action_workflow.py install --engine unity --out <Unity工程>/Assets/ActionTiming
python tools/action_workflow.py install --engine godot --out <Godot工程>/addons/action_timing
python tools/action_workflow.py install --engine threejs --out <网页工程>/src/action-timing
```

安装仅复制记录器源码，已有不同内容的同名文件会报错并保留。UE 需启用插件、编译；C++ 使用记录器的模块添加 `ActionTiming` 依赖。Unity/Godot 需把组件加入实际执行动作的对象。发布构建默认不开始记录，无后台上报。

## 在真实动作中接入

1. 在待测动作开始处启动记录，填写动作名、工程版本、来源、输入方式与输入脚本说明。
2. 在输入回调、规则真正变化、动画事件、声音播放请求处分别记录。每项调用取当时的单调时钟，包含暂停与时间缩放产生的真实等待。
3. 正常结束调用 StopAndSave / stop_and_save / stop；取消是否属于正常完成由当前任务测试定义。例如“取消换弹测试”可以完成，但意外关闭场景保存为未完成。
4. 导出 JSON，复制进游戏项目，再用下方 CLI 登记。

UE/Unity 接口：`StartRecording(action, revision, source, inputMode, inputDescription)`、`RecordEvent(track, eventName, uncertaintySeconds)`、`StopAndSave(complete)`。Godot 使用同名的小写下划线形式，启动和记录返回 Error，需要检查。所有原生接口在主线程调用。

UE 添加 `Record Action Event` Anim Notify，设置轨道和事件名；Notify 会找 Mesh 所属 Actor 上的记录器。普通通知触发取决于动画权重、混合和引擎配置。规则是否生效仍应由规则执行位置记录。启用 Animation Insights 后可配合 Rewind Debugger 查看姿态与状态；记录器也写 Insights Bookmark，需在引擎开启 bookmark trace 通道。它没有创建自定义 Rewind 轨道。

Unity 在 Animation Event 中调用 `RecordAnimationEvent` 并传事件名；事件接收对象应与记录器所在对象一致。Animator 状态回调在项目实际进入/退出时调用 `RecordEvent`。组件禁用时会保存未完成记录。

Godot 将 AnimationPlayer 方法轨道指向 `record_animation_event`；AnimationTree 状态切换由实际状态决定位置记录。Node 离开场景树时保存未完成记录。默认写入 `user://action-timing`，可通过 `output_directory` 改到开发工程中；导出游戏不要写只读的 `res://`。

网页示例：

```javascript
import {ActionRecorder, observeThreeMixer} from './action-timing/action-recorder.mjs';
const recording = new ActionRecorder({
  engine: 'threejs', engine_version: THREE.REVISION,
  action: 'interaction', revision: buildRevision, source: 'player interaction callbacks',
  input_mode: 'software', input_description: 'interaction-check-v1'
}).start();
recording.record('input', 'activate');
const detach = observeThreeMixer(recording, mixer, 'character');
// 在规则真正提交的回调中：
recording.record('logic', 'commit');
const capture = recording.stop(true); // 同时移除本次注册的监听
recording.download();                 // 或把 capture 交给项目自己的保存接口
```

Phaser 使用 `observePhaserSprite(recording, scene, sprite, track)`；场景 shutdown 会终止并标记未完成，解除监听。其他网页框架只用 ActionRecorder 即可。浏览器失焦、页面挂起可能延迟事件，记录显示实际回调时间。不同 Actor、Sprite 或动画实例应使用不同轨道或独立记录器；单个 Mixer 的观察器记录其全部完成/循环事件，不能据此分辨未单独标识的动作实例。

## 文件与检查

UE：`Saved/ActionTiming/*.json`。Unity：`Application.persistentDataPath/ActionTiming/*.json`。Godot：打印实际保存路径。网页：下载或项目自己的保存接口。JSON 是 `action-events/1`，单位为秒，`zero_s` 为 0。引擎版本、动作名、工程版本、输入说明、完成状态与丢失数必须保留。

轨道和事件名称使用字母、数字及 `_ . : / -`，最多 120 字符。每次记录从 1 编号：`commit#1`、`commit#2`；设定文件引用带次数的名称。新一轮会清空计数；重复开始会报错。每轮上限 10,000 个事件，溢出累计 dropped_events，检查不会显示通过。它适合离散事件，逐帧数值请使用已有响应采样工具。

```text
python tools/action_workflow.py import --project <游戏项目> --capture production/timing/capture.json --spec production/timing/spec.json --title "交互动作 · 修改后"
python tools/action_workflow.py compare --project <游戏项目> --a <原记录编号> --b <新记录编号>
```

设定格式见 [通用动作时间轴](../../../skills/game-animation-pipeline/references/action-timeline.md)。可以只导入实际记录，结果标明未设定检查标准，不会自动以实测值生成合格标准。没有录像也能检查事件，不能据此验收观感；声音触发时刻不代表声音实际出声时刻。

看板保存事件和设定的副本、原路径和 SHA-256。录像可选，填写项目内 MP4/WebM 和录像中动作零点；录像需在播放器中核对。录像保留原文件引用及哈希，文件改变后拒绝作为旧录像播放。结果文件保存在 `.openaigame/action-runs/<编号>/run.json`。导入、筛选、对照和导出不改引擎动作配置。看板使用既有会话、同源与 CSRF 校验，不开放跨域游戏上传接口。

对照检查动作名、时钟、输入方式和输入说明是否相同；这些条件来自记录声明，不能证明两次人工输入、硬件或网络完全一致。多机时钟没有自动对齐，必须另外记录同步依据并做真正的联网测试。

## 原生编辑与调试工具

- UE：[Rewind Debugger](https://dev.epicgames.com/documentation/en-us/unreal-engine/animation-rewind-debugger-in-unreal-engine?application_version=5.4)，保留引擎动画与姿态观察。
- Unity：[realtimeSinceStartupAsDouble](https://docs.unity3d.com/2022.3/Documentation/ScriptReference/Time-realtimeSinceStartupAsDouble.html)，记录真实时间；Animator/Animation 继续负责动作编辑。
- Godot：[Time](https://docs.godotengine.org/en/stable/classes/class_time.html)，使用单调时钟；AnimationPlayer/AnimationTree 负责动作与混合。
- Three.js：[AnimationMixer](https://threejs.org/docs/#api/en/animation/AnimationMixer)。
- Phaser：[动画事件](https://docs.phaser.io/api-documentation/4.0.0/namespace/animations-events)。

引擎的编辑时间、游戏模拟时间、真实经过时间、录音/录像时间不能混作同一个时钟。新版引擎或目标平台接入后应先做本地小场景测试，再接入正式动作。

## 自定义配置与预览客户端

共享看板没有动作检查及片段编辑页面；[编辑与引擎接入](EDITING.md) 提供自定义客户端所需的协议与调度接口。记录器和 CLI 继续保存真实运行结果。
