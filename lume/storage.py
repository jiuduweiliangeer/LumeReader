import json
from pathlib import Path
from .model import Layout
from .paths import USER_ROOT as ROOT
DATA = ROOT / 'data'

def load_json(name, default):
    try:
        return json.loads((DATA / name).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return default

def save_json(name, data):
    DATA.mkdir(parents=True,exist_ok=True)
    target = DATA / name
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding='utf-8')
    temp.replace(target)

def settings():
    result = {'layout': Layout().to_dict(), 'output': str(ROOT / 'output'), 'kindlegen': '',
              'font_dir': str(ROOT / 'fonts'), 'last_input': str(Path.home() / 'Documents')}
    saved = load_json('settings.json', {})
    result.update({key: value for key, value in saved.items() if key != 'layout'})
    result['layout'].update(saved.get('layout', {}))
    return result
