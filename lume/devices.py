from dataclasses import dataclass
from pathlib import Path
import ctypes
import os
import shutil
import hashlib
import json
from datetime import datetime
from .model import ConversionError
from .util import reserve_output

USB_FORMATS={'.azw3','.mobi','.kfx','.pdf','.txt','.azw'}
SEND_TO_KINDLE_URL='https://www.amazon.com/sendtokindle'

@dataclass
class Device:
    name: str
    kind: str
    path: str
    detail: str=''

def scan_devices():
    if os.name!='nt':
        return []
    devices=[]
    kernel=ctypes.windll.kernel32
    mask=kernel.GetLogicalDrives()
    for i in range(26):
        if not mask & (1<<i):
            continue
        drive=chr(65+i)+':\\'
        if kernel.GetDriveTypeW(drive) not in (2,3):
            continue
        volume=ctypes.create_unicode_buffer(261)
        if kernel.GetVolumeInformationW(drive,volume,261,None,None,None,None,0):
            documents=Path(drive)/'documents'
            if 'kindle' in volume.value.casefold() and documents.is_dir():
                devices.append(Device(volume.value,'usb',str(documents),'USB 磁盘'))
    try:
        from .wpd import scan
        for d in scan():
            devices.append(Device(d['name'],'mtp',json.dumps(d), 'MTP · 已连接'))
    except Exception as exc:
        if not devices:
            raise ConversionError('MTP 检测失败：'+str(exc)) from exc
    return devices

def send_file(source,device,progress=None):
    source=Path(source).resolve()
    if not source.is_file():
        raise ConversionError('要发送的文件不存在。')
    validate_file(source)
    if source.suffix.lower() not in USB_FORMATS:
        raise ConversionError('USB 不直接读取 EPUB/HTML/FB2。请转换为 KFX/AZW3，或用 Send to Kindle 上传 EPUB。')
    progress=progress or (lambda text:None)
    from .covers import thumbnail_for
    thumbnail=thumbnail_for(source)
    if device.kind=='mtp':
        from .wpd import upload
        info=json.loads(device.path)
        result=upload(source,info['id'],info['storage'],progress)
        try:
            if thumbnail:
                from .wpd import upload_thumbnail
                progress('同步 Kindle 书库封面…')
                result['cover']=upload_thumbnail(info['id'],info['storage'],*thumbnail)
        except Exception as exc:
            result['cover_error']=str(exc)
            record_send(source,device,result)
            raise ConversionError('书籍已发送并校验，但封面同步失败：'+str(exc)) from exc
        record_send(source,device,result)
        return result['path']
    folder=Path(device.path)
    if device.kind!='usb' or not folder.is_dir():
        raise ConversionError('USB 目录不可用。MTP 设备请使用资源管理器或 Send to Kindle。')
    if shutil.disk_usage(folder).free<source.stat().st_size+1024**2:
        raise ConversionError('目标设备空间不足。')
    target=reserve_output(folder,source.stem,source.suffix.lstrip('.'))
    partial=target.with_name('.'+target.name+'.lume-part')
    try:
        with open(source,'rb') as src,open(partial,'wb') as dest:
            copied=0
            while True:
                chunk=src.read(1024**2)
                if not chunk:
                    break
                dest.write(chunk)
                copied+=len(chunk)
                progress(f'发送中 · {copied/max(source.stat().st_size,1):.0%}')
            dest.flush()
            os.fsync(dest.fileno())
        if partial.stat().st_size!=source.stat().st_size:
            raise ConversionError('写入大小校验失败。')
        partial.replace(target)
        if digest(source)!=digest(target):
            raise ConversionError('USB 回读校验不一致。')
        result={'path':str(target),'size':target.stat().st_size,
                'sha256':digest(target),'transport':'USB','verified':True}
        if thumbnail:
            try:
                name,data=thumbnail
                thumb_dir=folder.parent/'system'/'thumbnails'
                thumb_dir.mkdir(parents=True,exist_ok=True)
                thumb_path=thumb_dir/name
                thumb_tmp=thumb_dir/(name+'.lume-part')
                thumb_tmp.write_bytes(data)
                thumb_tmp.replace(thumb_path)
                if digest(thumb_path)!=hashlib.sha256(data).hexdigest():
                    raise ConversionError('封面回读校验不一致。')
                result['cover']={'path':str(thumb_path),'sha256':digest(thumb_path),'verified':True}
            except Exception as exc:
                result['cover_error']=str(exc)
                record_send(source,device,result)
                raise ConversionError('书籍已发送，但封面同步失败：'+str(exc)) from exc
        record_send(source,device,result)
        return str(target)
    except BaseException:
        if partial.exists():
            partial.unlink()
        if target.exists() and target.stat().st_size==0:
            target.unlink()
        raise


def digest(path):
    value=hashlib.sha256()
    with open(path,'rb') as stream:
        for block in iter(lambda:stream.read(1024**2),b''):
            value.update(block)
    return value.hexdigest()

def validate_file(path):
    path=Path(path)
    if path.suffix.lower() not in USB_FORMATS:
        raise ConversionError('Kindle 有线传输不接受 EPUB/HTML/FB2，请先转为 AZW3/KFX/MOBI；无线 Send to Kindle 请上传 EPUB。')
    with path.open('rb') as f: magic=f.read(80)
    ext=path.suffix.lower()
    if ext in ('.azw3','.mobi','.azw'):
        from .kindle_formats import mobi_version
        version=mobi_version(path)
        if ext=='.azw3' and version!=8:
            raise ConversionError('此文件不是 KF8 / AZW3，不能仅修改扩展名发送。')
    if ext=='.kfx' and magic[:4]!=b'CONT':
        raise ConversionError('请选择完整的单文件 KFX 容器，不能直接发送 KFX-ZIP 或资源分片。')
    if ext=='.pdf' and not magic.startswith(b'%PDF'):
        raise ConversionError('文件不是有效 PDF。')

def record_send(source,device,result):
    from .storage import load_json,save_json
    entries=load_json('transfers.json',[])
    entries.insert(0,{'time':datetime.now().isoformat(timespec='seconds'),
                     'source':str(source),'device':device.name,**result})
    save_json('transfers.json',entries[:200])
