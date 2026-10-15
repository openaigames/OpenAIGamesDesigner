# Game Asset Sources, Acquisition, and Registration

[English](asset-sources.md) | [简体中文](asset-sources.zh-CN.md)

Find project resources by type, pricing, and download conditions, including free/paid content. The catalog favors author/official sites with item pages, files, licenses, and account requirements. Other sources, original work, and authorized generation remain available. Structured data: [sources.json](sources.json).

## Pricing Labels

**Free / mixed (free and paid) / paid / unverified** are independent of account/download requirements. Optional donations are not mandatory fees. Distinguish supporter early access, tools, and public libraries. Source labels do not guarantee that a specific package, format, or license tier is free. The catalog supports paid-only entries as well as free/mixed sources.

Record selected-version price, currency, included files, license, and verification date in project provenance. Record expiry for temporary offers rather than calling them permanently free. Acquire paid assets within existing budget/authorization or register purchased files supplied by users. Listing a site does not mean assets were purchased, downloaded, or licensed.

## Examples without Login

These sources offer public HTTPS downloads. Examples retain concrete files; recheck scope, license, format, and dependencies for other selections. Structured records hold download verification evidence.

| Source / types | Sample files and references | Account | Pricing and license |
| --- | --- | --- | --- |
| [Kenney](https://kenney.nl/assets)<br>2D, 3D, UI, materials, VFX, audio | [Particle Pack](https://kenney.nl/assets/particle-pack) · [Download](https://kenney.nl/media/pages/assets/particle-pack/f8fe0f8cb8-1677578741/kenney_particle-pack.zip) · [Pricing / terms](https://kenney.itch.io/kenney-game-assets) | None | Mixed: individual packs are free; All-in-1 collections are paid. Check each package license. |
| [Poly Haven](https://polyhaven.com/)<br>3D, materials, HDRI | [aerial_rocks_02 / Diffuse 1K](https://polyhaven.com/a/aerial_rocks_02) · [Download](https://dl.polyhaven.org/file/ph-assets/Textures/jpg/1k/aerial_rocks_02/aerial_rocks_02_diff_1k.jpg) · [Pricing / terms](https://polyhaven.com/license) | None | Free public CC0 assets/API; supporter benefits/tools are separate. Credit Poly Haven when using its API. The sample is only a diffuse texture. |
| [ambientCG](https://ambientcg.com/)<br>3D, materials, HDRI | [Wood051 / 1K-JPG](https://ambientcg.com/view?id=Wood051) · [Download](https://ambientcg.com/get?file=Wood051_1K-JPG.zip) · [Pricing / terms](https://docs.ambientcg.com/license/) | None | Free public CC0 assets; supporter benefits are separate. Retain the selected asset page and license. |
| [OpenGameArt](https://opengameart.org/)<br>2D, 3D, UI, materials, VFX, animation, audio, fonts | [80 CC0 RPG SFX](https://opengameart.org/content/80-cc0-rpg-sfx) · [Download](https://opengameart.org/sites/default/files/80-CC0-RPG-SFX_0.zip) · [Pricing / terms](https://opengameart.org/content/faq) | None | Free public assets with varied licenses. Record attribution and conditions per item. |
| [Godot Asset Library](https://godotengine.org/asset-library/asset)<br>Modules, VFX, UI | [Basic FPS Controller for Godot 4 / 1.0.0](https://godotengine.org/asset-library/asset/5421) · [Download](https://github.com/ar-bh/basic-fps-controller-godot/archive/7f50a91a7063106047a06bd8d6c200cdda80f3b2.zip) · [Pricing / terms](https://docs.godotengine.org/en/stable/community/asset_library/what_is_assetlib.html) | None | Free open-source plugins/tools/examples. Follow the source revision LICENSE and inspect code/dependencies before import. |
| [KayKit](https://kaylousberg.com/game-assets)<br>3D, animation | [Prototype Bits / Barrel_A](https://github.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0) · [glTF](https://raw.githubusercontent.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0/main/addons/kaykit_prototype_bits/Assets/gltf/Barrel_A.gltf) · [BIN](https://raw.githubusercontent.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0/main/addons/kaykit_prototype_bits/Assets/gltf/Barrel_A.bin) · [Texture](https://raw.githubusercontent.com/KayKit-Game-Assets/KayKit-Prototype-Bits-1.0/main/addons/kaykit_prototype_bits/Assets/gltf/prototypebits_texture.png) · [Pricing / terms](https://kaylousberg.itch.io/) | None | Mixed: free packs plus paid characters, extras, sources, and collections. Sample is CC0; retain package LICENSE and all three dependencies. |
| [Game-icons.net](https://game-icons.net/)<br>2D, UI | [White on black SVG archive](https://game-icons.net/) · [Download](https://game-icons.net/archives/ffffff/000000/game-icons.net.svg.zip) · [Pricing / terms](https://game-icons.net/faq.html) | None | Free SVG/PNG icons, primarily CC BY 3.0. Record individual authors and required attribution. |
| [Google Fonts](https://fonts.google.com/)<br>Fonts | [Abel Regular](https://github.com/google/fonts/tree/main/ofl/abel) · [Download](https://raw.githubusercontent.com/google/fonts/main/ofl/abel/Abel-Regular.ttf) · [Pricing / terms](https://github.com/google/fonts/blob/main/ofl/abel/OFL.txt) | None | Free fonts under their own OFL/Apache or other licenses. Abel sample uses OFL 1.1. |
| [Lucide](https://lucide.dev/icons/)<br>UI | [swords](https://lucide.dev/icons/swords) · [Download](https://raw.githubusercontent.com/lucide-icons/lucide/main/icons/swords.svg) · [Pricing / terms](https://lucide.dev/license) | None | Free ISC icons; some Feather-derived icons use MIT. Preserve copyright/license notices. |
| [Effekseer Sample Effects](https://effekseer.github.io/en/contribute.html)<br>VFX | [Effekseer01](https://effekseer.github.io/en/contributes/Effekseer01/index.html) · [Download](https://effekseer.github.io/contributes/Effekseer01.zip) · [Pricing / terms](https://effekseer.github.io/en/contribute.html) | None | Free official sample packs, mostly CC0; older sections/packages can differ. Requires authoring tools and engine runtime. |
| [Incompetech](https://incompetech.com/music/royalty-free/music.html)<br>Audio | [Bright Wish](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100377) · [Download](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Bright%20Wish.mp3) · [Pricing / terms](https://incompetech.com/music/royalty-free/music.html) | None | Mixed: free attributed tracks; attribution-free licenses and bulk downloads are paid. Free route uses track-specific CC BY 4.0 credits. |

Keep KayKit's three files together. Poly Haven's sample supplies only Diffuse; acquire other channels as needed. Effekseer needs its tools/runtime. Review controller code, dependencies, and engine compatibility before importing the Godot example.

## Login or Additional Steps

Account requirements and acquisition steps are separate. Conditional routes may permit anonymous content but still need download/claim/tool workflows. Agents can perform authorized ordinary browsing; users handle identity verification.

| Source / types | Official references | Account | Acquisition, pricing, and conditions |
| --- | --- | --- | --- |
| [Quaternius](https://quaternius.com/)<br>3D, animation | [Pricing / terms](https://quaternius.itch.io/universal-animation-library/purchase) · [Survival pack](https://quaternius.com/packs/survival.html) | By item/route | Mixed: many packs/Standard editions are free; Pro/Source/expansions may be paid. Follow author links to Drive/itch.io; user completes login/claim if required. |
| [itch.io Game Assets](https://itch.io/game-assets)<br>2D, 3D, UI, materials, VFX, animation, audio, fonts, modules | [Pricing / terms](https://itch.io/docs/creators/pricing) · [Pricing](https://itch.io/docs/creators/pricing) | By item/route | Mixed: free/zero-price/paid files may coexist. Follow donation/download pages and session links; accounts are required only where specified. |
| [Mixamo](https://www.mixamo.com/)<br>3D, animation | [Pricing / terms](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) · [FAQ](https://helpx.adobe.com/creative-cloud/faq/mixamo-faq.html) | Required | Free characters, animation, and auto-rigging with an eligible personal Adobe ID, without a Creative Cloud subscription. Check account/region limits; rigging mainly targets bipeds. Preserve export settings. |
| [Sketchfab](https://sketchfab.com/3d-models)<br>3D, animation | [Download authentication](https://sketchfab.com/developers/download-api/guidelines) · [Fab announcement](https://www.unrealengine.com/blog/fab-epics-new-unified-content-marketplace-launches-today) | Required | Mixed: downloadable free models; paid sales use Fab. Filter Downloadable, inspect licenses, log in, and register acquired files locally. Download API is not integrated; displayed models are not automatically downloadable/commercially usable. |
| [Fab](https://www.fab.com/)<br>2D, 3D, UI, materials, VFX, animation, audio, modules | [Pricing / terms](https://dev.epicgames.com/documentation/en-us/fab/purchasing-and-downloading-assets-in-fab) · [Acquisition guide](https://dev.epicgames.com/documentation/en-us/fab/purchasing-and-downloading-assets-in-fab) | By item/route | Mixed: free/paid/limited-time offers and license tiers vary. Some files allow anonymous EULA acceptance; personal libraries require login, UE/UEFN content uses Launcher/integration. Users complete identity-dependent steps. |
| [Unity Asset Store](https://assetstore.unity.com/)<br>2D, 3D, UI, materials, VFX, animation, audio, modules | [Pricing / terms](https://docs.unity.com/en-us/asset-store/downloads/purchase-asset-packages) · [Download guide](https://docs.unity.com/en-us/asset-store/downloads/purchase-asset-packages) | Required | Mixed: claim/buy authorized packages with Unity ID, then use the same account in Package Manager. Check Unity version/render pipeline and license tier. |
| [Freesound](https://freesound.org/)<br>Audio | [Pricing / terms](https://freesound.org/help/faq/) · [FAQ](https://freesound.org/help/faq/) | Required | Free downloads after login. Verify each CC0/CC BY/noncommercial license and attribution. Preview URLs are not original downloads. |
| [CraftPix](https://craftpix.net/)<br>2D, UI, VFX, animation | [Pricing / terms](https://craftpix.net/freebies/) · [UI example](https://craftpix.net/freebies/free-kids-math-game-ui-kit-numbers-counting/) · [File License](https://craftpix.net/file-licenses/) | Required | Mixed: Freebies require login; paid packs/subscriptions follow acquired rights. Distinguish Premium content and verify File License. |
| [Blendkit (formerly BlenderKit)](https://www.blendkit.com/)<br>3D, materials, HDRI, modules | [Pricing / terms](https://www.blendkit.com/get-blender-add-ons/) · [Integration](https://www.blendkit.com/get-blender-add-ons/) · [License](https://www.blendkit.com/docs/licenses/) | By item/route | Mixed: Free assets, paid Full Plan content, and some paid add-ons. Use official integration; free add-ons may not require login. Users authenticate when necessary. Procedural materials may require baking for games. |

Both free and paid candidates are valid within task budgets/authorization. Check Mixamo account eligibility, Quaternius Standard versus Pro/Source, Blendkit Free versus Full Plan, and Freesound's varied licenses. Machine records retain pricing, license_hint, evidence_urls, and notes.

## Catalog Fields and Maintenance

pricing.model is free/mixed/paid/unknown. summary describes scope; checked_at/evidence_urls retain dated official evidence. Pricing and download verification are independent: updating price must not refresh an old download hash's date. Missing pricing becomes unknown, not inferred free from anonymous access. free_scope preserves precise free-content scope.

download.mode is direct/user-step. download.login independently uses none/required/conditional/unknown. access summarizes acquisition; filters use download. verification stores check date/status, example page, format, files, bytes, hashes, and scope. Revisit original pages before reuse. Never store accounts, cookies, or temporary signed URLs.

Before adding a source, verify official/author entry, pricing, actual files, licenses, and login steps. direct requires at least one complete anonymous download with basic-format checks; otherwise retain actual steps/unverified scope. Homepage access cannot replace failed downloads. Update changed policies/links/classification and recheck changed-content hashes. Keep this guide and the homepage catalog aligned; run `python -m unittest discover -s tests -p test_asset_sources.py` from the source repository.

## Search Entry Points

From toolkit root:

```sh
python tools/asset_library.py sources --kind animation --query "humanoid locomotion"
python tools/asset_library.py sources --kind 3d --pricing mixed
python tools/asset_library.py sources --kind texture --pricing free --access direct
python tools/asset_library.py sources --kind vfx --access direct --query "pixel explosion"
python tools/asset_library.py sources --kind animation --access user-step --login required
python tools/asset_library.py search --kind 3d --query "wood crate" --limit 8
python tools/asset_library.py files --asset POLY_HAVEN_ASSET_ID
```

sources combines type, --pricing, download-mode, and login filters, returning catalog entries, verification scope, and search terms for further browsing, **not live asset search results**. search/files use the live Poly Haven API and identify that source. Keywords match names/tags without translation/semantic search. File listings retain resolution, format, and include dependencies; choose deliberately and preserve paths. Credit Poly Haven per its [API requirements](https://polyhaven.com/our-api).

--pricing matches exact source categories. free excludes free packs on mixed sites; omit the filter to consider those, then inspect free_scope/items. paid excludes paid packs on mixed sites and may return no entries.

Stable public query URLs may be used for requests; registration strips query strings from download provenance while retaining item pages. Use actual page/API URLs rather than guesses. Users complete login; do not bypass claims, CAPTCHAs, or dedicated downloads. Acquire non-HTTPS-file content through its store, then register project-local files.

## Unified Acquisition

Save a project request such as production/acquire-crate.json:

```json
{
  "title": "Selected crate", "kind": "3d", "source_id": "polyhaven",
  "source_url": "https://polyhaven.com/a/ASSET_ID",
  "author": "Original page author", "version": "Selected revision or acquisition date",
  "license": {"name": "CC0", "status": "reviewed", "evidence_files": ["production/licenses/crate-license.txt"]},
  "files": [
    {"name": "crate.glb", "url": "https://example.com/crate.glb"}
  ]
}
```

Replace example URLs/authors. License evidence must be saved original text or a verification record. If unknown, use name: unknown, status: unverified rather than assuming commercial rights. Each file uses url or project-relative local, with optional provider SHA-256. ZIP can use extract:true; code-bearing packages stay archived for native import review. List dependencies and preserve relationships.

```sh
python tools/asset_library.py --project "MyGame" acquire --request production/acquire-crate.json
python tools/asset_library.py --project "MyGame" list --query crate
python tools/asset_library.py --project "MyGame" verify
python tools/asset_library.py --project "MyGame" index --out production/asset-index-01.md
```

max_download_bytes defaults to 1 GiB per file, up to 8 GiB. Only public HTTPS is accepted. Existing targets, HTML login pages, empty files, hash mismatches, and unsafe ZIP paths fail. Partial files/records remain without claiming whole-package success. Matching requests/valid files can be reused; changed local inputs/license evidence create revisions.

Files go to `assets-source/<asset-id>/`; records/license copies to `.openaigame/asset-library/<asset-id>/`. Records include author, source page, revision, hashes, acquisition status, and query-stripped download provenance. Temporary signed URLs are excluded. Use public source pages. Generated Markdown indexes do not overwrite GDD/art documents; agents link selected IDs, uses, and indexes from Art Direction.md/asset specs.

## Register Generated Results

Use the same provenance/license request without files for a successful job:

```sh
python tools/asset_library.py --project "MyGame" from-job --job JOB_ID --request production/generated-asset-metadata.json
```

Records link job/provider/cloud ID and reference artifacts without recopying. source_url identifies the service; license evidence follows account terms. Acquisition, license review, art checks, and engine import remain separate. Registration neither edits engine assets nor proves in-game quality.
