"""Browse and manage Kindle documents through USB or Windows WPD."""
from __future__ import annotations
from dataclasses import dataclass, asdict
from pathlib import Path, PurePosixPath
import ctypes
import hashlib
import json
import os
import shutil
import uuid
from .devices import Device, digest
from .model import ConversionError
from .util import reserve_output

BOOK_FORMATS={'.azw3','.mobi','.kfx','.pdf','.txt','.azw','.azw8','.prc','.epub','.fb2','.cbz','.tpz'}
FOLDER_TYPE='{27E2E392-A111-48E0-AB0C-E17705A05F85}'

@dataclass(frozen=True)
class DeviceBook:
    id: str
    name: str
    path: str
    size: int
    @property
    def title(self):
        return PurePosixPath(self.name).stem
    @property
    def format(self):
        return PurePosixPath(self.name).suffix.lstrip('.').upper()

def device_key(device):
    if not device: return ''
    if device.kind=='mtp':
        info=json.loads(device.path)
        return 'mtp:'+info['id']+':'+info['storage']
    return 'usb:'+os.path.normcase(str(Path(device.path).resolve()))

def _book_file(name):
    return (Path(name).suffix.lower() in BOOK_FORMATS
            and not name.startswith('.') and name.casefold()!='my clippings.txt')

def _safe_relative(value):
    relative=PurePosixPath(value.replace('\\','/'))
    if relative.is_absolute() or not relative.parts or any(p in ('..','.') or ':' in p for p in relative.parts):
        raise ConversionError('无效的设备书籍路径。')
    if any(p.casefold().endswith('.sdr') for p in relative.parts):
        raise ConversionError('批注与阅读记录目录不属于可管理书籍。')
    return relative

def _usb_path(device,book):
    root=Path(device.path).resolve(strict=True)
    relative=_safe_relative(book.path)
    candidate=root.joinpath(*relative.parts)
    for parent in (candidate,*candidate.parents):
        if parent==root: break
        if parent.is_symlink():
            raise ConversionError('不操作指向其他位置的链接文件。')
    resolved=candidate.resolve(strict=True)
    if root not in resolved.parents or not resolved.is_file() or not _book_file(resolved.name):
        raise ConversionError('文件不在当前 Kindle 的书籍目录内。')
    if resolved.stat().st_size!=book.size:
        raise ConversionError('设备书籍已变化，请刷新书架后重试。')
    return resolved

def _mtp_tree(session,content,folder,progress):
    pending=[(folder['id'],'')]
    visited=set()
    books=[]
    while pending:
        parent,prefix=pending.pop()
        if parent in visited: continue
        visited.add(parent)
        for item in session.children(content,parent):
            name=item['name']
            if not name or '/' in name or '\\' in name or name in ('.','..'): continue
            relative=prefix+name
            if item.get('is_folder'):
                if not name.startswith('.') and not name.casefold().endswith('.sdr'):
                    pending.append((item['id'],relative+'/'))
            elif _book_file(name):
                books.append(DeviceBook(item['id'],name,relative,item['size']))
        progress(f'正在读取 Kindle 书架 · 已发现 {len(books)} 本')
    return books

def list_books(device,progress=None):
    progress=progress or (lambda text:None)
    if device.kind=='mtp':
        from .wpd import Session
        info=json.loads(device.path)
        with Session() as session:
            content=session.open(info['id'])
            storage,folder=session.documents(content,info['storage'])
            books=_mtp_tree(session,content,folder,progress)
            free,total=None,None
            try:
                props=content.Properties().GetValues(storage['id'],None)
                group='{01A3057A-74D6-4E80-BEA7-DC4C212CE50A}'
                free=int(props.GetUnsignedLargeIntegerValue(session.key(5,group)))
                total=int(props.GetUnsignedLargeIntegerValue(session.key(4,group)))
            except session.com.COMError: pass
    elif device.kind=='usb':
        root=Path(device.path).resolve(strict=True)
        books=[]
        for directory,dirs,files in os.walk(root,followlinks=False):
            dirs[:]=[name for name in dirs if not name.startswith('.') and not name.casefold().endswith('.sdr')
                     and not (Path(directory)/name).is_symlink()]
            for name in files:
                path=Path(directory)/name
                if _book_file(name) and not path.is_symlink():
                    relative=path.relative_to(root).as_posix()
                    books.append(DeviceBook(relative,name,relative,path.stat().st_size))
        usage=shutil.disk_usage(root)
        free,total=usage.free,usage.total
    else:
        raise ConversionError('不支持的设备连接。')
    books.sort(key=lambda b:(b.title.casefold(),b.path.casefold()))
    return {'books':books,'free':free,'total':total}

def _mtp_validate(session,content,folder,book):
    relative=_safe_relative(book.path)
    parent=folder['id']
    item=None
    for index,part in enumerate(relative.parts):
        item=next((x for x in session.children(content,parent) if x['name']==part),None)
        if not item: raise ConversionError('设备书籍已移动或移除，请刷新书架。')
        if index<len(relative.parts)-1:
            if not item.get('is_folder'): raise ConversionError('设备目录已变化。')
            parent=item['id']
    if (item['id']!=book.id or item['size']!=book.size or item.get('is_folder')
            or not _book_file(item['name'])):
        raise ConversionError('设备书籍已变化，请刷新书架后重试。')
    return item

