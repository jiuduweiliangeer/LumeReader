"""Kindle MTP transport through Windows Portable Devices, without Explorer automation.

Uses Microsoft PortableDeviceApiLib / PortableDeviceTypesLib and comtypes.
Each session owns its COM objects in the calling thread.
"""
from __future__ import annotations
import ctypes
import hashlib
import io
import os
from pathlib import Path
import threading
from .model import ConversionError

_INIT_LOCK=threading.Lock()

class Session:
    def __enter__(self):
        import comtypes
        import comtypes.client
        self.com=comtypes
        comtypes.CoInitialize()
        with _INIT_LOCK:
            comtypes.client.GetModule('portabledeviceapi.dll')
            comtypes.client.GetModule('portabledevicetypes.dll')
        from comtypes.gen import PortableDeviceApiLib as port
        from comtypes.gen import PortableDeviceTypesLib as types
        self.port,self.types=port,types
        self.manager=self.create(port.PortableDeviceManager,port.IPortableDeviceManager)
        self.devices=[]
        return self

    def create(self,kind,interface):
        return self.com.client.CreateObject(kind,clsctx=self.com.CLSCTX_INPROC_SERVER,interface=interface)

    def key(self,number,group='{EF6B490D-5CD8-437A-AFFC-DA8B60EE4A3C}'):
        result=self.port._tagpropertykey()
        result.fmtid=self.com.GUID(group)
        result.pid=number
        return result

    def values(self):
        return self.create(self.types.PortableDeviceValues,self.port.IPortableDeviceValues)

    def kindle_ids(self):
        count=ctypes.pointer(ctypes.c_ulong())
        self.manager.GetDevices(ctypes.POINTER(ctypes.c_wchar_p)(),count)
        if not count.contents.value: return []
        ids=(ctypes.c_wchar_p*count.contents.value)()
        self.manager.GetDevices(ids,count)
        return [value for value in ids if value and 'vid_1949' in value.lower()]

    def open(self,device_id):
        if device_id not in self.kindle_ids():
            raise ConversionError('Kindle 已断开，请重新连接并刷新设备。')
        dev=self.create(self.port.PortableDevice,self.port.IPortableDevice)
        client=self.values()
        dev.Open(device_id,client)
        self.devices.append(dev)
        return dev.Content()

    def item(self,content,object_id):
        props=content.Properties().GetValues(object_id,None)
        def string(n,default=''):
            try: return str(props.GetStringValue(self.key(n)))
            except self.com.COMError: return default
        def integer(n,default=0):
            try: return int(props.GetUnsignedLargeIntegerValue(self.key(n)))
            except self.com.COMError: return default
        try:
            content_type=str(props.GetGuidValue(self.key(7))).upper()
        except self.com.COMError:
            content_type=''
        return {'id':object_id,'name':string(12) or string(4),'size':integer(11),
                'parent':string(3),'is_folder':content_type=='{27E2E392-A111-48E0-AB0C-E17705A05F85}'}

    def children(self,content,parent='DEVICE'):
        enum=content.EnumObjects(0,parent,None)
        while True:
            count=ctypes.pointer(ctypes.c_ulong())
            values=enum.Next(1,count)
            if not count.contents.value: break
            yield self.item(content,str(values[0]))

    def documents(self,content,storage_id=None):
        for storage in self.children(content):
            if storage_id is not None and storage['id']!=storage_id: continue
            for item in self.children(content,storage['id']):
                if item['name'].lower()=='documents':
                    return storage,item
        raise ConversionError('Kindle 未提供 documents 目录，请解锁设备后重试。')

    def __exit__(self,*args):
        for dev in self.devices:
            try: dev.Close()
            except Exception: pass
        self.devices.clear()
        self.manager=None
        self.com.CoUninitialize()

def scan():
    if os.name!='nt': return []
    result=[]
    with Session() as session:
        for device_id in session.kindle_ids():
            content=session.open(device_id)
            root=session.item(content,'DEVICE')
            storage,folder=session.documents(content)
            result.append({'name':root['name'] or 'Kindle','id':device_id,
                           'storage':storage['id'],'folder':folder['id']})
    return result

