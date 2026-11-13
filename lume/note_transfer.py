"""Discover note apps and prepare their native import formats without plugins."""
from dataclasses import dataclass,field
from datetime import datetime
from pathlib import Path
import json
import os
import re
import uuid
import zipfile
from . import clippings as notes
from .model import ConversionError


@dataclass
class NoteTarget:
    id:str
    name:str
    kind:str
    executable:str=''
    detected:bool=False
    libraries:list=field(default_factory=list)
    associated:bool=False


APPS=(('obsidian','Obsidian','vault',('obsidian',),('Obsidian.exe',)),
      ('joplin','Joplin','joplin',('joplin',),('Joplin.exe',)),
      ('yinxiang','印象笔记','enex',('印象笔记','yinxiang'),('Yinxiang.exe','Evernote.exe')),
      ('evernote','Evernote','enex',('evernote',),('Evernote.exe',)),
      ('logseq','Logseq 文件图谱','vault',('logseq',),('Logseq.exe',)),
      ('notion','Notion','zip',('notion',),('Notion.exe',)))


def _exe(value):
    value=os.path.expandvars(str(value or '')).strip()
    match=re.match(r'^"([^"]+\.exe)"|^(.+?\.exe)(?:,|\s|$)',value,re.I)
    candidate=(match[1] or match[2]) if match else value
    path=Path(candidate)
    return str(path.resolve()) if path.suffix.casefold()=='.exe' and path.is_file() else ''


def _registry_apps():
    if os.name!='nt':return [],''
    import winreg
    found=[];association=''
    for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
        for view in (winreg.KEY_WOW64_64KEY,winreg.KEY_WOW64_32KEY):
            try:
                with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\Uninstall',0,winreg.KEY_READ|view) as root:
                    for i in range(min(winreg.QueryInfoKey(root)[0],5000)):
                        try:
                            with winreg.OpenKey(root,winreg.EnumKey(root,i)) as item:
                                def get(key):
                                    try:return winreg.QueryValueEx(item,key)[0]
                                    except OSError:return ''
                                name=get('DisplayName')
                                if any(token in str(name).casefold() for _,_,_,tokens,_ in APPS for token in tokens):
                                    found.append((str(name),str(get('InstallLocation')),_exe(get('DisplayIcon'))))
                        except OSError:continue
            except OSError:pass
        for _,name,_,_,exes in APPS:
            for executable in exes:
                try:
                    with winreg.OpenKey(hive,'Software\\Microsoft\\Windows\\CurrentVersion\\App Paths\\'+executable) as key:
                        path=_exe(winreg.QueryValueEx(key,'')[0])
                        if path:
                            detected_name=name
                            if executable.casefold()=='evernote.exe':
                                detected_name='印象笔记' if '印象' in path or 'yinxiang' in path.casefold() else 'Evernote'
                            found.append((detected_name,'',path))
                except OSError:pass
    try:
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER,r'Software\Microsoft\Windows\CurrentVersion\Explorer\FileExts\.enex\UserChoice') as key:
                progid=winreg.QueryValueEx(key,'ProgId')[0]
        except OSError:
            with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,'.enex') as key:progid=winreg.QueryValueEx(key,'')[0]
        with winreg.OpenKey(winreg.HKEY_CLASSES_ROOT,str(progid)+r'\shell\open\command') as key:
            association=_exe(winreg.QueryValueEx(key,'')[0])
    except OSError:pass
    return found,association


def obsidian_libraries(roaming=None):
    roaming=Path(roaming or os.environ.get('APPDATA',Path.home()/'AppData/Roaming'))
    try:
        data=json.loads((roaming/'obsidian/obsidian.json').read_text(encoding='utf-8'))
        result=[]
        for value in data.get('vaults',{}).values():
            path=Path(value.get('path',''))
            if path.is_dir() and (path/'.obsidian').is_dir():result.append(str(path.resolve()))
        return list(dict.fromkeys(result))
    except (OSError,ValueError,AttributeError,TypeError):return []


def discover_targets():
    installed,association=_registry_apps()
    local=Path(os.environ.get('LOCALAPPDATA',Path.home()/'AppData/Local'))
    program_roots=[local,local/'Programs',Path(os.environ.get('ProgramFiles','C:/Program Files')),
                   Path(os.environ.get('ProgramFiles(x86)','C:/Program Files (x86)'))]
    result=[]
    for key,name,kind,tokens,exes in APPS:
        executable='';detected=False
        for title,folder,icon in installed:
            if not any(token in title.casefold() for token in tokens):continue
            detected=True
            if icon:executable=icon;break
            for exe in exes:
                candidate=Path(folder)/exe
                if candidate.is_file():executable=str(candidate);break
            if executable:break
        if not executable:
            for base in program_roots:
                candidates=[base/name,base/key,base/name/name,base/'印象笔记'/'印象笔记']
                for directory in candidates:
                    for exe in exes:
                        candidate=directory/exe
                        if candidate.is_file():executable=str(candidate);detected=True;break
                    if executable:break
                if executable:break
        libraries=obsidian_libraries() if key=='obsidian' else []
        if key=='evernote' and executable and any(t.id=='yinxiang' and os.path.normcase(t.executable)==os.path.normcase(executable) for t in result):continue
        if detected or libraries or key in ('obsidian','logseq'):
            result.append(NoteTarget(key,name,kind,executable,detected or bool(libraries),libraries,
                                     bool(association and executable and os.path.normcase(executable)==os.path.normcase(association))))
    result.sort(key=lambda t:not t.detected)
    result.append(NoteTarget('markdown','其他软件 / Markdown 文件夹','folder'))
    return result


