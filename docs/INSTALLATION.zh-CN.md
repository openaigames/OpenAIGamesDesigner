# 安装、布局与迁移

[English](INSTALLATION.md) | [简体中文](INSTALLATION.zh-CN.md)

## 三个位置

| 位置 | 保存内容 | 更新方式 |
| --- | --- | --- |
| 源码工作树 | skills、tools、adapters、templates、docs 和维护测试 | 开发修改与版本管理 |
| Skill 安装根 | 16 个 Skill、根 LICENSE/README、game-preproduction/runtime | 完整新装或带备份的显式包升级；其他 Skill 和本地文件保持原样 |
| 游戏项目 | 原生工程、项目规则、资产、配置、存档与锁定的组件副本 | 由游戏维护者选择安装/迁移，不随工具包升级自动变化 |

公共 runtime 只是工具包资源根，不是跨游戏共享可写状态。Godot core 放在游戏的 addons/oagd，UE core 放在 Plugins/OAGDCore；playback 为独立的动作组件。

## 新装与检查

在源码根执行，输出必须为新目录：

```sh
python tools/package_skills.py --output dist/skills-bundle
```

复制输出的完整内容到宿主支持的 Skill 根，再重新加载。不要只复制 SKILL.md。安装版从 game-preproduction/runtime 运行工具：

```sh
python tools/check_installation.py --skills-root SKILLS_ROOT
```

SKILLS_ROOT 替换为安装根的绝对路径。missing 是清单内缺失，changed 是相对该包清单的修改，extra 是所属 Skill 下的额外文件；任何一项存在都会返回非零。其他不属于此包的 Skill 不在检查范围内。哈希清单确认内容身份，不代表功能或质量验收。

可选[资产质量工具](../adapters/assets/quality-review.zh-CN.md)需要在执行它的 Python 环境安装 Pillow（`python -m pip install Pillow`）；GLB 证据采集还需已安装的 Blender。这些依赖不包含在 Skill 包中。

## 更新工具包

在源码根目录或安装包的 runtime 目录使用 `tools/bundle_upgrade.py`。保留旧通用源码包作为 BASE、新通用包作为 NEW、当前安装作为 INSTALLED：

```sh
python tools/bundle_upgrade.py prepare --baseline BASE --new NEW --installed INSTALLED --output CANDIDATE
python tools/bundle_upgrade.py apply --candidate CANDIDATE --target INSTALLED --backup NEW_BACKUP
python tools/bundle_upgrade.py rollback --backup NEW_BACKUP
```

先检查候选回执和差异，在独立副本演练后再应用。prepare 保留本地覆盖，文本补丁上下文不唯一时拒绝；文件删除需专门迁移。apply 验证安装未变化并备份本次写入文件；回退遇到升级后的新编辑会拒绝覆盖。不得通过重建清单把未知修改伪装为已核对版本。

## 更新已有游戏组件

先查看锁定状态，再选择 core/playback：

```sh
python tools/runtime_components.py status --project GAME
python tools/runtime_migration.py plan --project GAME --engine godot --packages core playback --plan review.json
python tools/runtime_migration.py apply --project GAME --plan review.json --receipt BACKUP_OUTSIDE_GAME
python tools/runtime_migration.py rollback --project GAME --receipt BACKUP_OUTSIDE_GAME
```

UE 使用 --engine unreal。路径替换为实际位置，plan/receipt 使用新的输出；具体字段及限制见 [组合支持与迁移](../templates/engineering_example/SUPPORT.zh-CN.md)。迁移检查锁文件、上游与项目三方差异，不替换游戏规则、角色绑定、输入配置和存档；安装源码后仍须接入实际消费者并运行验证。

## 验证安装

使用上面的完整性命令，并在独立游戏工程中调用实际工具。安装包包含 Skill、运行工具、模板、必要示例、使用文档及许可证。维护测试、测试夹具和场景测试脚本保留在源码仓库，见[源码测试说明](../tests/README.zh-CN.md)。内部核对记录、本机日志、凭据和开发计划不进入公开源码或安装包。

如果新版发行内容删除了文件，应安装到新目录，再转移已核对的本地定制。增量升级工具会拒绝文件删除；直接覆盖旧安装可能留下过时文件。
