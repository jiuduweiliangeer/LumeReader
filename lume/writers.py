from __future__ import annotations
import base64
from datetime import datetime, timezone
from html import escape
import io
from pathlib import Path
import re
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED
from lxml import etree
from .model import ConversionError
from .typography import stylesheet, declarations, css_for_chapter
from .util import XHTML, EPUB, XML, body_root, fragment, plain_text, resolve_href

OUTPUTS = ('epub','azw3','kfx','mobi','pdf','txt','html','fb2')
OPF = 'http://www.idpf.org/2007/opf'
DC = 'http://purl.org/dc/elements/1.1/'
NCX = 'http://www.daisy.org/z3986/2005/ncx/'

def xml_bytes(root):
    return etree.tostring(root,xml_declaration=True,encoding='utf-8',pretty_print=False)

def xhtml_document(title,body,css='',lang='zh-CN',link=True):
    root = etree.Element('{'+XHTML+'}html',nsmap={None:XHTML,'epub':EPUB})
    root.set('{'+XML+'}lang',lang)
    root.set('lang',lang)
    head = etree.SubElement(root,'{'+XHTML+'}head')
    etree.SubElement(head,'{'+XHTML+'}title').text = title
    etree.SubElement(head,'{'+XHTML+'}meta',charset='utf-8')
    if css:
        # Keep shared stylesheets as links. Repeated inline @import statements
        # trigger a KindleGen 2.9 parser crash on some large decoded KFX books.
        def stylesheet_link(match):
            etree.SubElement(head,'{'+XHTML+'}link',rel='stylesheet',href=match.group(1),type='text/css')
            return ''
        css=re.sub(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\']\s*\)?\s*;',stylesheet_link,css,flags=re.I)
        if css.strip(): etree.SubElement(head,'{'+XHTML+'}style',type='text/css').text = css
    if link:
        etree.SubElement(head,'{'+XHTML+'}link',rel='stylesheet',href='../styles/reader.css',type='text/css')
    body_el = etree.SubElement(root,'{'+XHTML+'}body')
    parsed = body_root(body)
    body_el.text = parsed.text
    for child in parsed:
        # Parsing serialized XHTML re-establishes the default namespace correctly.
        body_el.append(child)
    return xml_bytes(root)

def toc_tree(entries):
    """Return a hierarchy even if source heading levels start at h2/h3."""
    roots, stack = [], []
    for entry in entries:
        node = [entry,[]]
        while stack and stack[-1][0].level >= entry.level:
            stack.pop()
        if stack:
            stack[-1][1].append(node)
        else:
            roots.append(node)
        stack.append(node)
    return roots

