# Unreal Engine

沿用明确选定的 UE 版本。[命令适配器](cli.py) 负责现有工程的运行/测试/构建；新工程创建及原生 Python 场景、资产、动画、PIE 操作见 [制作接口](production.md)。宿主已有合适的原生工具时也可按 [MCP 接入](../mcp.md) 使用，不把两种连接方式的证据混为一谈。

## 环境配置

以下以 Windows 为例，版本沿用目标工程，不自动升级。

| 组件 | 什么时候需要 | 在哪里操作 | 完成检查 |
| --- | --- | --- | --- |
| Unreal Editor | 打开和制作 UE 工程 | Epic Games Launcher 的 Unreal Engine → Library 安装目标版本，或沿用源码构建 | 用对应编辑器打开 `.uproject`，记录实际版本 |
| C++ 工具链与 Windows SDK | C++ 工程或需要本地编译的插件 | Visual Studio Installer → Modify，选择 Game development with C++，按目标 UE 的兼容表配置编译工具和 SDK | 构建真实 Development Editor 目标；仅安装 VS Code 不提供这些组件 |
| Unreal MCP 候选插件 | 采用下文候选提供方时 | 先放入独立验证工程 `Plugins/UnrealMCP/`，编译；UE Edit → Plugins 中确认启用 | 插件加载成功，随后验证连接和对象操作 |
| Python MCP 服务 | 同上 | 候选仓库的 `Python/` 目录，按上游说明安装 Python / uv 和依赖 | 服务启动并连接正确编辑器，记录日志 |
| 助手 MCP 连接 | 让 AI 调用该服务 | [助手端配置](../../environment-setup.md#mcp-三端配置)，填写实际服务启动命令 | 当前任务发现工具，并核对工程身份 |
| GAS（可选） | 项目已采用或根据需求选用时 | 核对 GameplayAbilities 插件；C++ 按实际 API 配置 GameplayAbilities / GameplayTags / GameplayTasks 等模块依赖；不要求样例工程 | 验证 ASC 初始化、能力授予/执行/结束与属性结果；与 MCP 联通分别记录 |

纯蓝图工程是否需要编译环境取决于所用插件和目标制作任务；本候选带源码 C++ 插件，因此首次构建需要工具链。UE 自带 Python / Remote Control 插件不能替代该候选要求的 UnrealMCP 插件。

Windows 查询 Visual Studio 安装时使用 `vswhere -all -products '*' -format json`，否则可能漏掉独立 Build Tools。组件目录名也不等于实际编译器补丁版本；最终以 UBT 构建日志及目标 UE 的兼容规则为准。

来源：[Epic 的 Visual Studio 环境配置](https://dev.epicgames.com/documentation/en-us/unreal-engine/setting-up-visual-studio-development-environment-for-cplusplus-projects-in-unreal-engine)、[候选提供方安装说明](https://github.com/chongdashu/unreal-mcp#-quick-start-guide)。需登录获取的工程和资产由用户完成账号访问，助手继续处理本地配置。

## 工程和命令

在工具包根运行，替换为实际路径；已有工程不复制或重建：

```sh
python tools/game_workflow.py init --project "MyGame" --engine unreal --engine-root game --editor "D:/UE/Engine/Binaries/Win64/UnrealEditor.exe" --project-file MyGame.uproject
python tools/game_workflow.py run --project "MyGame" --action doctor
```

doctor 检查编辑器文件与工程声明，不证明插件可加载、编辑器已运行或版本兼容。play 默认使用编辑器 `-game -log`；prepare 已提供只读工程加载检查，smoke 运行指定地图，test 接 Automation，build 接 UBT，export 接 UAT。先填写明确的地图、测试范围和目标，见 [执行配置](execution.md)；[命令与报告协议](../../README.md) 规定输出和错误传播。

## MCP 首次联调

候选 [chongdashu/unreal-mcp](https://github.com/chongdashu/unreal-mcp) 包含 Python MCP 服务和项目侧 C++ 插件。上游标注实验性质，示例基于 UE 5.5；“5.5+”声明不等于已验证所有新版引擎。

下列接口对应上游源码 [4e5f00d](https://github.com/chongdashu/unreal-mcp/tree/4e5f00da50733190481311e254d16d137a84ef33/Python)。以下是该版本提供的函数名，用于连接后对照发现结果，不表示本机已经注册：

| 联调动作 | 上游工具 / 缺口 |
| --- | --- |
| 列出 / 查询 Actor | `get_actors_in_level`、`find_actors_by_name`、`get_actor_properties` |
| 创建 / 修改 / 清理测试对象 | `spawn_actor`、`set_actor_transform`、`delete_actor` |
| 创建 / 编译 Blueprint | `create_blueprint`、`compile_blueprint`；成功后仍需读回和编译日志 |
| 工程身份、显式保存关卡、重开、PIE 与自动测试 | 此版本注册的 Python 工具中未找到相应独立入口，需另接可验证的工程 / 编辑器方法 |
| GAS 专项 | 未发现专用工具，按项目实现验证 |

上游 README 的 Python 前提写 3.12+，该 commit 的 `pyproject.toml` 写 >=3.10；首次联调用满足较高要求的环境并实际安装验证，不仅凭声明判断兼容。

1. 核实 UE 安装、项目类型、匹配的 C++ 编译工具链和 Windows SDK。固定提供方 commit / release，记录 Python 与依赖版本。
2. 在独立临时工程验证插件编译和加载；新验证工程不是正式游戏或用户已确认的资产方案。不直接向已有战斗工程拷入未验证插件。
3. 按该提供方说明启动服务，在宿主中发现真实工具，核对目标编辑器。候选使用本地 TCP 桥接，不把“端口已监听”当作目标工程身份。
4. 只读列出场景对象；在测试关卡创建唯一命名对象，修改属性后重新读取；保存并重开验证；最后清理本次测试对象并再次保存。缺少保存/读取工具时记录缺口，使用可核实的编辑器方式完成，不虚构接口。
5. 将编译日志、工具清单、读写结果与保存重开证据写入测试项目。基础联通通过后才接本轮战斗任务。

未接通 MCP 时仍可用工程已有命令、源码和已授权编辑器工具完成可验证的工作。不要把测试环境缺口改写成用户的玩法或引擎选择。

## 战斗专项边界

| 专项 | 需要明确或读取 | 实机验证 |
| --- | --- | --- |
| GAS | 工程是否采用、ASC 所有者、AttributeSet、Ability / Effect / Tag、输入与动画关系 | 授予 / 触发能力、消耗与冷却、取消和死亡清理；实际采用联网时再测复制 |
| 自有能力/战斗系统 | 现有输入、状态、生命/伤害组件、数据主源和结束/取消职责 | 激活、命中/结果提交、状态与恢复；不因不用 GAS 降低验收要求 |
| 动画与资产 | 用户已确认模型、骨架与动作来源、蒙太奇 / Notify / 命中窗口 | 导入、兼容、播放、命中时序、保存重载与试玩 |

通用 Actor / Blueprint MCP 工具不等于自动支持 GAS、蒙太奇或重定向。技术 Skill 先用 `unreal-project.md` 接入；路线未定时读 `ability-system-choice.md`，已采用 GAS 时读 `gas-combat.md`，动作集成读 `action-animation-integration.md`。按项目需要选择，不自动绑定完整示例或商业动作框架。使用原生源码或项目脚本的专项实现仍需编译与游戏运行证据。
