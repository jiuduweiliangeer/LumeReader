"""Read Kindle clippings without changing the device; export portable notes."""
from dataclasses import asdict,dataclass
from datetime import datetime,timezone
from hashlib import sha256
from html import escape
from pathlib import Path
import json
import re
import uuid
from lxml import etree
from .model import ConversionError

KINDS={'highlight':'划线','note':'笔记','bookmark':'书签'}
MAX_BYTES=128*1024*1024


def clean(value):
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ud800-\udfff\ufffe\uffff]','',value)


@dataclass(frozen=True)
class Clipping:
    title:str
    author:str
    kind:str
    text:str
    location:str=''
    page:str=''
    added:str=''

    @property
    def book_id(self):
        return sha256((self.title+'\n'+self.author).encode('utf-8')).hexdigest()[:24]

    @property
    def id(self):
        value='\n'.join((self.title,self.author,self.kind,self.location,self.page,self.text))
        return sha256(value.encode('utf-8')).hexdigest()


def decode(data):
    if len(data)>MAX_BYTES:raise ConversionError('摘抄文件超过 128 MB，请先按年份拆分后导入。')
    if data.startswith((b'\xff\xfe',b'\xfe\xff')):return data.decode('utf-16')
    if b'\x00' in data[:200]:
        try:return data.decode('utf-16-le')
        except UnicodeError:pass
    for encoding in ('utf-8-sig','gb18030'):
        try:return data.decode(encoding)
        except UnicodeError:pass
    raise ConversionError('无法识别摘抄文件编码，请另存为 UTF-8 文本后导入。')


def split_title(value):
    value=value.strip().lstrip('\ufeff')
    # The last balanced pair is Kindle's author field; preserve parentheses in titles.
    pairs={')':'(', '）':'（'}
    if value and value[-1] in pairs:
        opening=pairs[value[-1]];closing=value[-1];depth=0
        for i in range(len(value)-1,-1,-1):
            if value[i]==closing:depth+=1
            elif value[i]==opening:depth-=1
            if depth==0:
                if i>0:return value[:i].strip(),value[i+1:-1].strip()
                break
    return value,''


def parse_clippings(data):
    text=decode(data) if isinstance(data,bytes) else data
    records=[];skipped=0
    for block in re.split(r'^\s*={10,}\s*$',text.replace('\r\n','\n').replace('\r','\n'),flags=re.M):
        lines=block.strip().splitlines()
        if not lines:continue
        if len(lines)<2 or not lines[1].lstrip().startswith(('-', '–')):
            skipped+=1;continue
        title,author=split_title(clean(lines[0]))
        metadata=clean(lines[1]);lower=metadata.casefold()
        if re.search(r'highlight|标注|劃線|划线|畫線|突出显示',lower):kind='highlight'
        elif re.search(r'\bnote\b|笔记|筆記|注释|註記',lower):kind='note'
        elif re.search(r'bookmark|书签|書籤',lower):kind='bookmark'
        else:skipped+=1;continue
        body=clean('\n'.join(lines[2:]).strip())
        if not title or (not body and kind!='bookmark'):skipped+=1;continue
        location=re.search(r'(?:location|loc\.?|位置)\s*[:：#]?\s*([\d,]+(?:\s*[-–]\s*[\d,]+)?)',metadata,re.I)
        page=re.search(r'(?:page|第)\s*([\d,]+(?:\s*[-–]\s*[\d,]+)?)\s*(?:页|頁)?',metadata,re.I)
        added=re.search(r'(?:Added on|添加于|添加於|新增於|已添加至)\s*(.+)',metadata,re.I)
        records.append(Clipping(title,author,kind,body,location[1] if location else '',page[1] if page else '',added[1].strip() if added else ''))
    return records,skipped


def merge_clippings(existing,incoming):
    merged=list(existing);seen={c.id for c in merged};duplicates=0
    for item in incoming:
        if item.id in seen:duplicates+=1
        else:merged.append(item);seen.add(item.id)
    return merged,duplicates


def load_library():
    from .storage import load_json
    result=[]
    for value in load_json('clippings.json',[]):
        try:result.append(Clipping(**value))
        except (TypeError,ValueError):continue
    return result


def save_library(records):
    from .storage import save_json
    save_json('clippings.json',[asdict(c) for c in records])


def read_file(path):
    with Path(path).open('rb') as source:
        data=source.read(MAX_BYTES+1)
    if len(data)>MAX_BYTES:raise ConversionError('摘抄文件超过 128 MB，请拆分后导入。')
    return data


