"""Reading defaults and visible, device-aware conversion recommendations."""
from dataclasses import dataclass
from functools import lru_cache
import json
import math
import re
from .paths import APP_ROOT

PRESETS={
    'paperwhite6':{'name':'Paperwhite 6 · 7 英寸','font_size':18.,'line_height':1.65,'paragraph_gap':.35,'indent':2.,'margin':18.,'diagonal':7.,'ratio':1264/1680},
    'voyage':{'name':'Voyage · 6 英寸','font_size':18.,'line_height':1.5,'paragraph_gap':.25,'indent':2.,'margin':14.,'diagonal':6.,'ratio':1072/1448},
    'kindle6':{'name':'Kindle 入门版 · 6 英寸','font_size':18.,'line_height':1.55,'paragraph_gap':.3,'indent':2.,'margin':14.,'diagonal':6.,'ratio':.75},
    'paperwhite5':{'name':'Paperwhite 5 · 6.8 英寸','font_size':18.,'line_height':1.6,'paragraph_gap':.3,'indent':2.,'margin':16.,'diagonal':6.8,'ratio':.75},
    'oasis':{'name':'Oasis · 7 英寸','font_size':18.,'line_height':1.6,'paragraph_gap':.3,'indent':2.,'margin':18.,'diagonal':7.,'ratio':.75},
    'scribe':{'name':'Scribe 大屏 · 10.2 英寸','font_size':20.,'line_height':1.55,'paragraph_gap':.3,'indent':2.,'margin':25.,'diagonal':10.2,'ratio':.75},
    'scribe11':{'name':'Scribe 大屏 · 11 英寸','font_size':20.,'line_height':1.55,'paragraph_gap':.3,'indent':2.,'margin':27.,'diagonal':11.,'ratio':.75},
}
MODEL_NAMES={
    'voyage':'Kindle Voyage','paperwhite6':'Kindle Paperwhite 6','paperwhite5':'Kindle Paperwhite 5',
    'paperwhite_small':'Kindle Paperwhite 2 / 3 / 4','kindle6':'Kindle 入门版 · 6 英寸',
    'oasis':'Kindle Oasis','scribe':'Kindle Scribe','scribe11':'Kindle Scribe · 11 英寸',
    'colorsoft':'Kindle Colorsoft','paperwhite1':'Kindle Paperwhite 1',
    'legacy':'Kindle 3 / 4 / Touch','mobi_only':'Kindle 1 / 2 / DX',
}


def preset_values(key):
    p=PRESETS.get(key,PRESETS['paperwhite6'])
    return {**{k:p[k] for k in ('font_size','line_height','paragraph_gap','indent','margin')},
            'screen_profile':key if key in PRESETS else 'paperwhite6'}


def page_size(key):
    if key=='paperwhite6':return 303.36,403.2
    p=PRESETS.get(key,PRESETS['paperwhite6'])
    height=p['diagonal']*72/math.sqrt(1+p['ratio']**2)
    return height*p['ratio'],height


@lru_cache(maxsize=1)
def _device_ids():
    try:return json.loads((APP_ROOT/'lume'/'assets'/'device_ids.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):return {}


def identify_model(name='',serial=''):
    value=name.casefold()
    if 'voyage' in value:return 'voyage'
    if 'scribe' in value:return 'scribe11' if re.search(r'\b11\b|2025|2026',value) else 'scribe'
    if 'oasis' in value:return 'oasis'
    if 'colorsoft' in value:return 'colorsoft'
    if 'paperwhite' in value:
        if re.search(r'paperwhite\s*(1\b|2012)',value):return 'paperwhite1'
        if re.search(r'paperwhite\s*(5\b|2021)',value):return 'paperwhite5'
        if re.search(r'paperwhite\s*(6\b|2024)',value):return 'paperwhite6'
    if re.search(r'\b(dx|kindle 1|kindle 2)\b',value):return 'mobi_only'
    if re.search(r'\bkindle (3|4|5|touch|keyboard)\b',value):return 'legacy'
    if 'basic' in value or '入门' in value:return 'kindle6'
    serial=re.sub(r'[^A-Z0-9]','',serial.upper())
    ids=_device_ids()
    if len(serial)>=8 and serial[:2] in ('B0','90'):
        return ids.get('old:'+serial[2:4],'')
    if len(serial)>=8:
        return ids.get('new:'+serial[3:6],'')
    return ''


@dataclass(frozen=True)
class Recommendation:
    format: str
    reason: str
    kfx_mode: str
    preset: str
    model: str


def recommend(device,compiler=False):
    if not device:return Recommendation('kfx','默认推荐 KFX，可保留目录、字体和封面。','personal','paperwhite6','')
    model=device.model or identify_model(device.name)
    name=MODEL_NAMES.get(model,'Kindle（型号未识别）')
    preset=model if model in PRESETS else ('kindle6' if model in ('paperwhite_small','paperwhite1','legacy','mobi_only') else 'paperwhite6')
    kfx_mode='legacy' if device.kind=='usb' or model=='voyage' else 'personal'
    if model in ('legacy','paperwhite1','mobi_only'):
        fmt=('mobi' if model=='mobi_only' else 'azw3') if compiler else 'pdf'
        reason=(name+'：推荐 '+fmt.upper()+'，此机型不使用 KFX。'
                +('' if compiler else '未配置 KindleGen，先用内置 PDF；配置后可生成 MOBI / AZW3。'))
    elif model=='voyage':
        fmt='azw3' if compiler else 'kfx'
        reason=('Voyage：推荐 AZW3，兼容旧固件与书架封面。' if compiler else
                'Voyage：推荐 KFX（旧款封面兼容）。配置 KindleGen 后可选 AZW3。')
    else:
        fmt='kfx'
        reason=name+'：推荐 KFX。'+('发送时同步旧款书架封面。' if kfx_mode=='legacy' else '使用个人文档封面模式。')
        if not model:reason+=' 可在设备栏手动指定型号。'
    return Recommendation(fmt,reason,kfx_mode,preset,model)