"""Book covers and Kindle library thumbnails."""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import re
import struct
from PIL import Image,ImageOps
from .model import Resource,ConversionError

def image_jpeg(data,max_size=(1600,2560)):
    try:
        with Image.open(io.BytesIO(data)) as image:
            image=ImageOps.exif_transpose(image)
            image.thumbnail(max_size,Image.Resampling.LANCZOS)
            background=Image.new('RGB',image.size,'white')
            if image.mode in ('RGBA','LA') or 'transparency' in image.info:
                rgba=image.convert('RGBA')
                background.paste(rgba,mask=rgba.getchannel('A'))
            else:
                background.paste(image.convert('RGB'))
            out=io.BytesIO()
            background.save(out,'JPEG',quality=90,optimize=True)
            return out.getvalue()
    except Exception as exc:
        raise ConversionError('无法读取封面图片，请选择有效的 JPG / PNG / WebP。') from exc

def apply_cover(book,path):
    if not path: return
    source=Path(path)
    if not source.is_file() or source.stat().st_size>32*1024**2:
        raise ConversionError('封面图片不存在或大于 32 MB。')
    data=image_jpeg(source.read_bytes())
    book.cover_href='images/lume-cover.jpg'
    book.resources[book.cover_href]=Resource(book.cover_href,data,'image/jpeg')

def fingerprint(path):
    h=hashlib.sha256()
    with open(path,'rb') as f:
        for block in iter(lambda:f.read(1024**2),b''): h.update(block)
    return h.hexdigest()

def cache_dir():
    from .storage import ROOT
    folder=ROOT/'.cache'/'covers'
    folder.mkdir(parents=True,exist_ok=True)
    return folder

def remember(book,path):
    if not book.cover_href or not book.device_asin: return
    cover=book.resources.get(book.cover_href)
    if not cover: return
    key=fingerprint(path)
    thumb=image_jpeg(cover.data,(330,500))
    folder=cache_dir()
    (folder/(key+'.jpg')).write_bytes(thumb)
    (folder/(key+'.json')).write_text(json.dumps({
        'asin':book.device_asin,'type':book.device_cdetype,
        'thumbnail':key+'.jpg'},ensure_ascii=False),encoding='utf-8')

def pdb_metadata(path):
    from kindleunpack.mobi_split import read_exth,readsection,getint
    data=Path(path).read_bytes()
    header=readsection(data,0)
    def first(key):
        values=read_exth(header,key)
        return values[0] if values else b''
    asin=(first(113) or first(504)).decode('ascii',errors='ignore')
    kind=first(501).decode('ascii',errors='ignore') or 'PDOC'
    offset=first(201)
    cover=b''
    if len(offset)==4:
        index=getint(header,108)+struct.unpack('>I',offset)[0]
        cover=readsection(data,index)
    return asin,kind,cover

def thumbnail_for(path):
    path=Path(path)
    if path.suffix.lower() not in ('.kfx','.azw3','.mobi','.azw'): return None
    key=fingerprint(path)
    folder=cache_dir()
    info=folder/(key+'.json')
    if info.is_file():
        meta=json.loads(info.read_text(encoding='utf-8'))
        data=(folder/(key+'.jpg')).read_bytes()
        asin,kind=meta['asin'],meta['type']
    else:
        if path.suffix.lower()=='.kfx':
            from kfxlib.yj_book import YJ_Book
            meta=YJ_Book(str(path)).get_metadata()
            asin,kind=meta.asin,meta.cde_content_type
            cover=meta.cover_image_data[1] if meta.cover_image_data else b''
        else:
            asin,kind,cover=pdb_metadata(path)
        if not cover or not asin: return None
        data=image_jpeg(cover,(330,500))
    if not re.fullmatch(r'[A-Za-z0-9_-]{8,64}',str(asin)) or kind not in ('PDOC','EBOK'):
        return None
    return f'thumbnail_{asin}_{kind}_portrait.jpg',data