def upload(source,device_id,storage_id,progress=None):
    """Create a new object, commit, then read it back and compare SHA-256."""
    source=Path(source)
    progress=progress or (lambda message:None)
    size=source.stat().st_size
    with Session() as session:
        content=session.open(device_id)
        storage,folder=session.documents(content,storage_id)
        try:
            props=content.Properties().GetValues(storage['id'],None)
            free=props.GetUnsignedLargeIntegerValue(session.key(5,'{01A3057A-74D6-4E80-BEA7-DC4C212CE50A}'))
            if free<size+1024**2:
                raise ConversionError('Kindle 存储空间不足。')
        except session.com.COMError:
            pass
        names={x['name'].casefold() for x in session.children(content,folder['id'])}
        name=source.name
        for i in range(1,10000):
            if name.casefold() not in names: break
            name=f'{source.stem} ({i}){source.suffix}'
        else:
            raise ConversionError('设备上同名文件过多。')
        props=session.values()
        props.SetStringValue(session.key(3),folder['id'])
        props.SetStringValue(session.key(4),name)
        props.SetStringValue(session.key(12),name)
        props.SetUnsignedLargeIntegerValue(session.key(11),size)
        optimal=ctypes.pointer(ctypes.c_ulong())
        stream,_,_=content.CreateObjectWithPropertiesAndData(props,optimal,ctypes.POINTER(ctypes.c_wchar_p)())
        blocksize=max(4096,min(optimal.contents.value or 65536,1024**2))
        expected=hashlib.sha256()
        copied=0
        try:
            with source.open('rb') as src:
                while True:
                    block=src.read(blocksize)
                    if not block: break
                    buf=(ctypes.c_ubyte*len(block)).from_buffer_copy(block)
                    count=stream.RemoteWrite(buf,len(block))
                    if count!=len(block):
                        raise ConversionError('MTP 未完整写入数据，请重新连接后重试。')
                    copied+=count
                    expected.update(block)
                    progress(f'MTP 写入 · {copied/max(size,1):.0%}')
            stream.Commit(0)
        except BaseException:
            try: stream.Revert()
            except Exception: pass
            raise
        finally:
            stream=None
        stored=next((x for x in session.children(content,folder['id']) if x['name']==name),None)
        if not stored or stored['size']!=size:
            raise ConversionError('设备写入后大小不符，未标记发送成功。')
        progress('从 Kindle 回读校验 SHA-256…')
        optimal=ctypes.pointer(ctypes.c_ulong())
        _,reader=content.Transfer().GetStream(stored['id'],
                    session.key(0,'{E81E79BE-34F0-41BF-B53F-F1A06AE87842}'),0,optimal)
        actual=hashlib.sha256()
        total=0
        try:
            while True:
                block,count=reader.RemoteRead(max(4096,min(optimal.contents.value or 65536,1024**2)))
                if not count: break
                actual.update(bytes(block[:count]))
                total+=count
        finally:
            reader=None
        if total!=size or actual.digest()!=expected.digest():
            raise ConversionError('Kindle 回读校验不一致，未标记发送成功。')
        return {'path':'documents/'+name,'size':size,'sha256':actual.hexdigest(),
                'transport':'Windows WPD / MTP','verified':True}


def upload_thumbnail(device_id,storage_id,name,data):
    """Write only the selected book's Kindle library thumbnail and verify it."""
    import re
    if not re.fullmatch(r'thumbnail_[A-Za-z0-9_-]{8,64}_(PDOC|EBOK)_portrait\.jpg',name):
        raise ConversionError('无效的 Kindle 封面标识。')
    with Session() as session:
        content=session.open(device_id)
        storage=next((x for x in session.children(content) if x['id']==storage_id),None)
        if not storage: raise ConversionError('Kindle 存储已断开。')
        parent=storage['id']
        for part in ('system','thumbnails'):
            found=next((x for x in session.children(content,parent) if x['name'].casefold()==part),None)
            if not found:
                props=session.values()
                props.SetStringValue(session.key(3),parent)
                props.SetStringValue(session.key(4),part)
                props.SetStringValue(session.key(12),part)
                props.SetGuidValue(session.key(7),session.com.GUID('{27E2E392-A111-48E0-AB0C-E17705A05F85}'))
                content.CreateObjectWithPropertiesOnly(props,ctypes.POINTER(ctypes.c_wchar_p)())
                found=next((x for x in session.children(content,parent) if x['name'].casefold()==part),None)
            if not found: raise ConversionError('无法访问 Kindle 封面缩略图目录。')
            parent=found['id']
        existing=next((x for x in session.children(content,parent) if x['name']==name),None)
        expected=hashlib.sha256(data).hexdigest()
        def read_hash(item):
            optimal=ctypes.pointer(ctypes.c_ulong())
            _,reader=content.Transfer().GetStream(item['id'],
                session.key(0,'{E81E79BE-34F0-41BF-B53F-F1A06AE87842}'),0,optimal)
            value=hashlib.sha256()
            while True:
                block,count=reader.RemoteRead(65536)
                if not count: break
                value.update(bytes(block[:count]))
            return value.hexdigest()
        if existing and read_hash(existing)==expected:
            return {'path':'system/thumbnails/'+name,'sha256':expected,'verified':True}
        props=session.values()
        props.SetStringValue(session.key(3),parent)
        props.SetStringValue(session.key(4),name)
        props.SetStringValue(session.key(12),name)
        props.SetUnsignedLargeIntegerValue(session.key(11),len(data))
        optimal=ctypes.pointer(ctypes.c_ulong())
        if existing:
            writer,_=content.QueryInterface(session.port.IPortableDeviceContent2).UpdateObjectWithPropertiesAndData(
                existing['id'],props,optimal)
        else:
            writer,_,_=content.CreateObjectWithPropertiesAndData(props,optimal,ctypes.POINTER(ctypes.c_wchar_p)())
        try:
            for start in range(0,len(data),65536):
                block=data[start:start+65536]
                buf=(ctypes.c_ubyte*len(block)).from_buffer_copy(block)
                if writer.RemoteWrite(buf,len(block))!=len(block):
                    raise ConversionError('封面缩略图未完整写入。')
            writer.Commit(0)
        except BaseException:
            try: writer.Revert()
            except Exception: pass
            raise
        finally:
            writer=None
        stored=next((x for x in session.children(content,parent) if x['name']==name),None)
        if not stored or read_hash(stored)!=expected:
            raise ConversionError('Kindle 封面缩略图回读校验失败。')
        return {'path':'system/thumbnails/'+name,'sha256':expected,'verified':True}
