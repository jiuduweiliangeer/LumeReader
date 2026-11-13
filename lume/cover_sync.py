"""Restore only Lume-managed USB library thumbnails, without changing books."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import uuid
from .covers import fingerprint
from .model import ConversionError

THUMB_NAME=re.compile(r'thumbnail_[A-Za-z0-9_-]{8,64}_(PDOC|EBOK)_portrait\.jpg')


def _owned(root,*parts):
    path=root.joinpath(*parts)
    for item in (path,*path.parents):
        if item==root: break
        if item.is_symlink():
            raise ConversionError('封面路径不能指向链接文件。')
    if root not in path.resolve().parents:
        raise ConversionError('封面路径不在当前设备内。')
    return path


def _atomic_write(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    partial=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.lume-part')
    try:
        with partial.open('xb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        partial.replace(path)
        if path.read_bytes()!=data:
            raise ConversionError('封面回读校验不一致。')
    finally:
        partial.unlink(missing_ok=True)


def _book_path(documents,relative):
    relative=PurePosixPath(str(relative).replace('\\','/'))
    if (relative.is_absolute() or not relative.parts
            or any(p in ('.','..') or ':' in p or p.casefold().endswith('.sdr') for p in relative.parts)
            or relative.suffix.lower() not in ('.kfx','.mobi','.azw','.azw3')):
        raise ConversionError('无效的封面关联书籍路径。')
    return _owned(documents,*relative.parts)


def store_usb_cover(documents,book,thumbnail,book_digest):
    documents=Path(documents).resolve(strict=True)
    book=Path(book).resolve(strict=True)
    relative=book.relative_to(documents).as_posix()
    book=_book_path(documents,relative)
    name,data=thumbnail
    if not THUMB_NAME.fullmatch(name) or not data.startswith(b'\xff\xd8'):
        raise ConversionError('无效的 Kindle 封面缩略图。')
    device_root=documents.parent
    target=_owned(device_root,'system','thumbnails',name)
    cache=_owned(device_root,'system','lume-cover-cache',name)
    record=_owned(device_root,'system','lume-cover-cache',name+'.json')
    entries=[]
    try:
        saved=json.loads(record.read_text(encoding='utf-8'))
        if saved.get('version')==1 and isinstance(saved.get('books'),list):
            entries=[item for item in saved['books']
                     if isinstance(item,dict) and item.get('path')!=relative]
    except (OSError,ValueError,AttributeError):
        pass
    stat=book.stat()
    entries.append({'path':relative,'size':stat.st_size,'mtime_ns':stat.st_mtime_ns,'sha256':book_digest})
    cover_hash=hashlib.sha256(data).hexdigest()
    payload=json.dumps({'version':1,'sha256':cover_hash,'books':entries},ensure_ascii=False).encode('utf-8')
    _atomic_write(target,data)
    _atomic_write(cache,data)
    _atomic_write(record,payload)
    return {'path':str(target),'sha256':cover_hash,'verified':True,'cached':True}


def restore_usb_covers(device,progress=None):
    result={'restored':0,'errors':[]}
    if device.kind!='usb': return result
    progress=progress or (lambda text:None)
    documents=Path(device.path).resolve(strict=True)
    device_root=documents.parent
    cache_dir=_owned(device_root,'system','lume-cover-cache')
    if not cache_dir.is_dir(): return result
    for record in cache_dir.glob('thumbnail_*.jpg.json'):
        name=record.name[:-5]
        if not THUMB_NAME.fullmatch(name): continue
        try:
            record=_owned(device_root,'system','lume-cover-cache',record.name)
            if record.stat().st_size>256*1024:
                raise ConversionError('封面缓存记录过大。')
            saved=json.loads(record.read_text(encoding='utf-8'))
            if saved.get('version')!=1: continue
            # Never restore a cover whose associated book has been removed.
            present=False
            for entry in saved.get('books',[]):
                try:
                    book=_book_path(documents,entry['path'])
                    stat=book.stat()
                    if not book.is_file() or stat.st_size!=entry['size']: continue
                    if stat.st_mtime_ns!=entry['mtime_ns'] and fingerprint(book)!=entry['sha256']: continue
                    present=True
                    break
                except (OSError,ValueError,KeyError,TypeError,ConversionError):
                    continue
            if not present: continue
            cached=_owned(device_root,'system','lume-cover-cache',name)
            if cached.stat().st_size>2*1024**2:
                raise ConversionError('封面缩略图过大。')
            data=cached.read_bytes()
            if not data.startswith(b'\xff\xd8') or hashlib.sha256(data).hexdigest()!=saved['sha256']:
                raise ConversionError('封面缓存校验失败。')
            target=_owned(device_root,'system','thumbnails',name)
            if target.is_file() and fingerprint(target)==saved['sha256']: continue
            _atomic_write(target,data)
            result['restored']+=1
            progress(f"恢复 Kindle 书架封面 · {result['restored']} 张")
        except (OSError,ValueError,KeyError,TypeError,AttributeError,ConversionError) as exc:
            result['errors'].append(name+'：'+str(exc))
    return result