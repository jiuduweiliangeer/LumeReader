from __future__ import annotations
import base64
from html import escape
import io
from pathlib import Path
import posixpath
import re
from urllib.parse import unquote
from lxml import etree, html
from .model import Book, Chapter, TocEntry, Resource, ConversionError
from .util import xml, safe_zip, fragment, inner_body, resolve_href, relative_link, mime

INPUTS = ('txt','epub','mobi','azw','azw3','kfx','kfx-zip','kpf','pdf','html','htm','docx','fb2','md')
CHAPTER_RE = re.compile(
    r'^(?:第[零〇一二三四五六七八九十百千万两\d]{1,16}[章节卷回部篇集].*|'
    r'(?:卷|chapter|part|book)\s*[零一二三四五六七八九十百千万\dIVXLC]+.*|'
    r'(?:序章|序言|楔子|引子|尾声|终章|后记|番外)(?:\s.*|[：:].*|[一二三四五六七八九十\d].*)?)$',
    re.I)

def detect_encoding(path, requested='auto'):
    if requested != 'auto':
        return requested
    with open(path, 'rb') as stream:
        sample = stream.read(131072)
    if sample.startswith((b'\xff\xfe', b'\xfe\xff')):
        return 'utf-16'
    if sample.startswith(b'\xef\xbb\xbf'):
        return 'utf-8-sig'
    # Use an incremental decoder: sample may end in the middle of a codepoint.
    import codecs
    try:
        codecs.getincrementaldecoder('utf-8')().decode(sample, final=False)
        return 'utf-8'
    except UnicodeDecodeError:
        return 'gb18030'

def read_txt(path, layout, ctx):
    encoding = detect_encoding(path, layout.encoding)
    book = Book(Path(path).stem)
    pattern = re.compile(layout.chapter_pattern) if layout.chapter_pattern else CHAPTER_RE
    title = '正文'
    paragraphs, pending = [], []
    length = 0
    total = max(Path(path).stat().st_size, 1)

    def flush_paragraph():
        if pending:
            # CJK soft wraps have no intervening spaces; Latin words do.
            value = pending[0]
            for line in pending[1:]:
                sep = ' ' if value[-1:].isascii() and line[:1].isascii() else ''
                value += sep + line
            paragraphs.append('<p>' + escape(value) + '</p>')
            pending.clear()

    def flush_chapter():
        nonlocal paragraphs, length
        flush_paragraph()
        if paragraphs:
            book.add_chapter(title, '<h1>' + escape(title) + '</h1>\n' + '\n'.join(paragraphs))
        paragraphs = []
        length = 0

    try:
        with open(path, encoding=encoding, errors='strict') as stream:
            for index, raw in enumerate(stream):
                if index % 2000 == 0:
                    ctx.update(5 + 15 * stream.buffer.tell() / total, f'读取文本 · {index:,} 行')
                text = raw.strip('\r\n').strip()
                if not text:
                    flush_paragraph()
                    continue
                text = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)
                markdown_heading = Path(path).suffix.lower() == '.md' and re.match(r'^#{1,6}\s+', text)
                if len(text) <= 100 and (pattern.match(text) or markdown_heading):
                    flush_chapter()
                    title = re.sub(r'^#{1,6}\s+', '', text) if markdown_heading else text
                    continue
                length += len(text)
                if layout.join_lines:
                    pending.append(text)
                else:
                    paragraphs.append('<p>' + escape(text) + '</p>')
                # Bound individual chapter size for e-ink readers and long chapterless files.
                if length >= 120000:
                    flush_chapter()
                    title = re.sub(r'（续 \d+）$', '', title) + f'（续 {len(book.chapters)+1}）'
            flush_chapter()
    except UnicodeDecodeError as exc:
        raise ConversionError('文本解码失败，请在高级设置中指定 UTF-8、GB18030 或 UTF-16。') from exc
    if not book.chapters:
        raise ConversionError('文本没有可转换的正文。')
    book.warnings.append(f'文本编码：{encoding}')
    return book