def write_epub(book,path,layout,ctx):
    package = etree.Element('{'+OPF+'}package',nsmap={None:OPF,'dc':DC},version='3.0',
                            attrib={'unique-identifier':'book-id'})
    metadata = etree.SubElement(package,'{'+OPF+'}metadata')
    for tag,value in [('title',book.title),('creator',book.author),('language',book.language)]:
        etree.SubElement(metadata,'{'+DC+'}'+tag).text=value
    etree.SubElement(metadata,'{'+DC+'}identifier',id='book-id').text=book.uid
    etree.SubElement(metadata,'{'+OPF+'}meta',property='dcterms:modified').text=datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    manifest=etree.SubElement(package,'{'+OPF+'}manifest')
    spine=etree.SubElement(package,'{'+OPF+'}spine',toc='ncx')
    def item(id,href,kind,**attrs):
        return etree.SubElement(manifest,'{'+OPF+'}item',id=id,href=href,attrib={'media-type':kind,**attrs})
    item('style','styles/reader.css','text/css')
    item('nav','nav.xhtml','application/xhtml+xml',properties='nav')
    item('ncx','toc.ncx','application/x-dtbncx+xml')
    has_cover=book.cover_href in book.resources
    if has_cover:
        item('lume-cover-page','text/lume-cover.xhtml','application/xhtml+xml')
        etree.SubElement(spine,'{'+OPF+'}itemref',idref='lume-cover-page')
    for index,ch in enumerate(book.chapters):
        attrs = {'properties':'svg'} if '<svg' in ch.body else {}
        item(f'ch{index}',ch.href,'application/xhtml+xml',**attrs)
        etree.SubElement(spine,'{'+OPF+'}itemref',idref=f'ch{index}')
    for index,r in enumerate(book.resources.values()):
        attrs={'properties':'cover-image'} if r.href == book.cover_href else {}
        item(f'r{index}',r.href,r.media_type,**attrs)
        if r.href==book.cover_href:
            etree.SubElement(metadata,'{'+OPF+'}meta',name='cover',content=f'r{index}')
    nav=etree.Element('{'+XHTML+'}html',nsmap={None:XHTML,'epub':EPUB})
    nav.set('{'+XML+'}lang',book.language)
    head=etree.SubElement(nav,'{'+XHTML+'}head')
    etree.SubElement(head,'{'+XHTML+'}title').text='目录'
    body=etree.SubElement(nav,'{'+XHTML+'}body')
    toc=etree.SubElement(body,'{'+XHTML+'}nav',id='toc',attrib={'{'+EPUB+'}type':'toc'})
    etree.SubElement(toc,'{'+XHTML+'}h1').text='目录'
    ncx=etree.Element('{'+NCX+'}ncx',nsmap={None:NCX},version='2005-1')
    nhead=etree.SubElement(ncx,'{'+NCX+'}head')
    etree.SubElement(nhead,'{'+NCX+'}meta',name='dtb:uid',content=book.uid)
    etree.SubElement(nhead,'{'+NCX+'}meta',name='dtb:depth',content=str(max([x.level for x in book.toc] or [1])))
    etree.SubElement(nhead,'{'+NCX+'}meta',name='dtb:totalPageCount',content='0')
    etree.SubElement(nhead,'{'+NCX+'}meta',name='dtb:maxPageNumber',content='0')
    etree.SubElement(etree.SubElement(ncx,'{'+NCX+'}docTitle'),'{'+NCX+'}text').text=book.title
    navmap=etree.SubElement(ncx,'{'+NCX+'}navMap')
    counter=[0]
    def emit(nodes,html_parent,ncx_parent):
        ol=etree.SubElement(html_parent,'{'+XHTML+'}ol')
        for entry,children in nodes:
            counter[0]+=1
            li=etree.SubElement(ol,'{'+XHTML+'}li')
            etree.SubElement(li,'{'+XHTML+'}a',href=entry.href).text=entry.title
            point=etree.SubElement(ncx_parent,'{'+NCX+'}navPoint',id=f'nav{counter[0]}',playOrder=str(counter[0]))
            etree.SubElement(etree.SubElement(point,'{'+NCX+'}navLabel'),'{'+NCX+'}text').text=entry.title
            etree.SubElement(point,'{'+NCX+'}content',src=entry.href)
            if children:
                emit(children,li,point)
    emit(toc_tree(book.toc),toc,navmap)
    guide=etree.SubElement(package,'{'+OPF+'}guide')
    if has_cover:
        etree.SubElement(guide,'{'+OPF+'}reference',type='cover',title='封面',href='text/lume-cover.xhtml')
    etree.SubElement(guide,'{'+OPF+'}reference',type='toc',title='目录',href='nav.xhtml')
    etree.SubElement(guide,'{'+OPF+'}reference',type='text',title='正文',href=book.chapters[0].href)
    with ZipFile(path,'w',compression=ZIP_DEFLATED,compresslevel=3) as z:
        z.writestr('mimetype','application/epub+zip',compress_type=ZIP_STORED)
        z.writestr('META-INF/container.xml',b'<?xml version="1.0"?><container version="1.0" xmlns="urn:oasis:names:tc:opendocument:xmlns:container"><rootfiles><rootfile full-path="OEBPS/content.opf" media-type="application/oebps-package+xml"/></rootfiles></container>')
        z.writestr('OEBPS/content.opf',xml_bytes(package))
        z.writestr('OEBPS/nav.xhtml',xml_bytes(nav))
        z.writestr('OEBPS/toc.ncx',xml_bytes(ncx))
        z.writestr('OEBPS/styles/reader.css',stylesheet(layout,book))
        if has_cover:
            cover_body='<div style="text-align:center"><img src="../'+escape(book.cover_href,quote=True)+'" alt="封面"/></div>'
            z.writestr('OEBPS/text/lume-cover.xhtml',xhtml_document('封面',cover_body,lang=book.language))
        for i,ch in enumerate(book.chapters):
            if i%20 == 0:
                ctx.check()
            z.writestr('OEBPS/'+ch.href,xhtml_document(ch.title,ch.body,ch.css,book.language))
        for r in book.resources.values():
            ctx.check()
            z.writestr('OEBPS/'+r.href,r.data)

