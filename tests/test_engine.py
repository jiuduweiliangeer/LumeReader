import sys,io,threading,os
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from lxml import etree
from zipfile import ZipFile
from lume.engine import convert
from lume.model import Layout,Context,Book,ConversionError,Cancelled
from lume.readers import read_book
from lume.typography import normalized_book,declarations
from lume.writers import write_epub
from lume.util import body_root,xml,resolve_href
from lume.kindle_formats import find_kindlegen,mobi_version
FONT=Path(os.environ.get('LUME_TEST_FONT',str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'simhei.ttf')))
TEXT='第一章 山河初见\n没有缩进的中文段落，应该保留全部字符。\n　　已经空格缩进的段落，不要重复缩进。\n\n第二章 故事继续\nEnglish words remain intact. 中文也不能缺失。\n终章\n故事完结。\n'

@pytest.fixture
def source(tmp_path):
    path=tmp_path/'排版验证.txt'
    path.write_text(TEXT,encoding='utf-8')
    return path

def read(path,folder):
    return read_book(path,Layout(),Context(),str(folder))

def validate_epub(path):
    with ZipFile(path) as z:
        assert z.namelist()[0]=='mimetype'
        assert z.getinfo('mimetype').compress_type==0
        assert z.read('mimetype')==b'application/epub+zip'
        opf=xml(z.read('OEBPS/content.opf'))
        for href in opf.xpath('//*[local-name()="manifest"]/*/@href'):
            assert 'OEBPS/'+href in z.namelist()
        nav=xml(z.read('OEBPS/nav.xhtml'))
        for href in nav.xpath('//*[local-name()="a"]/@href'):
            target='OEBPS/'+href.split('#')[0]
            assert target in z.namelist()
            if '#' in href:
                anchor=href.split('#')[1]
                assert anchor in xml(z.read(target)).xpath('//@id')
        for name in z.namelist():
            if name.endswith(('.xhtml','.opf','.ncx','.xml')):
                xml(z.read(name))

def test_native_epub_and_collision(source,tmp_path):
    source_bytes=source.read_bytes()
    one=convert(source,tmp_path/'out')
    two=convert(source,tmp_path/'out')
    assert one.output!=two.output
    assert source.read_bytes()==source_bytes
    validate_epub(one.output)
    result=read(one.output,tmp_path)
    assert len(result.chapters)==3
    assert 'English words remain intact.' in ''.join(c.body for c in result.chapters)

@pytest.mark.parametrize('encoding',['utf-8-sig','utf-16','gb18030'])
def test_encoding(tmp_path,encoding):
    source=tmp_path/'encoding.txt'
    source.write_text(TEXT,encoding=encoding)
    book=read(source,tmp_path)
    assert len(book.chapters)==3
    assert '中文段落' in book.chapters[0].body

def test_preserve_positive_indent_and_no_double_spaces(tmp_path):
    b=Book('样式测试')
    b.add_chapter('第一章','<h1>第一章</h1><p class="old">保留已有缩进。</p><p>　　不要双倍。</p><p style="text-align:center">居中题记</p>')
    b.chapters[0].css='.old {text-indent: 3em !important;}'
    normalized_book(b,Layout(),Context(),tmp_path)
    nodes=body_root(b.chapters[0].body).xpath('.//p')
    assert declarations(nodes[0].get('style'))['text-indent'][0]=='3em'
    assert declarations(nodes[1].get('style'))['text-indent'][0]=='2em'
    assert not nodes[1].text.startswith('\u3000')
    assert 'text-indent' not in declarations(nodes[2].get('style'))
    normalized_book(b,Layout(indent_mode='all',indent=1.5),Context(),tmp_path)
    assert '1.5em' in b.chapters[0].body

@pytest.mark.skipif(not FONT.is_file(),reason='Local validation font not present')
def test_font_is_embedded(source,tmp_path):
    from fontTools.ttLib import TTFont
    result=convert(source,tmp_path/'out',layout=Layout(font_path=str(FONT)))
    with ZipFile(result.output) as z:
        data=z.read('OEBPS/fonts/selected.ttf')
        f=TTFont(io.BytesIO(data))
        assert ord('中') in f.getBestCmap()
        assert len(data)<FONT.stat().st_size
        assert b'LumeEmbedded' in z.read('OEBPS/styles/reader.css')