def read_epub(path, layout, ctx):
    with safe_zip(path) as z:
        names = set(z.namelist())
        container = xml(z.read('META-INF/container.xml'))
        opf_path = container.xpath('//*[local-name()="rootfile"]/@full-path')[0]
        opf = xml(z.read(opf_path))
        if 'META-INF/encryption.xml' in names:
            encryption = xml(z.read('META-INF/encryption.xml'))
            algorithms = encryption.xpath('//*[local-name()="EncryptionMethod"]/@Algorithm')
            if algorithms:
                raise ConversionError('此 EPUB 含加密或混淆资源，暂不支持；请提供未加密的源文件。')
        def metadata(name, default):
            values = opf.xpath(f'//*[local-name()="metadata"]/*[local-name()="{name}"]/text()')
            return values[0].strip() if values else default
        book = Book(metadata('title',Path(path).stem), metadata('creator','佚名'),
                    metadata('language','zh-CN'))
        manifest = {}
        for item in opf.xpath('//*[local-name()="manifest"]/*[local-name()="item"]'):
            resolved = resolve_href(opf_path, item.get('href',''))
            if resolved:
                manifest[item.get('id')] = (resolved[0], item.get('media-type',''), item.get('properties',''))
        spine = [manifest[i] for i in opf.xpath('//*[local-name()="spine"]/*/@idref') if i in manifest]
        cover_docs=set()
        for href in opf.xpath('//*[local-name()="guide"]/*[@type="cover"]/@href'):
            resolved=resolve_href(opf_path,href)
            if resolved: cover_docs.add(resolved[0])
        spine = [x for x in spine if 'nav' not in x[2]]
        if any(x[0] not in cover_docs for x in spine):
            spine=[x for x in spine if x[0] not in cover_docs]
        if not spine:
            raise ConversionError('EPUB 没有有效的阅读顺序。')
        mapping = {old: f'text/ch{i+1:05d}.xhtml' for i,(old,_,_) in enumerate(spine)}
        for old, mediatype, props in manifest.values():
            if old in mapping or old not in names or 'nav' in props or mediatype.endswith('ncx+xml'):
                continue
            new = 'assets/' + old
            mapping[old] = new
            book.resources[new] = Resource(new, z.read(old), mediatype or mime(old))
            if 'cover-image' in props:
                book.cover_href = new
        legacy_cover = opf.xpath('//*[local-name()="meta"][@name="cover"]/@content')
        if not book.cover_href and legacy_cover and legacy_cover[0] in manifest:
            book.cover_href = mapping.get(manifest[legacy_cover[0]][0], '')
        raw_toc = []
        for old, mediatype, props in manifest.values():
            if 'nav' in props and old in names:
                nav_root = xml(z.read(old))
                navs = nav_root.xpath('//*[local-name()="nav"]')
                nav = next((n for n in navs if 'toc' in n.get('{http://www.idpf.org/2007/ops}type','').split()), None)
                if nav is not None:
                    for a in nav.xpath('.//*[local-name()="a"][@href]'):
                        level = len(a.xpath('ancestor::*[local-name()="ol"]'))
                        raw_toc.append((''.join(a.itertext()).strip(), old, a.get('href'), max(1,level)))
        if not raw_toc:
            for old, mediatype, props in manifest.values():
                if mediatype.endswith('ncx+xml') and old in names:
                    for point in xml(z.read(old)).xpath('//*[local-name()="navPoint"]'):
                        label = point.xpath('./*[local-name()="navLabel"]/*[local-name()="text"]/text()')
                        href = point.xpath('./*[local-name()="content"]/@src')
                        if label and href:
                            raw_toc.append((label[0],old,href[0],1+len(point.xpath('ancestor::*[local-name()="navPoint"]'))))
        for label, base, href, level in raw_toc:
            resolved = resolve_href(base,href)
            if resolved and resolved[0] in mapping and resolved[0] not in cover_docs:
                book.toc.append(TocEntry(label,mapping[resolved[0]]+('#'+resolved[1] if resolved[1] else ''),level))
        for index,(old,_,_) in enumerate(spine):
            ctx.update(5+15*index/len(spine),f'读取 EPUB · {index+1}/{len(spine)}')
            raw = z.read(old)
            doc = html.document_fromstring(re.sub(r'^\s*<\?xml[^>]*\?>', '', raw.decode('utf-8-sig')))
            root = inner_body(raw)
            new = mapping[old]
            css_parts = []
            for link in doc.xpath('//link[@href]'):
                resolved = resolve_href(old,link.get('href'))
                if resolved and resolved[0] in mapping:
                    css_parts.append('@import url("' + relative_link(new,mapping[resolved[0]]) + '");')
            css_parts += doc.xpath('//style/text()')
            for el in root.iter():
                if not isinstance(el.tag,str):
                    continue
                for attr in ('src','href','poster','{http://www.w3.org/1999/xlink}href'):
                    value = el.get(attr)
                    if value:
                        resolved = resolve_href(old,value)
                        if resolved and resolved[0] in mapping:
                            el.set(attr,relative_link(new,mapping[resolved[0]],resolved[1]))
                        elif attr == 'src' and not value.startswith('data:'):
                            el.attrib.pop(attr,None)
            labels = [x.title for x in book.toc if x.href.split('#')[0] == new]
            headings = root.xpath('.//h1|.//h2|.//h3')
            title = labels[0] if labels else (''.join(headings[0].itertext()).strip() if headings else f'第 {index+1} 节')
            first = next((n for n in root.xpath('.//p|.//h1|.//h2|.//h3') if ''.join(n.itertext()).strip()), None)
            if first is not None and first.tag=='p' and ''.join(first.itertext()).strip()==title and len(title)<=120:
                first.tag='h1'
            book.chapters.append(Chapter(title,fragment(root),new,'\n'.join(css_parts)))
        if not book.toc:
            make_heading_toc(book)
        return book