def write_txt(book,path,layout,ctx):
    if book.cover_href: book.warnings.append('TXT 是纯文本格式，无法保存封面图片。')
    with open(path,'w',encoding='utf-8',newline='\n') as out:
        out.write(book.title+'\n'+book.author+'\n\n目录\n')
        out.write('\n'.join(x.title for x in book.toc)+'\n\n')
        for ch in book.chapters:
            ctx.check()
            root=body_root(ch.body)
            out.write('\n'+ch.title+'\n\n')
            for el in root.xpath('.//p|.//h1|.//h2|.//h3|.//li|.//pre'):
                text=''.join(el.itertext()).strip()
                if not text or (el.tag.startswith('h') and text == ch.title):
                    continue
                prefix=''
                if el.tag=='p':
                    indent=declarations(el.get('style','')).get('text-indent',('0',False))[0]
                    match=re.match(r'([\d.]+)',indent)
                    amount=float(match.group(1)) if match else 0
                    if indent.endswith('px'): amount/=layout.font_size
                    elif indent.endswith('pt'): amount/=(layout.font_size*.75)
                    prefix='\u3000'*min(8,max(0,round(amount)))
                out.write(prefix+text+'\n' + ('\n' if layout.paragraph_gap else ''))
    book.warnings.append('TXT 使用全角空格实现缩进，格式本身不支持字体嵌入、精确行距或可点击目录。')

def write_html(book,path,layout,ctx):
    css=stylesheet(layout,book)
    resources=book.resources
    def data_url(href):
        r=resources[href]
        return 'data:'+r.media_type+';base64,'+base64.b64encode(r.data).decode('ascii')
    def inline_css(text,base):
        def replace(match):
            target=match.group(1).strip("'\" ")
            resolved=resolve_href(base,target)
            return 'url("'+data_url(resolved[0])+'")' if resolved and resolved[0] in resources else 'url("")'
        return re.sub(r'url\(([^)]+)\)',replace,text)
    css=inline_css(css,'styles/reader.css')
    id_map={}
    for i,ch in enumerate(book.chapters):
        id_map[ch.href]=f'chapter-{i}'
        for el in body_root(ch.body).xpath('.//*[@id]'):
            id_map[ch.href+'#'+el.get('id')]=f'chapter-{i}-'+el.get('id')
    sections=[]
    for i,ch in enumerate(book.chapters):
        ctx.check()
        root=body_root(ch.body)
        for node in root.iter():
            if node.get('id'):
                node.set('id',id_map[ch.href+'#'+node.get('id')])
            for attr in ('href','src'):
                value=node.get(attr)
                resolved=resolve_href(ch.href,value) if value else None
                if not resolved:
                    continue
                target,anchor=resolved
                key=target+('#'+anchor if anchor else '')
                if attr=='href' and key in id_map:
                    node.set(attr,'#'+id_map[key])
                elif target in resources:
                    node.set(attr,data_url(target))
        css+='\n'+inline_css(css_for_chapter(book,ch),ch.href)
        sections.append(f'<section id="chapter-{i}">'+fragment(root)+'</section>')
    links=''.join('<li><a href="#'+id_map.get(e.href,id_map.get(e.href.split('#')[0],''))+'">'+escape(e.title)+'</a></li>' for e in book.toc)
    output='<!DOCTYPE html><html lang="'+escape(book.language)+'"><head><meta charset="utf-8"><title>'+escape(book.title)+'</title><style>'+css+'</style></head><body><nav><h1>目录</h1><ol>'+links+'</ol></nav>'+''.join(sections)+'</body></html>'
    if book.cover_href in book.resources:
        output=output.replace('<body>','<body><div style="text-align:center"><img alt="封面" src="'+data_url(book.cover_href)+'"/></div>',1)
    Path(path).write_text(output,encoding='utf-8')

