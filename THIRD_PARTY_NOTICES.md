# Third-Party Code and Asset Notices

[English](THIRD_PARTY_NOTICES.md) | [简体中文](THIRD_PARTY_NOTICES.zh-CN.md)

The toolkit's own code, skills, templates, and documentation use the [MIT License](LICENSE). Third-party code and assets retain their respective terms. This project's MIT license does not alter their copyright, trademark, or asset permissions.

## Bundled Code

The workbench includes Three.js 0.186.0 (r186) builds and addons, preserving original code and copyright comments. See the [original Three.js MIT license](tools/workbench/web/vendor/three/LICENSE). Other bundled components retain their own licenses.

| Component | Applicable license / notice |
| --- | --- |
| Draco, Basis Universal, Chevrotain | Apache-2.0; Basis NOTICE, Draco authors, and dependency notices are also retained |
| Earcut, potpack | ISC |
| fflate, lil-gui, meshoptimizer, motion-controllers, stats.js, surfaceNet, Tween.js, ktx-parse | Their respective MIT licenses |
| MikkTSpace JS/WASM | MIT wrapper; Zlib original algorithm; Rust dependencies under their respective licenses |
| zstddec / Zstandard | MIT wrapper, BSD-3-Clause Zstandard; the upstream Apache-2.0 alternative is also included |
| UTIF, UZIP, pako, JPEG decoder portions | Their respective MIT / Zlib / Apache-2.0 notices |
| EXRLoader, SculptGL-derived code | TinyEXR BSD-3-Clause; [SculptGL MIT](tools/workbench/web/vendor/three/examples/jsm/misc/SculptGL.LICENSE.txt) |
| demuxer_mp4.js derived from the W3C WebCodecs sample | W3C Software and Document License |
| gl-matrix code referenced in Three.js and dependencies such as Chevrotain's regexp-to-ast | Their respective MIT / Apache-2.0 notices |

See the [license index](licenses/README.md) and [component inventory](licenses/third-party-sources.json) for full texts, sources, and coverage. Original inline notices remain effective. A dependency's license-source version is not a verified embedded-binary version. The Three.js files are identified by the r186 distribution and file hashes.

demuxer_mp4.js is distributed with Three.js and derives from the [W3C WebCodecs video-decode-display sample](https://w3c.github.io/webcodecs/samples/video-decode-display/). Copyright © World Wide Web Consortium. It is provided as distributed in Three.js, with no further toolkit modifications. The sample's remote MP4Box module is not copied into this toolkit and is not a workbench dependency.

## Icons and UI Examples

- The OpenAIGamesDesigner mark is supplied by the project owner. The software's MIT license grants no trademark rights to the name or mark and implies no endorsement of derivative products.
- Tripo, Tencent Hunyuan, ElevenLabs, and ByteDance Seed icons identify configurable third-party services. Brand rights remain with their owners; see [icon sources](tools/settings-ui/logos/README.md). These icons are not relicensed under the project's MIT license.
- Game screenshots in the README demonstrate the tools. Third-party characters and assets remain the property of their rights holders. The repository and installation bundle do not distribute the game models or audio shown in those screenshots.

## External Services and User Assets

Separately installed Python runtimes, game engines, MCP servers, generation services, and other dependencies are subject to their own licenses and terms. The toolkit includes no service credits, keys, or game-asset licenses. Asset-catalog links do not grant permissions; check the specific resource page before use.

The distribution retains the toolkit LICENSE in each skill directory and this notice, full third-party license texts, and original component notices in `game-preproduction/runtime`.