def make_heading_toc(book):
    book.toc.clear()
    for chapter in book.chapters:
        root = html.fragment_fromstring(chapter.body, create_parent='div')
        headings = root.xpath('.//h1|.//h2|.//h3')
        for i,node in enumerate(headings):
            anchor = node.get('id') or f'lume-heading-{i}'
            node.set('id',anchor)
            book.toc.append(TocEntry(''.join(node.itertext()).strip(),chapter.href+'#'+anchor,int(node.tag[1])))
        if not headings:
            book.toc.append(TocEntry(chapter.title,chapter.href))
        chapter.body = fragment(root)

def read_html(path, layout, ctx):
    path = Path(path)
    text = path.read_text(encoding=detect_encoding(path,layout.encoding))
    doc = html.document_fromstring(re.sub(r'^\s*<\?xml[^>]*\?>', '', text))
    titles = doc.xpath('//title/text()')
    book = Book(titles[0].strip() if titles else path.stem)
    root = inner_body(text)
    # Only load local resources inside the document's directory.
    chapter = Chapter(book.title,'','text/ch00001.xhtml','\n'.join(doc.xpath('//style/text()')))
    def embedded(value):
        import hashlib,mimetypes
        from urllib.parse import unquote_to_bytes
        header,payload=value.split(',',1)
        media=header[5:].split(';')[0] or 'application/octet-stream'
        if len(payload)>90*1024**2:
            raise ConversionError('HTML 内嵌资源超过 64 MB。')
        data=base64.b64decode(re.sub(r'\s+','',payload),validate=True) if ';base64' in header.lower() else unquote_to_bytes(payload)
        if len(data)>64*1024**2: raise ConversionError('HTML 内嵌资源超过 64 MB。')
        extension={ 'image/jpeg':'.jpg','image/png':'.png','font/ttf':'.ttf',
                    'font/otf':'.otf','application/x-font-ttf':'.ttf'}.get(media,mimetypes.guess_extension(media) or '.bin')
        href='assets/embedded-'+hashlib.sha256(data).hexdigest()[:20]+extension
        book.resources[href]=Resource(href,data,media)
        return href
    def embedded_css(css):
        def replace(match):
            href=embedded(match.group(2))
            return 'url("'+relative_link(chapter.href,href)+'")'
        return re.sub(r'url\(\s*([\'"]?)(data:[^)]*?)\1\s*\)',replace,css,flags=re.I)
    for node in root.xpath('.//*[@src]'):
        value = node.get('src')
        if value.lower().startswith('data:'):
            href=embedded(value)
            node.set('src',relative_link(chapter.href,href))
            if node.get('alt','').casefold() in ('封面','cover'): book.cover_href=href
            continue
        resolved = resolve_href(path.name,value)
        if not resolved:
            node.attrib.pop('src',None)
            continue
        local = (path.parent / resolved[0]).resolve()
        if local.is_file() and path.parent.resolve() in local.parents:
            href = 'assets/' + resolved[0]
            book.resources[href] = Resource(href,local.read_bytes(),mime(href))
            node.set('src',relative_link(chapter.href,href))
    for link in doc.xpath('//link[@rel="stylesheet"][@href]'):
        resolved = resolve_href(path.name,link.get('href'))
        if resolved:
            local = (path.parent/resolved[0]).resolve()
            if local.is_file() and path.parent.resolve() in local.parents:
                chapter.css += '\n' + local.read_text(encoding='utf-8',errors='replace')
    chapter.body = fragment(root)
    book.chapters.append(chapter)
    make_heading_toc(book)
    return book