def read_device(device):
    if device.kind=='usb':
        root=Path(device.path).resolve(strict=True)
        path=next((p for p in root.iterdir() if p.name.casefold()=='my clippings.txt'),None)
        if not path or not path.is_file():raise ConversionError('Kindle documents 中没有 My Clippings.txt。请先在设备上划线或记录笔记。')
        if path.is_symlink() or path.resolve().parent!=root:raise ConversionError('摘抄文件不能是指向其他位置的链接。')
        return read_file(path)
    if device.kind=='mtp':
        from .wpd import Session
        from .device_library import _mtp_chunks
        info=json.loads(device.path)
        with Session() as session:
            content=session.open(info['id'])
            _,folder=session.documents(content,info['storage'])
            item=next((i for i in session.children(content,folder['id'])
                       if i['name'].casefold()=='my clippings.txt' and not i.get('is_folder')),None)
            if not item:raise ConversionError('设备中没有 My Clippings.txt。')
            chunks=[];size=0
            for chunk in _mtp_chunks(session,content,item):
                size+=len(chunk)
                if size>MAX_BYTES:raise ConversionError('摘抄文件超过 128 MB，请拆分后导入。')
                chunks.append(chunk)
            return b''.join(chunks)
    raise ConversionError('不支持的设备连接方式。')


def groups(records):
    result={}
    for item in records:result.setdefault(item.book_id,[]).append(item)
    return list(result.values())


def metadata(c):
    return ' · '.join(filter(None,(KINDS.get(c.kind,c.kind),'第 '+c.page+' 页' if c.page else '',
                                    '位置 '+c.location if c.location else '',c.added)))


def notes_html(records,styled=False):
    content=[]
    for c in records:
        body=escape(c.text or '书签').replace('\n','<br/>')
        meta=escape(metadata(c))
        if styled:
            # Qt rich text supports table cell padding, but ignores div padding.
            content.append('<table width="98%" cellspacing="0" cellpadding="16" bgcolor="#f1f7f3">'
                           '<tr><td style="border-left:3px solid #75a087;">'
                           '<p style="margin-top:0;margin-bottom:12px;line-height:150%;">'+body+'</p>'
                           '<p style="color:#61796b;font-size:10pt;margin:0;">'+meta+'</p>'
                           '</td></tr></table><p style="font-size:6pt;margin:0;"><br/></p>')
        else:
            content.append('<div><div>'+body+'</div><div style="color:#66796e;font-size:10pt;">'+meta+'</div><br/></div>')
    return ''.join(content)


def atomic_export(path,data):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_name('.'+path.name+'.'+uuid.uuid4().hex+'.tmp')
    try:
        temp.write_bytes(data)
        temp.replace(path)
    finally:temp.unlink(missing_ok=True)
    return path


def markdown_text(records):
    blocks=[]
    for book in groups(records):
        first=book[0]
        blocks.append('# '+first.title+'\n\n'+(('作者：'+first.author+'\n\n') if first.author else ''))
        for c in book:
            blocks.append('\n'.join('> '+line for line in (c.text or '书签').splitlines()))
            blocks.append('\n\n'+metadata(c)+'\n\n---\n\n')
    return ''.join(blocks)


def export_markdown(records,path):
    return atomic_export(path,markdown_text(records).encode('utf-8'))


def export_enex(records,path):
    now=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    root=etree.Element('en-export',{'export-date':now,'application':'LumeReader','version':'1.1.0'})
    for book in groups(records):
        first=book[0];note=etree.SubElement(root,'note')
        etree.SubElement(note,'title').text=clean(first.title)
        author='<div>作者：'+escape(first.author)+'</div>' if first.author else ''
        content='<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE en-note SYSTEM "http://xml.evernote.com/pub/enml2.dtd"><en-note>'+author+notes_html(book)+'</en-note>'
        etree.SubElement(note,'content').text=etree.CDATA(content)
        etree.SubElement(note,'created').text=now
        etree.SubElement(note,'updated').text=now
        etree.SubElement(note,'tag').text='Kindle'
    data=etree.tostring(root,encoding='utf-8',xml_declaration=True,pretty_print=True,
                        doctype='<!DOCTYPE en-export SYSTEM "http://xml.evernote.com/pub/evernote-export3.dtd">')
    return atomic_export(path,data)