"""Remove fixed pixel/point font sizes before compiling reflowable KF8."""
import re
from .model import Resource
from .util import body_root,fragment

ABSOLUTE_SIZE=re.compile(r'(font-size\s*:\s*)([0-9]*\.?[0-9]+)\s*(px|pt)\b',re.I)

def relative_css(css):
    def replace(match):
        px=float(match[2])*(4/3 if match[3].lower()=='pt' else 1)
        return match[1]+f'{px/18:g}em'
    return ABSOLUTE_SIZE.sub(replace,css)

def unlock_font_sizes(book):
    for ch in book.chapters:
        ch.css=relative_css(ch.css)
        root=body_root(ch.body)
        for el in root.xpath('.//*[@style]'):
            el.set('style',relative_css(el.get('style')))
        ch.body=fragment(root)
    for key,r in list(book.resources.items()):
        if r.media_type=='text/css':
            book.resources[key]=Resource(r.href,relative_css(r.data.decode('utf-8',errors='replace')).encode('utf-8'),r.media_type)