def read_pdf(path, layout, ctx):
    import pymupdf
    doc = pymupdf.open(path)
    if doc.needs_pass:
        doc.close()
        raise ConversionError('PDF 已加密，请先提供可读取的 PDF。')
    book = Book(doc.metadata.get('title') or Path(path).stem,doc.metadata.get('author') or '佚名')
    scanned = 0
    page_toc = {}
    for level,title,page in doc.get_toc():
        page_toc.setdefault(page,[]).append((level,title))
    try:
        for i,page in enumerate(doc):
            ctx.update(5+15*i/max(len(doc),1),f'提取 PDF · {i+1}/{len(doc)} 页')
            title = page_toc.get(i+1,[(1,f'第 {i+1} 页')])[0][1]
            blocks = page.get_text('blocks',sort=True)
            text_blocks = [b[4].strip() for b in blocks if b[6] == 0 and b[4].strip()]
            if not text_blocks:
                scanned += 1
                image = page.get_pixmap(matrix=pymupdf.Matrix(1.5,1.5),alpha=False)
                href = f'assets/page{i+1:05d}.png'
                book.resources[href] = Resource(href,image.tobytes('png'),'image/png')
                body = '<img src="../'+href+'" alt="'+escape(title)+'"/>'
            else:
                parts = []
                mixed = page.get_text('dict',sort=True)['blocks']
                for index,block in enumerate(mixed):
                    if block['type']==1:
                        href=f'assets/page{i+1:05d}-image{index}.{block["ext"]}'
                        book.resources[href]=Resource(href,block['image'],mime(href))
                        parts.append('<p><img src="../'+href+'"/></p>')
                        continue
                    lines=[''.join(span['text'] for span in line['spans']) for line in block.get('lines',[])]
                    value = ''
                    for line in lines:
                        sep = ' ' if value[-1:].isascii() and line[:1].isascii() else ''
                        value += (sep if value else '')+line.strip()
                    if value.strip(): parts.append('<p>'+escape(value)+'</p>')
                body = '\n'.join(parts)
            book.add_chapter(title,body)
        if scanned:
            book.warnings.append(f'{scanned} 页没有文本层，已按图片保留；未执行 OCR，图片内文字无法缩进。')
        book.warnings.append('PDF 按文本块提取后重排；多栏、公式和复杂表格请检查输出。')
        return book
    finally:
        doc.close()

