# Unity 制作接口

## 创建与启动

[production.py](production.py) 独立维护 Unity 的请求规则、工程创建、辅助文件安装和命令。需要 Windows、有效 Unity 许可证，以及制作独立 Player 时的 Windows Build Support。

```powershell
python tools/engine_workflow.py create --project "D:/Games/MyGame" --engine unity --editor "D:/Unity/Editor/Unity.exe" --name MyGame --brief "已确认的本轮范围"
```

调用 Editor 的 createProject 创建空工程，并加载核实实际版本。edit/inspect 使用 C# executeMethod；playback 构建独立 Development Player，再运行脚本操作。辅助文件通过安装哈希识别用户修改，仅在已有检查点且旧文件未被修改时升级。

定时操作和 PNG/帧耗时采样不代表真实键鼠链路或正式性能验收；录制会增加开销，测性能时单独关闭 capture_interval。Camera 离屏录制不包含独立 Overlay UI，也不包含音频。

公共入口与恢复：[会话管理](../sessions.md)。原生执行在 [OAGDProduction.cs](OAGDProduction.cs)，独立试玩在 [OAGDPlayback.cs](OAGDPlayback.cs)。脚本只安装到目标工程，版本与实际进程写入会话记录。

独立试玩包与正式构建共用 [OAGDBuild.cs](OAGDBuild.cs) 的底层构建调用，各自保留输出、目标及验收规则。制作入口自动检查并安装这项依赖；只更新有登记且未被用户修改的辅助文件，写入前建立检查点。正式构建入口通过 `tools/engine_setup.py` 显式安装 `OAGDEngineBridge.cs` 和 `OAGDBuild.cs`，见 [执行配置](execution.md)。

| 操作 | 必填与用途 |
| --- | --- |
| scene | `path: Assets/...unity`，`create: true` 新建，否则打开 |
| object | `target` 精确层级路径；新建时 `create: true`、target 为单一名称，可提供 `parent`；支持 `primitive` 或现有 prefab/model 的 `source` |
| components | object 中提供 `type`（完整类型名，如 UnityEngine.Rigidbody）及 `properties`；已有唯一组件复用，否则添加 |
| import | 源文件绝对 `source`、工程内 `path`；覆盖必须 `replace: true` |
| model | 模型 `path`、`animation_type`（None/Legacy/Generic/Human），可提供含有效 Avatar 的 `avatar` 资源路径 |
| animation | `target`、新 `controller` 路径、`states`；可设 parameters、transitions 和 avatar |

object 的 position / rotation / scale 使用本地坐标 xyz。组件属性使用 Unity **序列化属性名**，例如 Rigidbody 的 `m_UseGravity`；不是把 C# 属性名随意拼进去。属性条目 `{name, kind, ...}` 支持 float/int 的 number、bool 的 boolean、string/enum 的 text、vector3 的 vector、asset 的 asset 路径、object 的 object_path。Unity 原生类型约束仍然生效，缺字段或类型错误会失败。复杂嵌套数组须使用实际 SerializedProperty 路径，数组长度变更需扩展接口。

animation 的 states 为 `{name, clip, clip_name?}`；一个模型包含多个 AnimationClip 时必须选具体 clip_name。parameters 为 `{name, type}`（Float/Int/Bool/Trigger）；transitions 为 `{from,to,duration,parameter?,condition?,threshold?}`，condition 使用 AnimatorConditionMode 名称。第一状态为默认状态。已有 Controller 不覆盖，防止丢失手工状态机；此时走项目内定向实现/编辑。Human 配置不能代替人工骨骼映射和动作适配验收。

可直接复制并按工程修改 [场景示例](examples/scene.json)、[试玩示例](examples/playback.json)。示例创建验证几何体，不是游戏默认玩法或美术方案。

独立试玩使用 `scene`、`seconds`、`camera`，`capture_interval: 0` 关闭录制。actions 支持：

```json
{"at": 1, "op": "position", "target": "Player", "position": [1, 0, 0]}
```

或 `{at,op:"message",target,method,argument?}` 调用项目明确提供的 MonoBehaviour 方法；无接收器会报错。报告检查实际执行数量，保存帧耗时；方法的业务正确性还需要项目自己的断言和测试。

使用 `mode: inspect` 和 scene 可在新的编辑器进程读取层级、变换、组件类型、持久化资产引用。角色模型应先导入并实例化，再配置 Avatar/Animator，最后实际播放检查姿态、位移、动画衔接和碰撞。