def safe_title(value):
    value=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',value).strip(' .')[:90]
    if not value or re.match(r'^(CON|PRN|AUX|NUL|COM\d|LPT\d)(\.|$)',value,re.I):value='书籍_'+value
    return value


def _unique_file(folder,name,suffix):
    from .util import reserve_output
    return reserve_output(folder,name,suffix)


def _write_books(records,folder,progress,cancel,logseq=False):
    folder=Path(folder);folder.mkdir(parents=True,exist_ok=True)
    if folder.is_symlink():raise ConversionError('笔记输出目录不能是链接。')
    paths=[];books=notes.groups(records)
    for index,book in enumerate(books):
        if cancel.is_set():raise ConversionError(f'已取消；此前写入的 {len(paths)} 本书会保留。')
        progress(f'写入 {index+1} / {len(books)} · {book[0].title}')
        name=safe_title(book[0].title)
        if logseq:name+=' — Kindle '+datetime.now().strftime('%Y%m%d-%H%M%S')
        target=_unique_file(folder,name,'md')
        try:notes.export_markdown(book,target)
        except Exception as exc:
            if target.exists() and target.stat().st_size==0:target.unlink()
            raise ConversionError(f'导入未全部完成；已保留 {len(paths)} 本。'+str(exc)) from exc
        paths.append(target)
    return paths


def transfer(records,target,destination,staging,progress,cancel):
    """Return an honest receipt: written, or delegated to the receiving app."""
    if not records:raise ConversionError('没有可导入的摘抄。')
    if target.kind=='joplin':
        from .note_joplin import import_joplin
        return import_joplin(records,progress,cancel)
    stamp=datetime.now().strftime('%Y%m%d-%H%M%S')+'-'+uuid.uuid4().hex[:6]
    if target.kind in ('vault','folder'):
        root=Path(destination).expanduser().resolve(strict=True)
        if not root.is_dir():raise ConversionError('请选择有效的笔记库目录。')
        if target.id=='obsidian' and not (root/'.obsidian').is_dir():
            raise ConversionError('这里不是现有 Obsidian 笔记库，请选择含 .obsidian 的库目录。')
        if target.id=='logseq' and not (root/'logseq').is_dir():
            raise ConversionError('请选择 Logseq 文件图谱目录（含 logseq 文件夹）。数据库图谱请使用文件导入。')
        folder=root/'pages' if target.id=='logseq' else root/'Kindle 摘抄'/stamp
        if root not in folder.resolve().parents:
            raise ConversionError('笔记输出目录指向了所选笔记库之外。')
        paths=_write_books(records,folder,progress,cancel,target.id=='logseq')
        message=f'已导入 {len(paths)} 本书、{len(records)} 条摘抄到 '+target.name
        actions=[('obsidian',str(paths[0]))] if target.id=='obsidian' and target.detected else [('folder',str(folder))]
        return {'message':message,'state':'written','paths':[str(p) for p in paths],'actions':actions}
    folder=Path(staging)/stamp;folder.mkdir(parents=True,exist_ok=False)
    if target.kind=='enex':
        path=notes.export_enex(records,folder/'Kindle 摘抄.enex')
        if target.associated:
            actions=[('file',str(path))]
            message='已转换为 ENEX，将交给 '+target.name+' 导入；结果以目标软件显示为准。'
        else:
            actions=([('app',target.executable)] if target.executable else [])+[('folder',str(folder))]
            message='已生成 ENEX。请在 '+target.name+' 的“文件 → 导入”中选择该文件。'
    elif target.kind=='zip':
        paths=_write_books(records,folder/'Markdown',progress,cancel)
        path=folder/'Kindle 摘抄.zip'
        with zipfile.ZipFile(path,'w',zipfile.ZIP_DEFLATED) as archive:
            for item in paths:archive.write(item,item.name)
        actions=([('app',target.executable)] if target.executable else [])+[('folder',str(folder))]
        message='已生成 Markdown ZIP。请在 '+target.name+' 的“导入”中选择该文件。'
    else:raise ConversionError('此软件暂无适配的导入方式。')
    return {'message':message,'state':'handoff','paths':[str(path)],'actions':actions}