import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from lume.presets import PRESETS,identify_model,recommend,page_size
from lume.devices import Device
from lume.model import Layout
from lume.engine import convert

@pytest.mark.parametrize('name,serial,expected',[
    ('Kindle Voyage','','voyage'),('Kindle','B013123456789012','voyage'),
    ('Kindle','B024123456789012','paperwhite1'),('Kindle Paperwhite 5','','paperwhite5'),
    ('Kindle Paperwhite','B013123456789012','voyage'),('Kindle Scribe','','scribe'),
    ('Kindle Keyboard','','legacy'),('Kindle DX','','mobi_only'),('Kindle','',''),
])
def test_device_identity(name,serial,expected):
    assert identify_model(name,serial)==expected


def test_recommendation_and_compiler_availability():
    assert recommend(None).format=='kfx'
    voyage=Device('Voyage','usb','docs',model='voyage')
    assert recommend(voyage,True).format=='azw3'
    assert recommend(voyage,False).format=='kfx' and recommend(voyage).kfx_mode=='legacy'
    assert recommend(Device('Paperwhite','mtp','',model='paperwhite6')).format=='kfx'
    old=Device('DX','usb','',model='mobi_only')
    assert recommend(old,True).format=='mobi' and recommend(old,False).format=='pdf'


@pytest.mark.parametrize('profile',['paperwhite6','voyage','kindle6','oasis','scribe'])
def test_pdf_profile_changes_physical_page_size(tmp_path,profile):
    import pymupdf
    source=tmp_path/'book.html'
    source.write_text('<html><head><title>Profile test</title></head><body><h1>First chapter</h1><p>Profile dimensions remain readable.</p></body></html>',encoding='utf-8')
    result=convert(source,tmp_path/'out','pdf',Layout(screen_profile=profile))
    with pymupdf.open(result.output) as doc:
        width,height=page_size(profile)
        assert abs(doc[0].rect.width-width)<.1 and abs(doc[0].rect.height-height)<.1
        assert 'Profile dimensions' in ''.join(page.get_text() for page in doc)


def test_bundled_fonts_present_and_embeddable(tmp_path):
    from lume.fonts import available_fonts
    from zipfile import ZipFile
    from fontTools.ttLib import TTFont
    import io
    fonts=list(available_fonts(tmp_path/'empty'))
    assert len(fonts)==3
    source=tmp_path/'book.fb2'
    source.write_text('<?xml version="1.0"?><FictionBook xmlns="http://www.gribuser.ru/xml/fictionbook/2.0"><description><title-info><book-title>字体验证</book-title><lang>zh</lang></title-info></description><body><section><title><p>第一章</p></title><p>阅读字体测试，中文与 English。</p></section></body></FictionBook>',encoding='utf-8')
    for title,font in fonts:
        result=convert(source,tmp_path/'out','epub',Layout(font_path=font))
        with ZipFile(result.output) as book:
            names=[name for name in book.namelist() if name.endswith(('.ttf','.otf'))]
            assert names
            with TTFont(io.BytesIO(book.read(names[0]))) as embedded:
                assert ord('中') in embedded.getBestCmap()