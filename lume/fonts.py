"""Bundled, licensed fonts plus the user's own font directory."""
from pathlib import Path
from .paths import APP_ROOT

FONT_ROOT=APP_ROOT/'lume'/'assets'/'fonts'
BUNDLED=(('霞鹜文楷 · 内置','LXGWWenKai-Regular.ttf'),
         ('汇文明朝 · 内置','Huiwenmincho-improved.ttf'),
         ('悠哉字体 · 内置','Yozai-Light.ttf'))


def available_fonts(directory):
    seen=set()
    for title,name in BUNDLED:
        path=FONT_ROOT/name
        if path.is_file() and path.stat().st_size>=12:
            seen.add(str(path.resolve()).casefold());yield title,str(path)
    folder=Path(directory)
    if folder.is_dir():
        for path in sorted([*folder.rglob('*.ttf'),*folder.rglob('*.otf')],key=lambda p:p.name)[:300]:
            key=str(path.resolve()).casefold()
            if key not in seen and path.stat().st_size>=12:
                seen.add(key);yield path.stem+' · 本地',str(path)


def allow_subset(path):
    # The author's KingHwa licence prohibits modified font files.
    name=Path(path).stem.casefold()
    return not any(x in name for x in ('京華','京华','kinghwa'))