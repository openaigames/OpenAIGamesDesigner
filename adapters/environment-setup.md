# 按功能配置开发环境

先选本轮要用的功能，只配置对应环境。已有工程沿用其版本和工具；安装 Skills 不会自动安装游戏引擎、MCP 服务、生成模型或资产。

本文当前的宿主操作说明针对 **Codex 本地使用**。Claude Code 等其他 Agent 后续再补安装、连接与验证说明；通用引擎和工具方法继续共用。

## Codex 路径速查

`~` 表示当前用户主目录。Windows 默认对应 `C:/Users/<用户名>/`；表中 `<游戏项目>` 指要制作的游戏文件夹，不是本工具包源码目录。

| 内容 | Codex 使用的位置 | 如何操作 |
| --- | --- | --- |
| 个人 Skills | `~/.agents/skills/<skill-name>/` | 将打包生成的六个完整 Skill 目录放入这里，供本机多个项目使用 |
| 项目级 Skills（可选） | `<游戏项目>/.agents/skills/<skill-name>/` | 只为当前项目安装时使用；与个人安装通常二选一，避免维护不一致的副本 |
| 已安装工具包根 | 所选安装位置下的 `game-preproduction/runtime/` | 在此目录调用 `tools/game_workflow.py` 等工具；不能只复制 SKILL.md |
| Codex 的 Skill 展示信息 | 各 Skill 的 `agents/openai.yaml` | 随技能包保留；这里不是 MCP 配置或游戏设计记录 |
| Codex 用户配置与 MCP | 默认 `~/.codex/config.toml` | 合并到已有配置，保留其他设置；若设置了 `CODEX_HOME`，核对其实际配置目录 |
| Codex 项目级配置与 MCP（可选） | `<游戏项目>/.codex/config.toml` | 仅作用于受信任项目；按需要选择配置范围，避免重复注册服务 |
| 游戏工作目录 | `<游戏项目>/` | 在 Codex 中以此目录开始任务；项目管理和五个专业入口保存在这里 |
| 游戏原生工程 | 新作默认 `<游戏项目>/game/` | UE 的 .uproject、Godot 的 project.godot 或网页 package.json 位于实际工程目录；已有工程原位接入 |
| 引擎和执行命令配置 | `<游戏项目>/.openaigame/project.json` | 本工具包使用，记录真实引擎位置、程序路径与项目命令；不会注册 MCP |
| 资产工具配置 | `<游戏项目>/.openaigame/asset-providers.json` | 登记实际生成或处理工具；不会安装模型或引擎插件 |

安装后在 Codex 新开任务，确认六个 Skill 可被发现；可明确输入“使用 game-preproduction，检查这个游戏项目的当前阶段”验证读取，再测试自然语言自动触发。文件存在、Skill 被读取、CLI 可运行和引擎已连接是不同检查项。

