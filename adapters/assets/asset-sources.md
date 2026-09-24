# 游戏资产合集、获取与登记

按素材类型、收费方式和下载条件查找适合项目的资源，覆盖免费与付费内容。目录优先收录作者或官方站点，提供具体素材页、文件入口、许可依据与账号要求；也可结合其他来源、自制或已授权的生成方式选材。结构化数据见 [sources.json](sources.json)。

## 收费标记

**免费 / 部分免费（含付费）/ 付费 / 待核实** 与账号、下载方式独立标注。可选捐赠不算强制付费；支持者早期访问、独立工具和公开资产库分别判断。价格标签描述所列资源库，不保证具体包、格式或许可档位免费。当前来源有免费库和混合收费网站，目录也支持后续收录纯付费来源。

选材时记录具体版本的当前价格、币种、包含文件、许可和核查日期；限时免费记录领取期限，不能写成永久免费。付费素材可在用户已有预算与授权范围内获取，也可登记用户已购买并提供的文件。网站收录不代表素材已购买、下载或获得使用许可。

## 可免登录获取的文件示例

以下来源提供无需账号的文件下载入口，助手可通过公共 HTTPS 获取。表中列出具体素材与文件示例；选择其他素材或版本时，需重新核对免费范围、许可、文件格式和依赖。下载记录及检查日期保存在结构化目录中。

