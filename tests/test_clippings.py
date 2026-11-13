import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from lxml import etree
from lume.clippings import (Clipping,parse_clippings,merge_clippings,export_enex,export_markdown,
                           read_device,load_library,save_library)
from lume.devices import Device

SAMPLE='''山河稷（修订版） (作者甲)
- 您在第 12 页（位置 #125-127）的标注 | 添加于 2026年11月14日 星期六 08:12:00

一段中文摘抄，保留 <原文> & 符号。
第二行文字。
==========
山河稷（修订版） (作者甲)
- Your Note on page 12 | Location 128 | Added on Saturday, November 14, 2026 8:13:00 AM

A personal note.
==========
Another Book (Author (Editor))
- Your Bookmark on page 24 | Location 260 | Added on Saturday, November 14, 2026

==========
无法识别的段落
==========
'''

@pytest.mark.parametrize('encoding',['utf-8-sig','utf-16','gb18030'])
def test_parse_languages_encodings_and_metadata(encoding):
    clips,skipped=parse_clippings(SAMPLE.encode(encoding))
    assert skipped==1 and len(clips)==3
    first=clips[0]
    assert (first.title,first.author,first.kind,first.page,first.location)==('山河稷（修订版）','作者甲','highlight','12','125-127')
    assert first.text.endswith('第二行文字。')
    assert clips[1].kind=='note'
    assert clips[2].kind=='bookmark' and clips[2].author=='Author (Editor)'
    assert clips[0].book_id==clips[1].book_id!=clips[2].book_id


def test_import_merge_and_persistence(tmp_path,monkeypatch):
    import lume.storage as storage
    monkeypatch.setattr(storage,'DATA',tmp_path)
    clips,_=parse_clippings(SAMPLE)
    merged,duplicates=merge_clippings([clips[0]],clips+clips[:1])
    assert duplicates==2 and merged==clips
    save_library(merged)
    assert load_library()==clips
    assert merge_clippings(clips,clips)[0]==clips


def test_exports_preserve_content_and_make_one_note_per_book(tmp_path):
    clips,_=parse_clippings(SAMPLE)
    clips.append(Clipping('包含符号 <&>','作者','highlight','文字 ]]> < & " 测试'))
    xml=export_enex(clips,tmp_path/'摘抄.enex')
    root=etree.fromstring(xml.read_bytes(),etree.XMLParser(resolve_entities=False,no_network=True))
    assert len(root.findall('note'))==3
    texts=[]
    for note in root.findall('note'):
        enml=etree.fromstring(note.findtext('content').encode('utf-8'),etree.XMLParser(resolve_entities=False,no_network=True))
        assert enml.tag=='en-note'
        texts.append(''.join(enml.itertext()))
        assert note.findtext('created').endswith('Z')
    assert '<原文> & 符号' in texts[0]
    assert ']]> < & "' in texts[-1]
    markdown=export_markdown(clips,tmp_path/'摘抄.md').read_text(encoding='utf-8')
    assert '# 山河稷（修订版）' in markdown and '> 第二行文字。' in markdown and '位置 125-127' in markdown


def test_usb_clippings_read_is_read_only(tmp_path):
    docs=tmp_path/'documents';docs.mkdir()
    path=docs/'My Clippings.txt';original=SAMPLE.encode('utf-8-sig');path.write_bytes(original)
    assert read_device(Device('Kindle','usb',str(docs)))==original
    assert path.read_bytes()==original
    assert list(docs.iterdir())==[path]
    with pytest.raises(Exception,match='My Clippings'):
        read_device(Device('Kindle','usb',str(tmp_path)))


def test_mtp_clippings_read_uses_document_stream(monkeypatch):
    import json,types
    import lume.device_library as lib
    class Session:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def open(self,id):assert id=='kindle';return 'content'
        def documents(self,content,storage):return {},{'id':'docs'}
        def children(self,content,id):return [{'id':'clip','name':'My Clippings.txt','size':len(SAMPLE),'is_folder':False}]
    monkeypatch.setitem(sys.modules,'lume.wpd',types.SimpleNamespace(Session=Session))
    monkeypatch.setattr(lib,'_mtp_chunks',lambda *args:iter([SAMPLE.encode('utf-8')]))
    device=Device('Kindle','mtp',json.dumps({'id':'kindle','storage':'store'}))
    assert read_device(device)==SAMPLE.encode('utf-8')