路径依据：[Codex Skills 官方说明](https://learn.chatgpt.com/docs/build-skills)、[Codex MCP 官方说明](https://learn.chatgpt.com/docs/extend/mcp)。以下通用表中的“助手端”当前指 Codex。

## 需要准备什么

| 想使用的功能 | 必需环境 | 在哪里安装或配置 | 如何确认可用 |
| --- | --- | --- | --- |
| 讨论立项、GDD、美术和技术方案，维护项目文件 | 能读写项目的 AI 助手与六个 Skills | 助手的 Skill 安装目录；在游戏项目目录开始任务 | 新任务能读取 Skill，并把已知与待定保存到项目文件；不需要先安装引擎 |
| 初始化文档、记录任务、检查文件和运行记录 | Python 3.10+ 与完整运行资源 | 本机 Python；源码 `tools/` 或已安装的 `game-preproduction/runtime/tools/` | 在对应工具包根执行 `python tools/game_workflow.py --help` |
| Three.js 网页 3D / Phaser 网页 2D | 兼容项目 Vite 的 Node.js、npm 或 pnpm、浏览器 | 本机安装 Node；游戏工程安装依赖；项目配置记录 Node 与包管理器路径 | 依赖安装 → 构建 → HTTP 打开导出版本 → 实际操作；见 [网页说明](engines/web.md) |
| Godot 原型与试玩 | 项目所需 Godot 4 可执行文件 | 本机安装 / 解压引擎；在项目配置登记路径 | 查询版本、导入并运行真实场景；见 [Godot 配置](engines/godot/README.md#环境配置) |
| Godot 独立包 | 匹配引擎的导出模板、目标平台所需工具 | Godot 的 Editor → Manage Export Templates；导出窗口添加平台预设 | 导出后单独启动包；仅编辑器能运行还不够 |
| Unity 工程制作 | 匹配的 Unity Editor、项目包依赖；按目标安装平台模块 | Unity Hub 管理编辑器和模块；Unity Package Manager 管理工程包 | 工程正常导入、编译、进入 Play；见 [Unity 配置](engines/unity/README.md#环境配置) |
| Unreal 工程制作 | 匹配的 UE；C++ 工程 / 源码插件另需匹配工具链和 SDK | Epic Games Launcher 或既有引擎安装；Windows 编译组件在 Visual Studio Installer 中配置 | 工程可打开；涉及 C++ 时实际构建通过；见 [UE 配置](engines/unreal/README.md#环境配置) |
| AI 通过 MCP 操作编辑器 | 对应 MCP 服务及其依赖；提供方要求的引擎插件 | 引擎侧安装插件（若需要）＋本机服务环境＋AI 助手连接配置 | 工具可发现、目标工程正确、读写与保存重开通过；见 [MCP 三端配置](#mcp-三端配置) |
| UE 动作/动画接入 | 本轮选定或授权选材的资源/模块，目标版本兼容 | 工程 Content 导入动画，第三方代码按提供方安装到项目；检查骨架、控制接口和依赖 | 动画预览、工程中播放、规则时序、取消/恢复与试玩分别验证；不限定某个动作包 |
| 图像、3D、音频生成 | 用户选定的实际生成工具 / 服务及包装脚本 | 工具自己的环境；游戏项目 `.openaigame/asset-providers.json` | 先完成一次小任务，检查真实文件和日志；见 [资产接入](assets/README.md) |
| Blender 模型处理 | Blender 与适用的输入格式 / 依赖文件 | 本机安装 Blender；资产提供方配置填写其可执行路径 | 转换后重新打开检查模型、材质和动画；见 [资产处理说明](assets/README.md) |
| 数值 CSV 往返 | Python、真实 JSON 主源与字段绑定 | 游戏项目中的数值绑定文件；CSV 可用表格软件编辑 | 导出 → 修改 → 比较 → 应用 → 引擎重载确认 |
| 读取数值 Excel 表 | 上述环境，另加运行工具所用 Python 的 `openpyxl` | 在同一 Python 环境执行 `python -m pip install openpyxl` | 读取指定数值页并检查差异；见 [数值往返](../tools/README.md#数值表往返) |

表格制作、概念图生成等助手能力取决于宿主提供的工具；本项目不自动包含这些服务。GPU、显存、模型权重和服务凭据按实际选定的生成工具要求配置，没有所有用户通用的模型环境清单。

## MCP 三端配置

| 层级 | 用户会在哪操作 | 配置内容 | 验证依据 |
| --- | --- | --- | --- |
| 引擎端 | 目标工程的插件目录 / 插件面板 / 包管理器，按提供方说明 | 安装兼容插件并启用；有源码插件时先编译，必要时重启编辑器 | 插件成功加载，工程没有新增编译错误 |
| 本机服务端 | 提供方的独立目录、Python 虚拟环境或 Node 环境 | 安装并固定服务版本及依赖，设置启动命令 | 服务成功启动并能连接目标编辑器；日志无连接错误 |
| Codex 端 | 上表中的 Codex 用户级或项目级 config.toml；也可使用 Codex CLI 管理 | 服务命令 / URL、工作目录及必要环境变量 | 当前任务发现真实工具，调用只读查询并核对工程身份 |

并非每套 MCP 都需要引擎插件。引擎插件、独立服务与启动参数由所选提供方决定。使用提供方实际要求，不把 UE 的步骤套到所有引擎上。

Codex 的配置可位于用户级 `~/.codex/config.toml` 或受信任项目的 `.codex/config.toml`；也可使用 `codex mcp add`。服务的命令和参数必须来自实际安装路径，不能把其他客户端的 `mcpServers` JSON 直接当作 Codex TOML。配置后重新连接，并检查当前会话是否看到了工具。操作方式见 [官方 MCP 文档](https://learn.chatgpt.com/docs/extend/mcp)。

提供方示例见 [候选清单](engines/mcp.md#候选提供方)。这些是可评估的外部项目，不随本工具包安装；实际兼容性需在目标版本上验证。MCP 不是制作游戏的必选项，项目脚本和命令路线仍可使用。

## 配置应该存在哪里

| 内容 | 保存位置 | 谁维护 |
| --- | --- | --- |
| 引擎、Node 等程序 | 本机软件安装位置 | 用户或助手执行环境安装 |
| 项目使用哪个引擎、工程在哪里、构建 / 测试怎么执行 | 游戏项目 `.openaigame/project.json` | 初始化工具或助手；已有配置先读取再更新 |
| 资产生成 / 转换命令 | 游戏项目 `.openaigame/asset-providers.json` | 按实际工具配置；包装脚本需要真实存在 |
| MCP 服务连接 | 助手的 MCP 配置 | 用户或助手配置；不是写进 `project.json` 就会连通 |
| 采用的版本、配置依据、当前缺口 | `Technical Design.md`；必要时拆出 `design/technical/engine-connection.md` | 助手根据实际检查更新 |
| 安装 / 编译 / 工具调用和复查证据 | 游戏项目 `runs/` 与验证报告 | 执行者记录，项目管理链接摘要 |

机器上的绝对路径由每位使用者按实际情况填写；不要直接采用示例路径作为安装位置。密钥不写入会归档的命令参数和文档，使用工具自身凭据管理或环境变量名引用。

## 用户与助手分别做什么

用户提供本轮目标、明确的引擎选择，以及已有工程的位置（若有）；使用账号授权的资源时由用户完成对应登录。助手先检查已有环境，列出缺项及其影响，完成授权范围内的下载、配置和测试。管理员弹窗、账户登录、软件许可确认等需要用户交互的步骤，会说明具体操作位置。

可以直接说：

```text
这次使用 Unreal，先检查制作环境和 MCP 接入条件。
已有工程是 D:/Games/MyGame/MyGame.uproject。
列出已经可用的部分、缺少的组件，以及分别在哪里配置。
```

检查结果分为“未安装 / 未配置 / 已配置未验证 / 已验证 / 验证失败”，每项带下一步。当前 `doctor` 只覆盖对应适配器的检查范围，不会自动完成上述全部检查或安装；尤其 Unity / UE 的文件检查不证明 MCP、编译、打包已经可用。

环境配置通常在第一次接入时完成；引擎升级、插件更新、换机器或目标平台变化后，复查受影响的部分。
