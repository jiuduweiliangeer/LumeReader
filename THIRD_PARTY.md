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
- Calibre adapter modules present in upstream packages are not called by Lume. The application neither imports Calibre nor invokes its executables.
- Windows WPD transport is implemented in lume/wpd.py against Microsoft type libraries using comtypes. API usage was checked against Microsoft WPD interfaces and the MIT-licensed https://github.com/Heribert17/mtp examples. The mtp package itself is not a runtime dependency.
- Kindle send-path and thumbnail conventions were researched from https://github.com/kovidgoyal/calibre/tree/master/src/calibre/devices; its driver is not used at runtime.

Python/Qt dependencies are listed with versions in requirements.txt; their installed distribution metadata retains their individual licenses. PyQt6 / Qt, PyMuPDF, fontTools, ReportLab, Pillow, lxml, cssselect2, tinycss2, BeautifulSoup and comtypes are third-party packages.

Amazon KindleGen is an optional, separately installed executable discovered locally. It is not bundled or redistributed here.

## Windows release

Exact versions, source retrieval links and retained licenses: [docs/DEPENDENCIES.md](docs/DEPENDENCIES.md). Application source is published with each release. Original SVG/PNG/ICO artwork uses AGPL-3.0-only. User fonts, novels, device data and KindleGen are not redistributed.

Release compatibility adaptation: deferred type annotation evaluation in bundled formula helpers for Python 3.9. Original headers and licenses retained. Files: vendor/kfxgen/vendor/latex2mathml/symbols_parser.py.
