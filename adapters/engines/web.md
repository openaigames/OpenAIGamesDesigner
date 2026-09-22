# 网页游戏：Three.js 与 Phaser

网页 3D 使用 Three.js，网页 2D 使用 Phaser。已有工程保留其框架和构建方式；单纯提出游戏想法，不代表已选择网页平台。引擎选择、设计、资产方案和试玩目标仍沿用通用 workflow，网页不是自动降级路线。

## 初始化与接手

先保存六个项目入口并明确本轮目标。以下两种 engine 任选其一，不在同一个项目重复初始化：

```sh
python tools/game_workflow.py init --project "MyGame" --engine threejs --create-engine --node "C:/Tools/node/node.exe" --package-manager-cli "C:/Tools/node/node_modules/npm/bin/npm-cli.js"
```

2D 将 `threejs` 改成 `phaser`。已有项目省略 `--create-engine`，通过 `--engine-root` 指向包含 package.json 的真实目录。初始化只创建空渲染入口，不生成玩法、资产或已通过的测试。项目根保留六份专业文档，网页源代码在 `game/`。

Node 与包管理器路径是本机实际路径，示例不能直接照抄。也支持 `pnpm.cjs`；其他包管理器在 `commands.prepare` 配置。Windows 通过 Node 调用包管理器 JS，避免依赖 shell 的 npm.cmd。新模板锁定 Three.js 0.186.0 / Phaser 4.2.1、Vite 8.3.0；首次安装保存 lockfile，以后使用 npm ci / pnpm frozen-lockfile。现有项目不自动升级。Vite 8 的 Node 要求见官方资料，路径检查不替代真实版本兼容检查。

## 命令与证据

| 动作 | 默认行为 | 通过代表什么 |
| --- | --- | --- |
| doctor | 检查 Node 路径、package.json 中选定框架声明 | 配置可读；不证明运行环境或网页可用 |
| prepare | 安装项目依赖，已有锁文件时严格沿用 | 安装命令完成；保存真实日志 |
| build / export | 调用工程本地 Vite，输出到独立 builds/运行编号 | 构建命令完成；export 另检查非空 index.html 并登记产物哈希 |
| play | Vite 在 127.0.0.1:5173 提供开发服务，端口冲突报错 | 这是持续进程；超时会停止并如实记录 timeout，不能当作试玩通过 |
| smoke / test | 项目配置命令，无虚假的默认成功 | 使用真实浏览器检查或游戏断言；test 必须返回实际测试报告 |

```sh
python tools/game_workflow.py run --project "MyGame" --action prepare --timeout 600
python tools/game_workflow.py run --project "MyGame" --action export --timeout 180
```

沿用 [命令配置与报告协议](../README.md)，commands 可覆盖默认动作。测试包装器传播失败并把真实报告摘要写入 `{run}/test-results.json`。没有 smoke/test 配置会记录 blocked，不能将构建冒充浏览器测试。

实际试玩可由宿主终端管理开发进程，记录工作目录、命令、URL、退出方式；使用浏览器打开输出 URL。CLI play 适合有限时长会话，不是后台服务管理器。不要用 file:// 加载游戏。交付前另以 HTTP 服务打开导出目录，检查子路径、资产请求、控制台异常、输入、重开和目标设备。启动服务不等于公开发布，导出不会部署。

## 工程规则

- Three.js 提供渲染；输入、角色控制、碰撞/物理、动画状态、游戏流程按已确认需求实现，不默认添加完整游戏框架。
- Phaser 采用 Scene、Loader、Input 和需要的物理系统；仅渲染启动不代表关卡或战斗已制作。
- 在技术文件记录依赖/锁文件、模块职责、构建和测试入口；在美术文件登记真实素材、用途、格式、来源及导入状态。网页需要另检查加载失败、纹理/音频兼容、画布缩放和资源体积。
- 数值主源可为工程 JSON；通过现有数值交换工具修改后，重新加载并验证实际行为。记录是构建时打包还是运行时 fetch，不能假定改表会自动更新已导出的包。

依据：[Three.js 官方手册](https://threejs.org/manual/)、[Phaser 安装](https://docs.phaser.io/phaser/getting-started/installation)、[Vite 入门与环境要求](https://vite.dev/guide/)。
