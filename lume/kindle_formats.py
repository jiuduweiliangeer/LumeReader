from __future__ import annotations
import io
import hashlib
import os
from pathlib import Path
import shutil
import struct
import subprocess
import time
from .model import ConversionError
from .typography import declarations, css_for_chapter, matcher_for, computed_style, stylesheet
from .util import body_root, resolve_href
from .writers import write_epub

def find_kindlegen(configured=''):
    if configured:
        return str(Path(configured)) if Path(configured).is_file() else ''
    from .paths import EXE_ROOT,USER_ROOT
    paths = [os.environ.get('KINDLEGEN',''),shutil.which('kindlegen') or '',
             str(EXE_ROOT/'tools'/'kindlegen.exe'),str(USER_ROOT/'tools'/'kindlegen.exe')]
    if os.name=='nt':
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER,winreg.HKEY_LOCAL_MACHINE):
            for view in (winreg.KEY_WOW64_32KEY,winreg.KEY_WOW64_64KEY):
                try:
                    with winreg.OpenKey(hive,r'Software\Microsoft\Windows\CurrentVersion\Uninstall',0,winreg.KEY_READ|view) as parent:
                        for index in range(winreg.QueryInfoKey(parent)[0]):
                            try:
                                with winreg.OpenKey(parent,winreg.EnumKey(parent,index)) as key:
                                    name=winreg.QueryValueEx(key,'DisplayName')[0]
                                    if 'kindle previewer' not in name.lower(): continue
                                    for field in ('InstallLocation','DisplayIcon','UninstallString'):
                                        try:
                                            value=str(winreg.QueryValueEx(key,field)[0]).strip().strip('"')
                                            value=value.split(',')[0].strip('"')
                                            location=Path(value)
                                            if location.suffix.lower()=='.exe': location=location.parent
                                            paths.append(str(location/'lib'/'fc'/'bin'/'kindlegen.exe'))
                                        except OSError: pass
                            except OSError: pass
                except OSError: pass
    for base in (os.environ.get('LOCALAPPDATA',''),os.environ.get('ProgramFiles',''),
                 os.environ.get('ProgramFiles(x86)','')):
        for name in ('Kindle Previewer 3','Kindle Previewer 4'):
            paths.extend([str(Path(base)/'Amazon'/name/'lib/fc/bin/kindlegen.exe'),
                          str(Path(base)/name/'lib/fc/bin/kindlegen.exe')])
    return next((p for p in paths if p and Path(p).is_file()),'')

def mobi_version(path):
    with open(path,'rb') as f:
        header=f.read(86)
        if len(header)<86 or header[60:68] != b'BOOKMOBI':
            raise ConversionError('输出不是有效的 MOBI/PalmDB 文件。')
        offset=struct.unpack_from('>I',header,78)[0]
        f.seek(offset)
        record=f.read(40)
        if len(record)<40 or record[16:20] != b'MOBI':
            raise ConversionError('MOBI 头部不完整。')
        if struct.unpack_from('>H',record,12)[0]:
            raise ConversionError('此 Kindle 文件已加密，无法直接转换。')
        return struct.unpack_from('>I',record,36)[0]