| 来源 / 覆盖类型 | 素材示例 / 文件入口 | 账号 | 收费方式与许可 |
| --- | --- | --- | --- |
| [Kenney](https://kenney.nl/assets)<br>2D、3D、UI、材质、VFX、音频 | [Particle Pack](https://kenney.nl/assets/particle-pack)<br>[文件](https://kenney.nl/media/pages/assets/particle-pack/f8fe0f8cb8-1677578741/kenney_particle-pack.zip) · PNG / ZIP | 无需 | **部分免费 / 含付费** — 单独资源包免费；All-in-1 整合包付费。 [收费依据](https://kenney.itch.io/kenney-game-assets)。 单独资源包与付费合集分别核实；查看具体包的许可文件。 |
| [Poly Haven](https://polyhaven.com/)<br>3D、材质、HDRI | [aerial_rocks_02 / Diffuse 1K](https://polyhaven.com/a/aerial_rocks_02)<br>[文件](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/aerial_rocks_02/aerial_rocks_02_diff_1k.jpg) · JPG | 无需 | **免费** — 公开模型、材质和 HDRI 免费；支持者权益与工具另计。 [收费依据](https://polyhaven.com/license)。 公开 CC0 资产与公共 API 免费；使用 API 时按官方要求标明 Poly Haven 来源；公开资产 CC0，保留资源页面和许可依据。 |
| [ambientCG](https://ambientcg.com/)<br>3D、材质、HDRI | [Wood051 / 1K-JPG](https://ambientcg.com/view?id=Wood051)<br>[文件](https://ambientcg.com/get?file=Wood051_1K-JPG.zip) · PBR JPG/PNG / ZIP | 无需 | **免费** — 公开材质、HDRI 和模型免费；支持者权益另列。 [收费依据](https://docs.ambientcg.com/license/)。 公开资产免费，支持者权益另列；公开资产 CC0，查看 https://docs.ambientcg.com/license/。 |
| [OpenGameArt](https://opengameart.org/)<br>2D、3D、UI、材质、VFX、动画、音频、字体 | [80 CC0 RPG SFX](https://opengameart.org/content/80-cc0-rpg-sfx)<br>[文件](https://opengameart.org/sites/default/files/80-CC0-RPG-SFX_0.zip) · OGG / ZIP | 无需 | **免费** — 站内公开素材免费；各资产的署名与许可要求分别核对。 [收费依据](https://opengameart.org/content/faq)。 逐条目核实下载内容；许可多样，逐资产记录署名和适用条件。 |
| [Godot Asset Library](https://godotengine.org/asset-library/asset)<br>模块、VFX、UI | [Basic FPS Controller for Godot 4 / 1.0.0](https://godotengine.org/asset-library/asset/5421)<br>[文件](https://github.com/ar-bh/basic-fps-controller-godot/archive/7f50a91a7063106047a06bd8d6c200cdda80f3b2.zip) · GDScript / TSCN / ZIP | 无需 | **免费** — 此目录中的开源插件、工具和示例免费。 [收费依据](https://docs.godotengine.org/en/stable/community/asset_library/what_is_assetlib.html)。 开源插件、工具和示例，逐条目核实；跟随源仓库具体版本的 LICENSE。 |
| [KayKit](https://kaylousberg.com/game-assets)<br>3D、动画 | [Prototype Bits / Barrel_A](https://github.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0)<br>[文件1](https://raw.githubusercontent.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0/main/addons/kaykit_prototype_bits/Assets/gltf/Barrel_A.gltf) / [文件2](https://raw.githubusercontent.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0/main/addons/kaykit_prototype_bits/Assets/gltf/Barrel_A.bin) / [文件3](https://raw.githubusercontent.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0/main/addons/kaykit_prototype_bits/Assets/gltf/prototypebits_texture.png) · glTF + BIN + PNG | 无需 | **部分免费 / 含付费** — 公开免费包与付费角色包、扩展内容和整合包并存。 [收费依据](https://kaylousberg.itch.io/)。 作者公开免费包；付费角色、Extras/Source 与合集的内容和价格另核实；样例 CC0；逐包保留 LICENSE。 |
| [Game-icons.net](https://game-icons.net/)<br>2D、UI | [White on black SVG archive](https://game-icons.net/)<br>[文件](https://game-icons.net/archives/ffffff/000000/game-icons.net.svg.zip) · SVG / ZIP | 无需 | **免费** — 公开 SVG / PNG 图标免费，使用时保留所需署名。 [收费依据](https://game-icons.net/faq.html)。 公开 SVG/PNG 图标；以条目及包内许可为准，主要为 CC BY 3.0，需记录各图标作者。 |
| [Google Fonts](https://fonts.google.com/)<br>字体 | [Abel Regular](https://github.com/google/fonts/tree/main/ofl/abel)<br>[文件](https://raw.githubusercontent.com/google/fonts/main/ofl/abel/Abel-Regular.ttf) · TTF | 无需 | **免费** — Google Fonts 目录中的字体免费；按所选字体许可使用。 [收费依据](https://github.com/google/fonts/blob/main/ofl/abel/OFL.txt)。 官方字体仓库公开字体；逐字体查看 OFL/Apache 等许可；样例 Abel 为 OFL 1.1。 |
| [Lucide](https://lucide.dev/icons/)<br>UI | [swords](https://lucide.dev/icons/swords)<br>[文件](https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/swords.svg) · SVG | 无需 | **免费** — 公开图标免费，保留版权与许可声明。 [收费依据](https://lucide.dev/license)。 公开 SVG 图标；ISC；部分源自 Feather 的图标为 MIT，保留版权及许可声明。 |
| [Effekseer Sample Effects](https://effekseer.github.io/en/contribute.html)<br>VFX | [Effekseer01](https://effekseer.github.io/en/contributes/Effekseer01/index.html)<br>[文件](https://effekseer.github.io/contributes/Effekseer01.zip) · EFKPROJ / textures / ZIP | 无需 | **免费** — 官方公开示例效果包免费；按具体包核对许可。 [收费依据](https://effekseer.github.io/en/contribute.html)。 公开示例效果包；多数 CC0；旧包另有许可，按页面分区及包内说明核对。 |
| [TextureCan](https://www.texturecan.com/)<br>材质、3D | [Paper 0037 / 1K](https://www.texturecan.com/details/658/)<br>[文件](https://www.texturecan.com/downloads/paper_0037/paper_0037_1k_kV5kti.zip) · JPG/PNG / ZIP | 无需 | **免费** — 公开 PBR 贴图与模型免费。 [收费依据](https://www.texturecan.com/terms/)。 公开 PBR 贴图与模型；公开资产 CC0，保留具体页面及 Terms。 |
| [Incompetech](https://incompetech.com/music/royalty-free/music.html)<br>音频 | [Bright Wish](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100377)<br>[文件](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Bright%20Wish.mp3) · MP3 | 无需 | **部分免费 / 含付费** — 单曲可按署名许可免费使用；免署名许可与整库下载收费。 [收费依据](https://incompetech.com/music/royalty-free/music.html)。 单曲免费署名路线；无署名许可和整库下载可能收费；免费路线按曲目 CC BY 4.0 署名，保留曲名、作者和许可链接。 |

KayKit 示例的三个文件应保留同目录关系。Poly Haven 示例仅包含 Diffuse 通道，完整材质需按用途获取其他通道；Effekseer 效果工程需要对应的制作工具和引擎运行库。Godot 控制器包应先检查代码、依赖与目标引擎版本，再导入工程验证。

## 需要登录或额外操作

**账号要求与获取流程分别列出。** 标为“按条目/路线”的来源可能允许部分内容免登录，但仍需经过下载页、领取或专用工具。助手可完成已授权的普通浏览器操作；账号登录等需要身份验证的步骤由用户完成。

| 来源 / 覆盖类型 | 是否需要账号 | 获取路径 / 用户需要补的一步 | 收费方式、使用条件 / 官方说明 |
| --- | --- | --- | --- |
| [Quaternius](https://quaternius.com/)<br>3D、动画 | 按条目/路线 | 通过作者页面进入 Google Drive / itch.io 等获取所选版本；免费与付费文件可能位于同一下载页。<br>打开作者给出的包链接；如出现登录或领取由用户完成，再取得原始包。 | **部分免费 / 含付费** — 许多模型包及 Standard 版免费；部分 Pro、Source 版和扩展包付费。 [收费依据](https://quaternius.itch.io/universal-animation-library/purchase)。 [Survival 示例包](https://quaternius.com/packs/survival.html)通过 Drive 获取；免费版、扩展版与合集分别核对。 |
| [itch.io Game Assets](https://itch.io/game-assets)<br>2D、3D、UI、材质、VFX、动画、音频、字体、模块 | 按条目/路线 | 免费/零价包可能需跳过捐赠、进入下载页后取得会话链接；不一律要求账号。<br>按具体包完成浏览器下载；仅在条目要求账号或领取时请用户操作。 | **部分免费 / 含付费** — 包含免费、可零价下载和付费包；同一包的额外文件可能收费。 [收费依据](https://itch.io/docs/creators/pricing)。 [定价说明](https://itch.io/docs/creators/pricing)：零价下载与付费文件可以共存，应确认所需文件是否包含在免费版本中。 |
| [Mixamo](https://www.mixamo.com/)<br>3D、动画 | 需要 | Adobe ID 登录后选角色、动作和导出格式。<br>用户登录可用的 Adobe ID；保留所选模型/骨架、动作与导出设置。 | **免费** — 角色、动画及自动绑定服务免费；需要可用的个人 Adobe ID，无需 Creative Cloud 订阅。 [收费依据](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)。 [官方 FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html)列出账号类型与地区限制；自动绑定主要面向双足人形角色。 |
| [Sketchfab](https://sketchfab.com/3d-models)<br>3D、动画 | 需要 | 筛选 Downloadable，逐模型核对许可，登录后下载；付费购买进入作者对应的 Fab 页面。<br>下载后可用 local 方式登记；本工具未集成其 Download API。 | **部分免费 / 含付费** — 免费可下载模型；付费商店已迁至 Fab。[下载认证要求](https://sketchfab.com/developers/download-api/guidelines)与 [Fab 上线说明](https://www.unrealengine.com/blog/fab-epics-new-unified-content-marketplace-launches-today)。并非每个展示模型都可下载或适合商用；逐项保存许可、作者与署名。 |
| [Fab](https://www.fab.com/)<br>2D、3D、UI、材质、VFX、动画、音频、模块 | 按条目/路线 | 部分免费文件可匿名接受 EULA 后下载；加入库需登录，UE/UEFN 内容走 Launcher/集成。<br>按所选文件完成 EULA/领取流程；需要个人库或引擎专用格式时用户登录 Epic 账号。 | **部分免费 / 含付费** — 包含免费与付费资产；限时免费、许可档位及领取期限逐项核实。 [收费依据](https://dev.epicgames.com/documentation/en-us/fab/purchasing-and-downloading-assets-in-fab)。 [获取说明](https://dev.epicgames.com/documentation/en-us/fab/purchasing-and-downloading-assets-in-fab)：下载方式取决于格式；普通文件、个人库与引擎专用内容分别处理。 |
| [Unity Asset Store](https://assetstore.unity.com/)<br>2D、3D、UI、材质、VFX、动画、音频、模块 | 需要 | 使用 Unity ID 领取免费包或购买已授权的付费包，再由相同账号在 Package Manager 获取。<br>用户登录、Add to My Assets，然后在目标 Unity 工程下载；先核对版本与管线。 | **部分免费 / 含付费** — 包含免费与付费资产；以具体包和许可选项的当前价格为准。 [收费依据](https://docs.unity.com/en-us/asset-store/downloads/purchase-asset-packages)。 [下载说明](https://docs.unity.com/en-us/asset-store/downloads/purchase-asset-packages)：商店与编辑器使用相同 Unity ID；核对素材包对应的 Unity 版本和渲染管线。 |
| [Freesound](https://freesound.org/)<br>音频 | 需要 | 注册账号登录后在音频详情页下载原文件。<br>用户登录后下载选定文件；网页试听地址不能冒充原文件下载地址。 | **免费** — 公开声音免费下载；需要账号，许可按单条音频核对。 [收费依据](https://freesound.org/help/faq/)。 [官方 FAQ](https://freesound.org/help/faq/)说明下载与署名要求；逐音频核对 CC0、CC BY 或非商业许可。 |
| [CraftPix](https://craftpix.net/)<br>2D、UI、VFX、动画 | 需要 | 注册或登录后从 Freebies 下载免费版本；付费包或订阅内容按已取得的权益获取。 | **部分免费 / 含付费** — Freebies 免费；付费素材包和订阅内容另列。 [收费依据](https://craftpix.net/freebies/)。 [UI 素材示例](https://craftpix.net/freebies/free-kids-math-game-ui-kit-numbers-counting/)；使用范围按 [File License](https://craftpix.net/file-licenses/)核对，Premium 内容另行区分。 |
| [Blendkit（原 BlenderKit）](https://www.blendkit.com/)<br>3D、材质、HDRI、模块 | 按条目/路线 | 通过官方集成取资产；官方说明免费插件可免登录，其他资产的账户要求按所选条目。<br>准备对应集成，按预算选择 Free、Full Plan 或插件；需要账户时用户登录，付费内容按已有购买或订阅权益获取。 | **部分免费 / 含付费** — Free 内容免费；Full Plan 内容和部分插件付费。 [收费依据](https://www.blendkit.com/get-blender-add-ons/)。 [集成说明](https://www.blendkit.com/get-blender-add-ons/)与 [许可说明](https://www.blendkit.com/docs/licenses/)；程序材质用于游戏时可能需要烘焙或转换。 |

免费与付费版本都可以作为候选，按本轮预算和实际授权选择。Mixamo 免费但需要可用的个人 Adobe ID；Quaternius 的 Standard 与 Pro/Source、Blendkit 的 Free 与 Full Plan 分别核对。Freesound 混有 CC0、CC BY 和非商业许可。每站收费依据、许可入口及版本限制见机器目录的 `pricing`、`license_hint`、`evidence_urls` 和 `notes`。

## 目录字段与维护

`pricing.model` 使用 `free`、`mixed`、`paid`、`unknown`，分别对应免费、部分免费/含付费、付费、待核实；`summary` 说明收费范围，`checked_at` 与 `evidence_urls` 保存该判断的核查日期与官方依据。价格核查与文件下载的 `verification` 独立维护，不能更新价格后顺便刷新旧下载哈希的日期。旧目录缺少价格字段时按 `unknown` 筛选，不从免登录或可下载推断免费。`free_scope` 保留具体免费内容范围，兼容已有调用。

`download.mode` 是 `direct` 或 `user-step`；`download.login` 独立使用 `none`、`required`、`conditional`、`unknown`。`access` 字段提供获取方式摘要，筛选使用 `download`。`verification` 保存检查日期、状态、样例页、格式、文件入口、字节数、哈希及适用范围。样例 URL 用于重现获取，使用前回到当前页面确认版本；不存账号、Cookie 或临时签名 URL。

新增来源先核对作者/官方入口、免费与付费范围、实际文件、许可证据和登录步骤。有至少一个匿名完整文件通过获取及基本格式检查才归入 `direct`；其余保留真实步骤和未测范围。下载失败不能用首页可访问替代；失效或政策变化时更新该条目的日期、状态和分类。素材内容变化应重新核验哈希，不能机械把旧样例哈希用于另一个版本。更新目录时同步本页与首页专栏，运行 `python -m unittest discover -s tests -p test_asset_sources.py`。

## 搜索入口

在工具包根调用：

```sh
python tools/asset_library.py sources --kind animation --query "humanoid locomotion"
python tools/asset_library.py sources --kind 3d --pricing mixed
python tools/asset_library.py sources --kind texture --pricing free --access direct
python tools/asset_library.py sources --kind vfx --access direct --query "pixel explosion"
python tools/asset_library.py sources --kind animation --access user-step --login required
python tools/asset_library.py search --kind 3d --query "wood crate" --limit 8
python tools/asset_library.py files --asset 实际PolyHaven编号
```

`sources` 支持按类型、收费类别（`--pricing`）、获取模式和账号要求组合筛选，返回分类目录、核验范围和搜索词，由模型使用宿主的网页搜索/浏览器继续检索，**不是实际资产搜索结果**。`search` 和 `files` 查询 Poly Haven 实时 API，结果明确标注 Poly Haven；关键词匹配名称/标签，不提供自动翻译或语义搜索。文件列表保留分辨率、格式和 include 依赖，模型应选择所需版本并保持相对路径。API 使用要求向用户标明 Poly Haven 来源，见 [官方 API 说明](https://polyhaven.com/our-api)。

`--pricing` 精确匹配来源类别：`free` 不包含 `mixed` 网站中的免费包；寻找所有免费候选时可不加收费筛选，再检查 `free_scope` 和具体资产。`paid` 只匹配纯付费来源，不包含混合网站中的付费包；当前没有纯付费来源时返回空列表。

带查询参数的稳定公开下载入口可用于当次请求；登记保留去除查询参数的下载来源和原素材页，复现入口看目录或当前原站。需要登录的网站由用户完成登录；不绕过商店领取、验证码或专用下载流程。下载 URL 应从实际页面/API 获取，不猜测链接。不支持普通 HTTPS 文件下载的资源先通过商店获取到项目内，再走 local 登记。

## 统一获取

游戏项目内保存请求，例如 `production/acquire-crate.json`：

```json
{
  "title": "选定的木箱", "kind": "3d", "source_id": "polyhaven",
  "source_url": "https://polyhaven.com/a/实际资产编号",
  "author": "原页面作者", "version": "选定版本或下载日期",
  "license": {"name": "CC0", "status": "reviewed", "evidence_files": ["production/licenses/crate-license.txt"]},
  "files": [
    {"name": "crate.glb", "url": "https://实际文件地址/crate.glb"}
  ]
}
```

示例中的地址和作者需要替换，许可证据必须是已保存的原始许可或核查记录。无法确认许可时用 `name: "unknown", status: "unverified"`，不假称允许商用。每个文件可选择 `url` 或项目相对路径 `local`，可选 `sha256` 校验原站给定的 SHA-256。ZIP 可设置 `extract: true`；带代码的包保留压缩文件，按原生工具的导入流程处理。依赖应逐个列出并保留文件关系。

```sh
python tools/asset_library.py --project "MyGame" acquire --request production/acquire-crate.json
python tools/asset_library.py --project "MyGame" list --query crate
python tools/asset_library.py --project "MyGame" verify
python tools/asset_library.py --project "MyGame" index --out production/asset-index-01.md
```

下载限制可用请求的 `max_download_bytes` 设置，默认单文件 1 GiB，上限 8 GiB。只接受公共 HTTPS 地址，拒绝覆盖目标、HTML 登录页、空文件、哈希不符及不安全 ZIP 路径。失败保留记录和已获取文件，不声明整包成功；相同请求与有效文件可复用，修改本地输入或许可证据产生新版本。

文件写到 `assets-source/AS编号/`，记录和许可副本写到 `.openaigame/asset-library/AS编号/`。记录包括作者、来源页、版本、文件哈希、获取状态，以及去除查询参数的下载来源；临时签名下载地址不进入记录。来源页应填写公开页面。生成 Markdown 索引不会覆盖既有 GDD 或美术文档，由助手把选定资产 ID、用途及索引链接写回 Art Direction.md/资产规格。

## 登记生成结果

使用同样的来源/许可元数据请求，省略 files，通过已成功的生成任务登记：

```sh
python tools/asset_library.py --project "MyGame" from-job --job A实际编号 --request production/generated-asset-metadata.json
```

记录关联生成任务、提供器和云任务编号，引用原产物而不重复复制。元数据的 source_url 填所用服务页面，许可依据取账户对应的条款。获取、许可核查、美术质检、引擎导入分别记录；统一登记工具不会直接修改引擎资产或证明游戏内效果。
