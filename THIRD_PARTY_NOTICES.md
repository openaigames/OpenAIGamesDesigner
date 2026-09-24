# 第三方组件与素材声明

工具包自身的代码、Skill、模板和文档采用 [MIT License](LICENSE)。第三方代码与素材按各自条款提供；本项目的 MIT 许可证不改变其版权、商标或素材授权。

## 随工具包提供的代码

看板附带 Three.js 0.186.0（r186）的构建文件和 addons，保留原始代码与版权注释。Three.js 的 MIT 许可见 [原始许可证](tools/workbench/web/vendor/three/LICENSE)。附带目录中的其他组件仍使用各自许可。

| 组件 | 适用许可 / 声明 |
| --- | --- |
| Draco、Basis Universal、Chevrotain | Apache-2.0；同时保留 Basis NOTICE、Draco 作者名单及相关依赖声明 |
| Earcut、potpack | ISC |
| fflate、lil-gui、meshoptimizer、motion-controllers、stats.js、surfaceNet、Tween.js、ktx-parse | 各自 MIT 许可 |
| MikkTSpace JS/WASM | 包装库 MIT；原始算法 Zlib；Rust 依赖按各自许可 |
| zstddec / Zstandard | 包装库 MIT、Zstandard BSD-3-Clause；同时附上上游提供的 Apache-2.0 替代许可 |
| UTIF、UZIP、pako、JPEG 解码部分 | 各自 MIT / Zlib / Apache-2.0 声明 |
| EXRLoader、SculptGL 派生代码 | TinyEXR BSD-3-Clause；[SculptGL MIT](tools/workbench/web/vendor/three/examples/jsm/misc/SculptGL.LICENSE.txt) |
| W3C WebCodecs 示例派生的 demuxer_mp4.js | W3C Software and Document License |
| Three.js 内引用的 gl-matrix 代码、Chevrotain 的 regexp-to-ast 等依赖 | 各自 MIT / Apache-2.0 声明 |

完整文本、来源和覆盖范围见 [许可索引](licenses/README.md) 与 [组件清单](licenses/third-party-sources.json)。原始内联版权声明继续有效。外部依赖的许可来源版本不等于已确认的内嵌二进制版本；Three.js 文件由 r186 发布包和文件哈希确定。

demuxer_mp4.js 随 Three.js 分发，源自 [W3C WebCodecs video-decode-display 示例](https://w3c.github.io/webcodecs/samples/video-decode-display/)。Copyright © World Wide Web Consortium；代码按 Three.js 中的形式提供，本工具包未进一步修改。该示例引用的 MP4Box 远程模块未复制进工具包，也不是当前看板的依赖。

## 图标与界面示例

- OpenAIGamesDesigner 标识由项目所有者提供。软件的 MIT 授权不授予对项目名称或标识的商标权，也不表示对衍生产品的背书。
- Tripo 与腾讯混元图标用于标识可配置的第三方服务，品牌权利归各自所有者；原始地址见 [图标来源](tools/settings-ui/logos/README.md)。这些图标不按本项目 MIT 许可证重新授权。
- README 中的游戏界面示例用于演示工具。截图里的第三方角色和素材权利仍归各自权利人；仓库和安装包不分发截图对应的游戏模型或音频。

## 外部服务与用户资产

用户另行安装的 Python、游戏引擎、MCP、生成服务及其他依赖按其各自许可和服务条款使用。工具包不附带服务额度、密钥或游戏资产授权。资产合集中的链接不是素材授权，使用时应核对具体资源页面。

分发包在每个 Skill 目录保留工具包 LICENSE，在 game-preproduction/runtime 中保留本声明、第三方许可全文与原有的组件版权声明。