@pytest.mark.parametrize('fmt',['html','txt','fb2','pdf','kfx','mobi','azw3'])
def test_format_roundtrip(source,tmp_path,fmt):
    if fmt in ('mobi','azw3') and not find_kindlegen():
        pytest.skip('KindleGen is optional')
    font=str(FONT) if FONT.is_file() and fmt in ('pdf','kfx','azw3','mobi') else ''
    output=convert(source,tmp_path/'out',fmt,Layout(font_path=font))
    assert Path(output.output).stat().st_size>100
    restored=read(output.output,tmp_path)
    text=''.join(''.join(body_root(ch.body).itertext()) for ch in restored.chapters)
    assert 'English words remain intact.' in text
    assert '没有缩进的中文段落' in text
    if fmt=='azw3': assert mobi_version(output.output)==8
    if fmt=='pdf':
        import pymupdf
        with pymupdf.open(output.output) as pdf:
            assert len(pdf.get_toc())==3
            assert abs(pdf[0].rect.width-303.36)<.1
            assert pdf[0].get_links()
    if fmt=='kfx':
        assert Path(output.output).read_bytes()[:4]==b'CONT'
        assert 'calibre' not in sys.modules

def test_cancellation_does_not_publish(source,tmp_path):
    stop=threading.Event()
    def callback(percent,text):
        if percent>=54: stop.set()
    with pytest.raises(Cancelled):
        convert(source,tmp_path/'out',ctx=Context(callback,stop))
    assert not list((tmp_path/'out').glob('*'))

def test_empty_font_rejected(source,tmp_path):
    font=tmp_path/'empty.ttf'
    font.write_bytes(b'')
    with pytest.raises(ConversionError,match='字体文件为空'):
        convert(source,tmp_path/'out',layout=Layout(font_path=str(font)))

def test_usb_copy_collision_and_content(source,tmp_path,monkeypatch):
    import lume.storage
    monkeypatch.setattr(lume.storage,'DATA',tmp_path/'appdata')
    from lume.devices import Device,send_file
    folder=tmp_path/'device'/'documents'
    folder.mkdir(parents=True)
    one=send_file(source,Device('test','usb',str(folder)))
    two=send_file(source,Device('test','usb',str(folder)))
    assert one!=two
    assert Path(one).read_bytes()==source.read_bytes()==Path(two).read_bytes()
    epub=tmp_path/'bad.epub'
    epub.write_bytes(b'invalid')
    with pytest.raises(ConversionError): send_file(epub,Device('test','usb',str(folder)))

def test_zip_traversal(tmp_path):
    from lume.util import safe_zip
    path=tmp_path/'traversal.epub'
    with ZipFile(path,'w') as z: z.writestr('../outside','bad')
    with pytest.raises(ConversionError): safe_zip(path)


def test_renamed_epub_rejected_for_device(tmp_path):
    from lume.devices import validate_file
    fake=tmp_path/'renamed.kfx'
    fake.write_bytes(b'PK fake ebook')
    with pytest.raises(ConversionError): validate_file(fake)


def test_pdf_mixed_text_and_image_survive(tmp_path):
    import pymupdf
    from PIL import Image
    image=io.BytesIO()
    Image.new('RGB',(40,30),'green').save(image,format='PNG')
    path=tmp_path/'mixed.pdf'
    pdf=pymupdf.open()
    page=pdf.new_page()
    page.insert_text((40,40),'Visible body text.')
    page.insert_image(pymupdf.Rect(40,65,120,125),stream=image.getvalue())
    pdf.save(path)
    pdf.close()
    book=read(path,tmp_path)
    assert 'Visible body text.' in book.chapters[0].body
    assert '<img ' in book.chapters[0].body
    assert any(r.media_type.startswith('image/') for r in book.resources.values())

@pytest.mark.skipif(not FONT.is_file(),reason='Local validation font not present')
def test_existing_epub_font_survives_kfx_without_reselection(source,tmp_path):
    first=convert(source,tmp_path/'epub','epub',Layout(font_path=str(FONT)))
    second=convert(first.output,tmp_path/'kfx','kfx')
    restored=read(second.output,tmp_path)
    with ZipFile(first.output) as z:
        expected=z.read('OEBPS/fonts/selected.ttf')
    assert any(r.data==expected for r in restored.resources.values())


@pytest.fixture
def cover(tmp_path):
    from PIL import Image
    path=tmp_path/'cover.png'
    Image.new('RGB',(180,270),(30,90,65)).save(path)
    return path

