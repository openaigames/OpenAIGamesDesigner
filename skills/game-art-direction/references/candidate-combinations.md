# 从候选素材形成可验证的组合

可从需求或素材任一方向进入。保留原目标与选定工作对象，分别判断玩家、Boss、场景等能力；玩家持剑不意味着怪物也必须持剑。读取真实模型、骨架、动作、反馈样本和来源约束后，再决定组合与必要设计调整。来源改变不自动授权降低原目标。

现有 `asset_library.py` 新增 fit/fits，复用同一资产登记区；没有新增登记→测试→晋升流程。实际文件归属继续由工程内容根决定，只有候补和游戏应用两栏。方案记录可以早于下载，文件进入 Content 也不自动证明品质合格。

```text
python tools/asset_library.py --project <项目> fit --request design/candidates/creature-combination.json
python tools/asset_library.py --project <项目> fits
```

请求字段：schema_version:1、id、title、object、role、use、goal_ref（实际目标文件）、sources、members、requirements、tradeoffs。sources 记录原始 HTTPS url/title/version/price/license 和已保存 evidence；未核验价格/许可直接写未确认，不能把站点免费标签当当前具体资产授权。

members 有稳定 id、source_url、可选本地 path、capabilities。能力项有 id/kind/label/availability/preview_type/evidence/conditions；availability 为 observed/claimed/missing/unknown，preview_type 为 motion/image/native/audio/none。动作和 VFX 的 observed 必须有动态或原生播放证据，静态模型图只能支撑相应外观观察。声音需要真实监听依据。实际清单不代表每项都已测试，逐项标注条件与版本。

requirements 逐项记录 id/description/coverage/member/capability/notes；coverage 为 supported/partial/missing/unknown。supported 必须关联已观察能力，缺口保留说明。tradeoffs 写组合收益、代价及对原目标的影响。文件哈希随记录冻结；目标、素材或证据变化后显示过期。修订用新 id 与 supersedes，保留旧记录，不能覆盖另一对象或另一目标。

看板的方案卡直接展示能力、需求覆盖、缺口、取舍和来源。方案适配、获取成功、游戏目录归属、运行功能与艺术品质是不同事实，不能用其中一个替代另一个。