def _mtp_chunks(session,content,item):
    optimal=ctypes.pointer(ctypes.c_ulong())
    _,reader=content.Transfer().GetStream(item['id'],
        session.key(0,'{E81E79BE-34F0-41BF-B53F-F1A06AE87842}'),0,optimal)
    try:
        while True:
            block,count=reader.RemoteRead(max(4096,min(optimal.contents.value or 65536,1024**2)))
            if not count: break
            yield bytes(block[:count])
    finally:
        reader=None

def _copy_verified(book,destination,chunks,progress):
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    target=reserve_output(destination,Path(book.name).stem,Path(book.name).suffix.lstrip('.'))
    partial=target.with_name('.lume-download-'+uuid.uuid4().hex+'.part')
    value=hashlib.sha256()
    total=0
    try:
        with partial.open('xb') as output:
            for block in chunks:
                output.write(block)
                value.update(block)
                total+=len(block)
                progress(f'保存 {book.name} · {total/max(book.size,1):.0%}')
            output.flush()
            os.fsync(output.fileno())
        if total!=book.size or digest(partial)!=value.hexdigest():
            raise ConversionError('保存文件校验失败，设备书籍未删除。')
        partial.replace(target)
        return {'book':asdict(book),'output':str(target),'sha256':value.hexdigest(),'size':total}
    except BaseException:
        partial.unlink(missing_ok=True)
        if target.exists() and target.stat().st_size==0: target.unlink()
        raise

def export_books(device,books,destination,progress=None):
    progress=progress or (lambda text:None)
    records=[]
    if device.kind=='mtp':
        from .wpd import Session
        info=json.loads(device.path)
        with Session() as session:
            content=session.open(info['id'])
            _,folder=session.documents(content,info['storage'])
            for book in books:
                item=_mtp_validate(session,content,folder,book)
                records.append(_copy_verified(book,destination,_mtp_chunks(session,content,item),progress))
    elif device.kind=='usb':
        for book in books:
            path=_usb_path(device,book)
            with path.open('rb') as source:
                record=_copy_verified(book,destination,iter(lambda:source.read(1024**2),b''),progress)
            if digest(path)!=record['sha256']:
                raise ConversionError('设备书籍在保存时发生变化，请重试。')
            records.append(record)
    else: raise ConversionError('不支持的设备连接。')
    return records

def remove_books(device,books,backup_dir,progress=None):
    """Back up every selection before deleting individual book files, never folders."""
    progress=progress or (lambda text:None)
    records=export_books(device,books,backup_dir,progress)
    manifest=Path(backup_dir)/'backup.json'
    receipt={'device':device.name,'device_key':device_key(device),'files':records,'removed':[]}
    def save_receipt():
        temp=manifest.with_suffix('.json.part')
        temp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(manifest)
    save_receipt()
    def removed(book):
        receipt['removed'].append(book.path)
        save_receipt()
        progress(f'已移除 {book.name} · 本地备份已保留')
    try:
        if device.kind=='mtp':
            from .wpd import Session
            info=json.loads(device.path)
            with Session() as session:
                content=session.open(info['id'])
                _,folder=session.documents(content,info['storage'])
                for book,record in zip(books,records):
                    item=_mtp_validate(session,content,folder,book)
                    value=hashlib.sha256()
                    for block in _mtp_chunks(session,content,item): value.update(block)
                    if value.hexdigest()!=record['sha256']:
                        raise ConversionError('设备书籍已变化，停止删除。')
                    collection=session.create(session.types.PortableDevicePropVariantCollection,
                                              session.port.IPortableDevicePropVariantCollection)
                    prop=session.port.tag_inner_PROPVARIANT()
                    prop.vt=31  # VT_LPWSTR
                    getattr(prop,'__MIDL____MIDL_itf_PortableDeviceApi_0001_00000001').pwszVal=ctypes.c_wchar_p(book.id)
                    collection.Add(prop)
                    # NO_RECURSION: this call can remove a file, never a folder tree.
                    errors=session.create(session.types.PortableDevicePropVariantCollection,
                                          session.port.IPortableDevicePropVariantCollection)
                    content.Delete(0,collection,ctypes.pointer(errors))
                    try:
                        session.item(content,book.id)
                    except session.com.COMError:
                        removed(book)
                    else:
                        raise ConversionError('Kindle 未确认删除，请刷新书架查看。')
        else:
            for book,record in zip(books,records):
                path=_usb_path(device,book)
                if digest(path)!=record['sha256']:
                    raise ConversionError('设备书籍已变化，停止删除。')
                path.unlink()
                removed(book)
    except Exception as exc:
        raise ConversionError(f'{exc}\n已移除 {len(receipt["removed"])} 本；备份位于 {backup_dir}') from exc
    return receipt