def compile_kindle(book,path,layout,ctx,workdir,kindlegen=''):
    tool=find_kindlegen(kindlegen)
    if not tool:
        raise ConversionError('MOBI/AZW3 输出需要独立的 KindleGen 官方编译器。请在设置中选择 kindlegen.exe；不需要 Calibre。EPUB、KFX、PDF 可直接生成。')
    from .reflow import unlock_font_sizes
    unlock_font_sizes(book)
    epub=Path(workdir)/'source.epub'
    write_epub(book,epub,layout,ctx)
    ctx.update(62,'生成 Kindle 文件')
    logfile=Path(workdir)/'kindlegen.log'
    with open(logfile,'wb') as log:
        # A compiler crash must become a job error, never a blocking Windows dialog.
        if os.name=='nt':
            import ctypes
            old_error_mode=ctypes.windll.kernel32.SetErrorMode(0x0001|0x0002|0x8000)
        process=subprocess.Popen([tool,str(epub),'-c1','-dont_append_source','-o','compiled.mobi'],
                                  stdout=log,stderr=subprocess.STDOUT,cwd=str(workdir),
                                  creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if os.name=='nt': ctypes.windll.kernel32.SetErrorMode(old_error_mode)
        try:
            started=time.monotonic()
            while process.poll() is None:
                ctx.check()
                if time.monotonic()-started>1200:
                    raise ConversionError('KindleGen 编译超过 20 分钟，已中止。')
                time.sleep(.1)
        except BaseException:
            process.kill()
            process.wait()
            raise
    compiled=Path(workdir)/'compiled.mobi'
    if process.returncode not in (0,1) or not compiled.is_file():
        text=logfile.read_text(encoding='utf-8',errors='replace')
        raise ConversionError('KindleGen 编译失败：\n'+text[-2400:])
    mobi_version(compiled)
    set_pdb_identity(compiled,book,layout)
    if Path(path).suffix.lower()=='.azw3':
        from kindleunpack.mobi_split import mobi_split
        split=mobi_split(str(compiled))
        if not split.combo:
            raise ConversionError('编译器没有生成 KF8 数据，无法导出真正的 AZW3。')
        Path(path).write_bytes(split.getResult8())
        if mobi_version(path)!=8:
            raise ConversionError('AZW3 格式验证失败。')
    else:
        shutil.copyfile(compiled,path)
        book.warnings.append('MOBI 为 MOBI7 + KF8 双格式；旧设备的 MOBI7 部分不支持嵌入字体，KPW6 建议使用 AZW3/KFX。')

def decode_kindle(path,workdir,ctx):
    import tempfile
    # Repeated reads sharing a work directory must never pick up another book.
    Path(workdir).mkdir(parents=True,exist_ok=True)
    workdir=Path(tempfile.mkdtemp(prefix='decode-',dir=workdir))
    ctx.update(6,'读取 Kindle 格式')
    if path.suffix.lower() in ('.kfx','.kfx-zip','.kpf'):
        from kfxlib.yj_book import YJ_Book
        try:
            data=YJ_Book(str(path)).convert_to_epub()
        except Exception as exc:
            raise ConversionError('KFX 读取失败。仅支持未加密且资源完整的 KFX/KFX-ZIP/KPF。\n'+str(exc)[:600]) from exc
        output=workdir/'decoded.epub'
        output.write_bytes(data)
        return output
    mobi_version(path)
    from kindleunpack.kindleunpack import unpackBook
    folder=workdir/'unpacked'
    try:
        unpackBook(str(path),str(folder),epubver='3')
    except Exception as exc:
        raise ConversionError('MOBI/AZW3 解析失败：'+str(exc)) from exc
    epubs=list(folder.rglob('*.epub'))
    if epubs:
        return epubs[0]
    # Legacy MOBI7 resources are read by the HTML importer.
    html_files=list(folder.rglob('*.html'))+list(folder.rglob('*.htm'))
    if html_files:
        return max(html_files,key=lambda f:f.stat().st_size)
    raise ConversionError('Kindle 文件没有可读取的正文。')

def write_kfx(book,path,layout,ctx):
    import cssselect2
    from kfxgen.native_generator import NativeKFXGenerator
    from kfxgen.converter import extract_blocks_from_html
    from kfxgen.font_table import Face, FontTable
    chapters=[]
    for index,ch in enumerate(book.chapters):
        if index%10==0:
            ctx.update(55+20*index/max(len(book.chapters),1),f'构建 KFX · {index+1}/{len(book.chapters)} 章')
        root=body_root(ch.body)
        root.tag='body'
        matcher=matcher_for(KFX_HEADING_CSS+'\n'+css_for_chapter(book,ch))
        styles={}
        for wrap in cssselect2.ElementWrapper.from_html_root(root).iter_subtree():
            parent=styles.get(wrap.etree_element.getparent(),{
                'font-size':layout.font_size,'line-height':str(layout.line_height),
                'font-family':'LumeEmbedded' if book.embedded_font else 'serif'})
            inherited={k:v for k,v in parent.items() if k in ('font-family','font-size','font-weight','font-style','line-height','text-align','text-indent')}
            computed=computed_style(wrap,matcher,inherited)
            # The independent KFX extractor expects numeric CSS pixels.
            # CSS strings are treated as an absent size, collapsing headings.
            computed['font-size']=kfx_font_pixels(computed.get('font-size'),parent['font-size'],layout.font_size)
            styles[wrap.etree_element]=computed
        blocks=extract_blocks_from_html(root,style_resolver=lambda el:styles.get(el,{}),
                                       base_href=ch.href,native_tables=True,keep_nav_listings=True)
        if not blocks:
            continue
        # Keep source hierarchy and in-document anchors in the Kindle navigation tree.
        entries=[e for e in book.toc if e.href.split('#')[0]==ch.href]
        starts={0:(ch.title,1)}
        for entry in entries:
            if '#' not in entry.href:
                starts[0]=(entry.title,entry.level)
                continue
            target=entry.href
            found=next((i for i,b in enumerate(blocks) if target in (b.get('anchor_keys') or [])),None)
            if found is not None:
                starts[found]=(entry.title,entry.level)
        indices=sorted(starts)
        for j,start in enumerate(indices):
            end=indices[j+1] if j+1<len(indices) else len(blocks)
            selected=blocks[start:end]
            title,level=starts[start]
            chapters.append({'title':title,'text':'\n\n'.join(b.get('text','') for b in selected),
                             'blocks':selected,'toc_level':max(0,level-1),
                             'anchor_keys':[ch.href] if start==0 else [],'_omit_title_heading':True})
    if not chapters:
        raise ConversionError('KFX 没有可生成的正文。')
    images={}
    from PIL import Image
    for r in book.resources.values():
        if r.media_type.startswith('image/') and r.media_type!='image/svg+xml':
            try:
                im=Image.open(io.BytesIO(r.data))
                if im.format not in ('PNG','JPEG'):
                    out=io.BytesIO()
                    im.convert('RGB').save(out,format='PNG')
                    images[r.href]=out.getvalue()
                else:
                    images[r.href]=r.data
            except Exception:
                book.warnings.append('KFX 忽略了一张无法解析的图片。')
    if any(r.media_type=='image/svg+xml' for r in book.resources.values()):
        book.warnings.append('KFX 暂未嵌入 SVG 资源，请用 EPUB 保留矢量图。')
    faces=[]
    if book.embedded_font:
        faces.append(Face('lumeembedded',400,False,book.embedded_font,'LumeEmbedded','resource/lume_font'))
    if not faces:
        faces=source_font_faces(book)
    generator=NativeKFXGenerator()
    # Older USB Kindles need EBOK plus an uploaded library thumbnail.
    # Modern MTP firmware derives library covers from personal documents.
    book.device_cdetype='EBOK' if layout.kfx_mode=='legacy' else 'PDOC'
    generator.lume_cde_content_type=book.device_cdetype
    # KFX line-height uses reader-relative lh, with a 1.2 CSS baseline.
    generator.lume_line_height_base=1.2
    ctx.update(80,'序列化 KFX 与字体资源')
    identity=hashlib.sha256((book.title+'\0'+book.author+'\0'+str(layout.to_dict())).encode('utf-8'))
    identity.update(b'Lume-KFX-typography-v2')
    identity.update(book.embedded_font)
    for chapter in book.chapters:
        identity.update((chapter.css+chapter.body).encode('utf-8'))
    for face in faces:
        identity.update(face.data)
    for chapter in chapters:
        identity.update(chapter['text'].encode('utf-8'))
    if book.cover_href in book.resources:
        identity.update(book.resources[book.cover_href].data)
    book.device_asin=identity.hexdigest()[:32].upper()
    data=generator.generate_full_book(title=book.title,author=book.author,chapters=chapters,
                asin=book.device_asin,
                language=book.language,publisher='Lume Reader',images=images or None,
                cover_image=images.get(book.cover_href),font_table=FontTable(faces),resolved_image_refs=True)
    ctx.check()
    if data[:4]!=b'CONT':
        raise ConversionError('KFX 容器验证失败。')
    Path(path).write_bytes(data)
    book.warnings.append('Kindle 阅读设置可以覆盖书内字体和行距；复杂版式建议预览确认。')

def source_font_faces(book):
    """Retain unencrypted EPUB font faces when the user has not replaced them."""
    import re
    import tinycss2
    from kfxgen.font_table import Face,is_ttf_otf
    result=[]
    seen=set()
    sheets=[(r.href,r.data.decode('utf-8',errors='replace')) for r in book.resources.values()
            if r.media_type=='text/css']
    sheets.extend((ch.href,ch.css) for ch in book.chapters)
    for base,css in sheets:
        for rule in tinycss2.parse_stylesheet(css,skip_comments=True,skip_whitespace=True):
            if rule.type!='at-rule' or rule.lower_at_keyword!='font-face' or not rule.content:
                continue
            values={k:v[0] for k,v in declarations(tinycss2.serialize(rule.content)).items()}
            family=values.get('font-family','').strip().strip(chr(34)+chr(39)).lower()
            links=re.findall(r'url\(\s*([^)]*)\)',values.get('src',''),re.I)
            for link in links:
                resolved=resolve_href(base,link.strip().strip(chr(34)+chr(39)))
                resource=book.resources.get(resolved[0]) if resolved else None
                if not family or not resource or not is_ttf_otf(resource.data): continue
                weight=values.get('font-weight','400')
                weight=int(weight) if weight.isdigit() else 700 if weight=='bold' else 400
                italic=values.get('font-style','normal') in ('italic','oblique')
                key=(family,weight,italic)
                if key not in seen:
                    slug='LumeSource'+hashlib.sha1(family.encode()).hexdigest()[:10]
                    result.append(Face(family,weight,italic,resource.data,slug,'resource/font'+str(len(result))))
                    seen.add(key)
                break
    return result

def set_pdb_identity(path,book,layout):
    from kindleunpack.mobi_split import readsection,writesection,read_exth,write_exth,add_exth
    data=Path(path).read_bytes()
    identity=hashlib.sha256(data).hexdigest()[:32].upper()
    book.device_asin=identity
    # Update both halves of a hybrid MOBI before extracting the KF8 half.
    header=readsection(data,0)
    boundaries=read_exth(header,121)
    indices=[0]
    if boundaries:
        boundary=struct.unpack('>I',boundaries[0])[0]
        if boundary!=0xffffffff: indices.append(boundary)
    for index in indices:
        header=readsection(data,index)
        for key,value in ((113,identity.encode('ascii')),(504,identity.encode('ascii')),(501,b'PDOC')):
            header=(write_exth if read_exth(header,key) else add_exth)(header,key,value)
        data=writesection(data,index,header)
    Path(path).write_bytes(data)

KFX_HEADING_CSS = """
h1 {font-size:1.6em;font-weight:700;text-align:left;margin-top:1.4em;margin-bottom:0.9em;}
h2 {font-size:1.35em;font-weight:700;text-align:left;margin-top:1.2em;margin-bottom:0.8em;}
h3,h4,h5,h6 {font-size:1.15em;font-weight:700;text-align:left;margin-top:1em;margin-bottom:0.6em;}
"""

def kfx_font_pixels(value,parent,root):
    import re
    if isinstance(value,(int,float)):
        return max(1,float(value))
    text=str(value or '').strip().lower()
    match=re.fullmatch(r'([0-9]*[.]?[0-9]+)(px|pt|em|rem|%)?',text)
    if match:
        number=float(match[1])
        factors={'px':1,'pt':4/3,'em':parent,'rem':root,'%':parent/100,None:1}
        return max(1,number*factors[match[2]])
    if text=='larger': return parent*1.2
    if text=='smaller': return parent/1.2
    return parent
