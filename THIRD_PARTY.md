# Third-party components

Lume's original source is distributed under AGPL-3.0-only. Third-party components retain their original licenses and notices; GPLv3/AGPLv3 combinations follow section 13 of those licenses. User documents, fonts and conversion results are not licensed by this project.

| Component | Upstream / revision | License | Local use |
|---|---|---|---|
| KindleUnpack | https://github.com/kevinhendricks/KindleUnpack · bf0ca6ece4e73494625e7950be3e259b6260774c | GPL-3.0 | vendor/kindleunpack, unencrypted MOBI/KF8 decoding and splitting |
| kfxgen | https://github.com/jloutsch/kfxgen · a1d24e28cfcd876accfc0c92a26a8626b8e168b3 | GPL-3.0 | vendor/kfxgen, standalone native KFX generator |
| kfxlib | https://github.com/jaltez/kindle2epub · 2c69dfd86f52edd703247d9ae2a080b454f50048 | GPL-3.0 | vendor/kfxlib, John Howell's KFX parser, only unencrypted decoding library |

License copies: vendor/KINDLEUNPACK-LICENSE.txt, vendor/KFXGEN-LICENSE.txt, vendor/KFXGEN-NOTICE.txt, vendor/KFXLIB-LICENSE.txt. Original file notices remain in place.

Local adaptations:
- Removed optional Calibre integration imports from the standalone kfxlib utility/output path; use lxml's soup parser directly.
- Added an optional native-generator line-height baseline override, set by Lume to 1.2.
- Added a native-generator content-type override: EBOK for older USB Kindles such as Voyage, PDOC for modern MTP models.
- Calibre adapter modules present in upstream packages are not called by Lume. The application neither imports Calibre nor invokes its executables.
- Windows WPD transport is implemented in lume/wpd.py against Microsoft type libraries using comtypes. API usage was checked against Microsoft WPD interfaces and the MIT-licensed https://github.com/Heribert17/mtp examples. The mtp package itself is not a runtime dependency.
- Kindle send-path and thumbnail conventions were researched from https://github.com/kovidgoyal/calibre/tree/master/src/calibre/devices; its driver is not used at runtime.

Python/Qt dependencies are listed with versions in requirements.txt; their installed distribution metadata retains their individual licenses. PyQt6 / Qt, PyMuPDF, fontTools, ReportLab, Pillow, lxml, cssselect2, tinycss2, BeautifulSoup and comtypes are third-party packages.

Amazon KindleGen is an optional, separately installed executable discovered locally. It is not bundled or redistributed here.

## Windows release

Exact versions, source retrieval links and retained licenses: [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md). Application source is published with each release. Original SVG/PNG/ICO artwork uses AGPL-3.0-only. Private user fonts, novels, device data and KindleGen are not redistributed. The three explicitly licensed bundled fonts are listed below.

Release compatibility adaptation: deferred type annotation evaluation in bundled formula helpers for Python 3.9. Original headers and licenses retained. Files: vendor/kfxgen/vendor/latex2mathml/symbols_parser.py.


## Added in 1.1

- Markdown rendering: markdown-it-py 3.0.0 and mdurl 0.1.2, MIT; retained licenses in `licenses/markdown-it-py` and `licenses/mdurl`.
- Bundled reading fonts retain their own terms and are not relicensed under AGPL. LXGW WenKai Regular and Yozai Light: SIL Open Font License 1.1. Huiwen-mincho improved: font metadata declares Public Domain. Unmodified binaries, license texts, original metadata and SHA256 records are in `lume/assets/fonts/`; details in [docs/FONTS.md](docs/FONTS.md).
- Factual Kindle model/serial-prefix identifiers in `lume/assets/device_ids.json` were checked against [NiLuJe/KindleTool kindle_tool.h](https://github.com/NiLuJe/KindleTool/blob/master/KindleTool/kindle_tool.h). No KindleTool executable is used or bundled. Unknown identifiers remain unknown and can be selected manually.
- ENEX / ENML export follows [Evernote's documented file format](https://dev.evernote.com/legacy/doc/articles/enml.php); no Evernote SDK or online service is called.