def write_fb2(book,path,layout,ctx):
    ns='http://www.gribuser.ru/xml/fictionbook/2.0'
    root=etree.Element('{'+ns+'}FictionBook',nsmap={None:ns,'l':'http://www.w3.org/1999/xlink'})
    desc=etree.SubElement(root,'{'+ns+'}description')
    info=etree.SubElement(desc,'{'+ns+'}title-info')
    etree.SubElement(info,'{'+ns+'}genre').text='prose'
    author=etree.SubElement(info,'{'+ns+'}author')
    etree.SubElement(author,'{'+ns+'}nickname').text=book.author
    etree.SubElement(info,'{'+ns+'}book-title').text=book.title
    etree.SubElement(info,'{'+ns+'}lang').text=book.language
    di=etree.SubElement(desc,'{'+ns+'}document-info')
    au=etree.SubElement(di,'{'+ns+'}author')
    etree.SubElement(au,'{'+ns+'}nickname').text='Lume'
    etree.SubElement(di,'{'+ns+'}date').text=datetime.now().strftime('%Y-%m-%d')
    etree.SubElement(di,'{'+ns+'}id').text=book.uid
    etree.SubElement(di,'{'+ns+'}version').text='1.0'
    body=etree.SubElement(root,'{'+ns+'}body')
    image_map={}
    if book.cover_href in book.resources:
        image_map[book.cover_href]='cover'
        coverpage=etree.SubElement(info,'{'+ns+'}coverpage')
        etree.SubElement(coverpage,'{'+ns+'}image',attrib={'{http://www.w3.org/1999/xlink}href':'#cover'})
    for ch in book.chapters:
        ctx.check()
        sec=etree.SubElement(body,'{'+ns+'}section')
        etree.SubElement(etree.SubElement(sec,'{'+ns+'}title'),'{'+ns+'}p').text=ch.title
        for p in body_root(ch.body).xpath('.//p|.//h2|.//h3|.//img|.//li'):
            if p.tag=='img':
                resolved=resolve_href(ch.href,p.get('src',''))
                if resolved and resolved[0] in book.resources:
                    image_map.setdefault(resolved[0],f'image{len(image_map)}')
                    etree.SubElement(sec,'{'+ns+'}image',attrib={'{http://www.w3.org/1999/xlink}href':'#'+image_map[resolved[0]]})
            else:
                value=''.join(p.itertext()).strip()
                if value:
                    etree.SubElement(sec,'{'+ns+'}p').text=value
    for href,id in image_map.items():
        r=book.resources[href]
        etree.SubElement(root,'{'+ns+'}binary',id=id,attrib={'content-type':r.media_type}).text=base64.b64encode(r.data).decode('ascii')
    Path(path).write_bytes(xml_bytes(root))
    book.warnings.append('FB2 的目录来自 section 结构；字体、行距与缩进由阅读器控制。')

