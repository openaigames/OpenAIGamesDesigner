# 历史片段取舍接口

共享模型预览已移除动作取舍表单；下文保留旧客户端的数据协议和交互约定，供兼容读取、保存和导出使用，不代表当前看板仍提供该表单。已有项目记录和备份不迁移、不删除。模型动作播放控件继续使用；共享看板不提供独立动作检查页面，记录与适配器保留。

兼容接口保存资源级“待定 / 保留 / 不采用”结论，可区分候补与游戏应用来源；不会移动、删除、导入资产或通过阶段验收。无需先初始化 Art Direction。技术资产 ID 来自扫描路径，保存时关联已有美术 ID，未知来源、许可与标签不补造。

## 预览、上下文与版本

`POST /api/motion-context` 为只读描述请求（沿用会话与 CSRF）：

```json
{"path":"game/attack.fbx","context":{"character_id":"player","role":"player","use":"general","rig_path":null}}
```

返回源文件与依赖 `source.fingerprint`、revision、entries。实际动作路径来自角色当前展示动画，而不是角色模型路径。context 中的 role、use、character_id、rig_path 与版本内 clip_index 共同区分结论；重复片段名不作为身份。多个角色可以共享同一片段并各自保存。

浏览器先获取指纹，再加载实际预览。加载后追加 `observation: {fingerprint, clips: [{name, duration}]}` 再描述/保存。GLTF 名称按本地文件核对；FBX 元数据由当前 FBXLoader 实际加载所得，保存为 `browser_fbx_observation`。这不是引擎原生观测，也不证明贴图、材质或最终效果合格。修改源文件后，旧的观测指纹不能用于保存。

指纹覆盖动作源、有效关联预览、glTF 外部缓冲/图像、映射声明依赖、所选角色模型与该角色绑定子记录/依赖、临时 FBX 预览角色。其他角色的名称或绑定不使当前角色结论过期。角色清单中的全局 legacy dependencies 仍按其声明范围参与；需要细粒度失效时使用每个角色的 dependencies。

FBX 本体包含骨架/动作轨道；外置 FBX 依赖需在角色绑定或关联预览清单中声明，才能参与完整版本校验。纯动作临时配角色只检查同名同层级播放，不执行重定向。mirror/root_motion 都是制作要求，不改变当前显示。

## 保存、历史与导出

`POST /api/motion-review`：`{revision, preview: 上述描述请求, clip_index, fingerprint, choice}`。choice 包含 decision、role、semantic、mirror、root_motion、note；keep 需要具体 role 与 semantic。角色用途必须与预览上下文一致。HTTP 409 表示版本冲突，界面保留输入，要求显式重新加载。

`GET /api/motion-review` 读取最新判断及 current/stale/unavailable 状态；历史保存在 `.asset-browser/motion-review.json` schema 2。首次写入 v1 时，先保存字节相同的 `motion-review.v1.<revision>.json` 备份，再升级；旧记录保持资源级用途并等待重新审阅，不推测角色。损坏或未知 schema 拒绝读取/覆盖。读请求不初始化文件。

写入复用 `record_io.project_lock`、路径检查和原子替换，同时校验 revision。中断遗留锁应按共享恢复工具检查原进程及证据后处理，不能自动删除别人的锁。

`GET /api/motion-handoff` 导出当前 keep 与排除项；`?character=player` 限定角色。导出携带记录 ID、动作路径、片段序号、context、source.files / fingerprint、provenance、原始 choice 和 revision。`runtime_validation` 始终为 `not_checked`。

显式交接时，将导出 JSON 放在项目证据目录：`asset_fit` 的 capability.evidence 可引用该文件，并将其中 source.files 作为该组合的证据依赖一起登记；不要仅保存导出而漏掉其所依据的素材。选材只证明所观察的预览范围。实际引擎质量仍使用 observation/evidence，并通过现有任务工具显式关联对象、阶段或问题。保存 keep 不自动关闭问题、不覆盖 asset_fit，也不自动通过阶段 3。

未保存保护覆盖资产、片段、角色、工程动画、临时 FBX 角色、刷新、导航和导出；取消时保持原下拉值、时间与暂停状态。保存期间禁止切换，错误保留草稿。浏览器关闭仍使用原生 beforeunload 提示。