def read_docx(path, layout, ctx):
    book = Book(Path(path).stem)
    w = {'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    with safe_zip(path) as z:
        doc = xml(z.read('word/document.xml'))
        rels = {}
        if 'word/_rels/document.xml.rels' in z.namelist():
            for rel in xml(z.read('word/_rels/document.xml.rels')):
                if rel.get('TargetMode') != 'External':
                    resolved = resolve_href('word/document.xml',rel.get('Target',''))
                    if resolved:
                        rels[rel.get('Id')] = resolved[0]
        title, parts = '正文', []
        for i,p in enumerate(doc.xpath('//w:body/w:p|//w:body/w:tbl//w:p',namespaces=w)):
            if i % 500 == 0:
                ctx.check()
            text = ''.join(p.xpath('.//w:t/text()',namespaces=w))
            styles = p.xpath('./w:pPr/w:pStyle/@w:val',namespaces=w)
            is_heading = styles and re.match(r'(?:Heading|标题)[1-3]$',styles[0],re.I)
            if is_heading and text.strip():
                if parts:
                    book.add_chapter(title,'\n'.join(parts))
                title, parts = text.strip(), ['<h1>'+escape(text.strip())+'</h1>']
            elif text.strip():
                parts.append('<p>'+escape(text)+'</p>')
            for image in p.xpath('.//*[local-name()="blip"]'):
                rid = image.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}embed')
                target = rels.get(rid)
                if target and target in z.namelist():
                    href = 'assets/'+target
                    book.resources[href] = Resource(href,z.read(target),mime(target))
                    parts.append('<p><img src="../'+href+'"/></p>')
        if parts:
            book.add_chapter(title,'\n'.join(parts))
    if not book.chapters:
        raise ConversionError('DOCX 中没有可读取的内容。')
    book.warnings.append('DOCX 以正文、标题和图片为主导入，复杂表格与批注不保留。')
    return book

def read_fb2(path, layout, ctx):
    root = xml(Path(path).read_bytes())
    titles = root.xpath('//*[local-name()="title-info"]/*[local-name()="book-title"]/text()')
    author = root.xpath('//*[local-name()="title-info"]/*[local-name()="author"]/*/text()')
    book = Book(titles[0] if titles else Path(path).stem,' '.join(author) or '佚名')
    for resource in root.xpath('//*[local-name()="binary"]'):
        href = 'assets/'+resource.get('id','image')
        book.resources[href] = Resource(href,base64.b64decode(resource.text or '',validate=False),
                                       resource.get('content-type','image/jpeg'))
    cover=root.xpath('//*[local-name()="title-info"]/*[local-name()="coverpage"]/*[local-name()="image"]/@*[local-name()="href"]')
    if cover:
        href='assets/'+str(cover[0]).lstrip('#')
        if href in book.resources: book.cover_href=href
    for section in root.xpath('//*[local-name()="body"]/*[local-name()="section"]'):
        title = section.xpath('./*[local-name()="title"]//text()')
        parts = []
        for node in section.iter():
            tag = etree.QName(node).localname
            if tag in ('p','subtitle'):
                text = ''.join(node.itertext())
                heading=node.getparent() is not None and etree.QName(node.getparent()).localname=='title'
                tag='h1' if heading else 'p'
                parts.append('<'+tag+'>'+escape(text)+'</'+tag+'>')
            elif tag == 'image':
                ref = node.get('{http://www.w3.org/1999/xlink}href','').lstrip('#')
                parts.append('<p><img src="../assets/'+escape(ref,quote=True)+'"/></p>')
        book.add_chapter(''.join(title).strip() or f'第 {len(book.chapters)+1} 节','\n'.join(parts))
    if not book.chapters:
        raise ConversionError('FB2 中没有可读取的章节。')
    return book

def read_book(path, layout, ctx, workdir):
    suffix = Path(path).suffix.lower().lstrip('.')
    if suffix in ('txt','md'):
        return read_txt(path,layout,ctx)
    if suffix == 'epub':
        return read_epub(path,layout,ctx)
    if suffix in ('html','htm'):
        return read_html(path,layout,ctx)
    if suffix == 'pdf':
        return read_pdf(path,layout,ctx)
    if suffix == 'docx':
        return read_docx(path,layout,ctx)
    if suffix == 'fb2':
        return read_fb2(path,layout,ctx)
    if suffix in ('mobi','azw','azw3','kfx','kfx-zip','kpf'):
        from .kindle_formats import decode_kindle
        extracted = decode_kindle(Path(path),Path(workdir),ctx)
        book = read_epub(extracted,layout,ctx) if extracted.suffix == '.epub' else read_html(extracted,layout,ctx)
        return book
    raise ConversionError(f'不支持输入格式：{suffix}')