@pytest.mark.parametrize('fmt',['epub','azw3','kfx'])
def test_embedded_cover_and_kindle_identity(source,cover,tmp_path,fmt):
    if fmt=='azw3' and not find_kindlegen(): pytest.skip('KindleGen optional')
    from lume.covers import pdb_metadata,thumbnail_for
    result=convert(source,tmp_path/'out',fmt,Layout(cover_path=str(cover)))
    if fmt=='epub':
        validate_epub(result.output)
        with ZipFile(result.output) as z:
            opf=xml(z.read('OEBPS/content.opf'))
            assert opf.xpath('//*[local-name()="meta"][@name="cover"]/@content')
            assert opf.xpath('//*[local-name()="item"][@properties="cover-image"]')
        restored=read(result.output,tmp_path)
        assert len(restored.chapters)==3
        assert restored.cover_href in restored.resources
    else:
        if fmt=='azw3':
            asin,kind,image=pdb_metadata(result.output)
            assert len(asin)==32 and kind=='PDOC' and image.startswith(b'\xff\xd8')
        else:
            from kfxlib.yj_book import YJ_Book
            meta=YJ_Book(result.output).get_metadata()
            asin,kind=meta.asin,meta.cde_content_type
            assert meta.cover_image_data[1].startswith(b'\xff\xd8')
        name,data=thumbnail_for(result.output)
        assert name==f'thumbnail_{asin}_{kind}_portrait.jpg'
        assert data.startswith(b'\xff\xd8')

def test_azw3_font_size_is_relative_after_compilation(source,tmp_path):
    if not find_kindlegen(): pytest.skip('KindleGen optional')
    import re
    result=convert(source,tmp_path/'out','azw3')
    restored=read(result.output,tmp_path)
    css='\n'.join(r.data.decode('utf-8',errors='replace') for r in restored.resources.values() if r.media_type=='text/css')
    css+='\n'.join(ch.css+ch.body for ch in restored.chapters)
    assert not re.search(r'font-size\s*:\s*[0-9.]+(?:px|pt)\b',css)
    assert re.search(r'font-size\s*:\s*1em\b',css)


def test_kfx_chapter_heading_survives_as_larger_bold_text(source,tmp_path):
    import cssselect2
    from lume.typography import css_for_chapter,matcher_for,computed_style
    layout=Layout(font_path=str(FONT) if FONT.is_file() else '')
    result=convert(source,tmp_path/'out','kfx',layout)
    restored=read(result.output,tmp_path)
    chapter=restored.chapters[0]
    root=body_root(chapter.body)
    matcher=matcher_for(css_for_chapter(restored,chapter))
    heading=None
    for wrapper in cssselect2.ElementWrapper.from_html_root(root).iter_subtree():
        if wrapper.etree_element.tag=='h1':
            heading=computed_style(wrapper,matcher)
            break
    assert heading is not None
    assert heading['font-weight'] in ('bold','700')
    assert float(heading['font-size'].removesuffix('em'))>=1.5
    assert float(heading['margin-top'].removesuffix('em'))>=1
    assert float(heading['margin-bottom'].removesuffix('em'))>=.6


@pytest.mark.parametrize('input_format,output_format',[('fb2','kfx'),('html','mobi'),('html','azw3'),('epub','kfx'),('kfx','azw3')])
def test_cross_format_metadata_images_and_replaced_font(source,cover,tmp_path,input_format,output_format):
    if output_format in ('mobi','azw3') and not find_kindlegen(): pytest.skip('KindleGen optional')
    layout=Layout(font_path=str(FONT) if FONT.is_file() else '',cover_path=str(cover))
    first=convert(source,tmp_path/'first',input_format,layout)
    second=convert(first.output,tmp_path/'second',output_format,layout)
    restored=read(second.output,tmp_path/'decoded-output')
    text=''.join(''.join(body_root(ch.body).itertext()) for ch in restored.chapters)
    assert 'English words remain intact.' in text and '没有缩进的中文段落' in text
    assert restored.cover_href in restored.resources
    assert len(restored.toc)>=3
    fonts=[r for r in restored.resources.values() if 'font' in r.media_type or r.href.endswith(('.ttf','.otf'))]
    if FONT.is_file(): assert len(fonts)==1

def test_kindle_decode_workspace_does_not_reuse_other_book(tmp_path):
    if not find_kindlegen(): pytest.skip('KindleGen optional')
    paths=[]
    for index,marker in enumerate(('FIRST UNIQUE BODY','SECOND DISTINCT BODY')):
        source=tmp_path/f'book{index}.txt'
        source.write_text('第一章\n'+marker,encoding='utf-8')
        paths.append(convert(source,tmp_path/'out','mobi').output)
    first=read(paths[0],tmp_path/'shared')
    second=read(paths[1],tmp_path/'shared')
    assert 'FIRST UNIQUE BODY' in first.chapters[0].body
    assert 'SECOND DISTINCT BODY' in second.chapters[0].body
    assert 'FIRST UNIQUE BODY' not in second.chapters[0].body