def write_pdf(book,path,layout,ctx):
    from reportlab.platypus import BaseDocTemplate, PageTemplate, Frame, Paragraph, Spacer, PageBreak, Image
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.pdfbase.cidfonts import UnicodeCIDFont
    from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_CENTER
    size=layout.font_size*.75
    font_name='LumeBody'
    if book.embedded_font:
        try:
            # Some Chinese TTFs use a non-ASCII PostScript name. Repair only
            # the embedded PDF copy; glyphs and the user's original are unchanged.
            from fontTools.ttLib import TTFont as FontToolsFont
            import hashlib
            sfnt=FontToolsFont(io.BytesIO(book.embedded_font),recalcTimestamp=False)
            alias='Lume-'+hashlib.sha256(book.embedded_font).hexdigest()[:16]
            for record in sfnt['name'].names:
                if record.nameID==6:
                    record.string=alias.encode(record.getEncoding(),errors='replace')
            sfnt['name'].setName(alias,6,3,1,0x409)
            buffer=io.BytesIO()
            sfnt.save(buffer)
            sfnt.close()
            pdfmetrics.registerFont(TTFont(font_name,io.BytesIO(buffer.getvalue())))
        except Exception as exc:
            raise ConversionError('PDF 无法嵌入此字体，请使用带 TrueType 轮廓的 TTF 字体。') from exc
    else:
        pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))
        font_name='STSong-Light'
    width,height=303.36,403.2 # 1264 x 1680 at 300 dpi, in PDF points
    margin=layout.margin
    base=ParagraphStyle('Body',fontName=font_name,fontSize=size,leading=size*layout.line_height,
                        spaceAfter=size*layout.paragraph_gap,wordWrap='CJK',
                        alignment=TA_JUSTIFY if layout.alignment=='justify' else TA_LEFT,
                        allowWidows=0,allowOrphans=0,splitLongWords=True)
    heading=ParagraphStyle('Heading',parent=base,fontSize=size*1.35,leading=size*1.8,
                           spaceBefore=size,spaceAfter=size,keepWithNext=True,alignment=TA_LEFT)
    tocs=ParagraphStyle('TOC',parent=base,fontSize=size*.85,leading=size*1.3,spaceAfter=size*.35,alignment=TA_LEFT)
    class PdfDocument(BaseDocTemplate):
        def afterFlowable(self,flowable):
            marker=getattr(flowable,'lume_bookmark',None)
            if marker:
                self.canv.bookmarkPage(marker[0])
                self.canv.addOutlineEntry(marker[1],marker[0],0,False)
        def afterPage(self):
            ctx.check()
    def footer(canvas,doc):
        canvas.saveState()
        canvas.setFont(font_name,8)
        canvas.setFillGray(.45)
        canvas.drawCentredString(width/2,10,str(doc.page))
        canvas.restoreState()
    doc=PdfDocument(str(path),pagesize=(width,height),leftMargin=margin,rightMargin=margin,
                        topMargin=margin,bottomMargin=margin,title=book.title,author=book.author)
    doc.addPageTemplates(PageTemplate(id='page',frames=[Frame(margin,margin,width-2*margin,height-2*margin,
                             leftPadding=0,rightPadding=0,topPadding=0,bottomPadding=0)],onPage=footer))
    story=[Paragraph(escape(book.title),heading),Paragraph(escape(book.author),base),Spacer(1,size),Paragraph('目录',heading)]
    if book.cover_href in book.resources:
        cover_image=Image(io.BytesIO(book.resources[book.cover_href].data))
        ratio=min((width-2*margin)/cover_image.imageWidth,(height-2*margin)/cover_image.imageHeight)
        cover_image.drawWidth=cover_image.imageWidth*ratio
        cover_image.drawHeight=cover_image.imageHeight*ratio
        story[0:0]=[cover_image,PageBreak()]
    for i,ch in enumerate(book.chapters):
        story.append(Paragraph(f'<link href="#chapter-{i}">{escape(ch.title)}</link>',tocs))
    for i,ch in enumerate(book.chapters):
        if i%20==0:
            ctx.update(58+20*i/max(len(book.chapters),1),f'排版 PDF · {i+1}/{len(book.chapters)} 章')
        story.append(PageBreak())
        title=Paragraph(escape(ch.title),heading)
        title.lume_bookmark=(f'chapter-{i}',ch.title)
        story.append(title)
        root=body_root(ch.body)
        for node in root.xpath('.//p|.//h1|.//h2|.//h3|.//li|.//pre|.//img'):
            if node.tag=='img':
                resolved=resolve_href(ch.href,node.get('src',''))
                if resolved and resolved[0] in book.resources:
                    try:
                        image=Image(io.BytesIO(book.resources[resolved[0]].data))
                        ratio=min((width-2*margin)/image.imageWidth,(height-2*margin-size*3)/image.imageHeight,1)
                        image.drawWidth=image.imageWidth*ratio
                        image.drawHeight=image.imageHeight*ratio
                        story.append(image)
                    except Exception:
                        book.warnings.append('PDF 中有一张图片无法嵌入。')
                continue
            text=''.join(node.itertext()).strip()
            if not text or node.tag=='h1' and text==ch.title:
                continue
            if node.tag.startswith('h'):
                story.append(Paragraph(escape(text),heading))
            else:
                css=declarations(node.get('style',''))
                indent=css.get('text-indent',('0',False))[0]
                match=re.match(r'([+-]?[\d.]+)(em|px|pt|%)?',indent)
                first=0.
                if match:
                    amount=float(match.group(1))
                    first=amount*(size if match.group(2)=='em' else .75 if match.group(2)=='px' else 1)
                align=css.get('text-align',('',False))[0]
                style=ParagraphStyle('Paragraph',parent=base,firstLineIndent=first,
                                     alignment=TA_CENTER if align=='center' else base.alignment)
                story.append(Paragraph(escape(text).replace('\n','<br/>'),style))
    ctx.update(80,'生成 PDF 页面与书签')
    doc.build(story)
    if not book.embedded_font:
        book.warnings.append('PDF 使用内置中文宋体；选择 TTF 后会将所选字体嵌入 PDF。')
