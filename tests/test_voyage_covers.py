"""Regression coverage for Voyage KFX identity and USB cover restoration."""
import io
import json
import sys
from dataclasses import asdict
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from PIL import Image
from lume.model import Layout,Context,ConversionError
from lume.engine import convert
from lume.devices import Device,send_file,digest,kfx_mode_for_device
from lume.covers import thumbnail_for
from lume.cover_sync import restore_usb_covers
from lume.device_library import refresh_books
from kfxlib.yj_book import YJ_Book


@pytest.fixture
def library(tmp_path,monkeypatch):
    import lume.storage as storage
    import lume.engine as engine
    import lume.covers as covers
    monkeypatch.setattr(storage,'DATA',tmp_path/'data')
    monkeypatch.setattr(engine,'ROOT',tmp_path/'engine')
    cache=tmp_path/'cover-cache'
    cache.mkdir()
    monkeypatch.setattr(covers,'cache_dir',lambda:cache)
    source=tmp_path/'示例.txt'
    source.write_text('第一章 开始\n这段中文用于封面测试。\n第二章 后续\nEnglish marker remains unchanged.',encoding='utf-8')
    image=tmp_path/'封面.png'
    Image.new('RGB',(400,600),(30,90,70)).save(image)
    epub=convert(source,tmp_path/'source','epub',Layout(cover_path=str(image))).output
    documents=tmp_path/'Voyage'/'documents'
    documents.mkdir(parents=True)
    return Path(epub),Device('Kindle Voyage','usb',str(documents))


@pytest.mark.parametrize('mode,kind,expected',[
    ('auto','usb','legacy'),('auto','mtp','personal'),
    ('personal','usb','personal'),('legacy','mtp','legacy')])
def test_transport_default_and_manual_override(mode,kind,expected):
    assert kfx_mode_for_device(mode,Device('Test',kind,''))==expected


@pytest.mark.parametrize('mode,expected',[('auto','PDOC'),('personal','PDOC'),('legacy','EBOK')])
def test_kfx_file_and_thumbnail_identity_match(library,tmp_path,mode,expected):
    source,device=library
    output=convert(source,tmp_path/'out','kfx',Layout(kfx_mode=mode)).output
    metadata=YJ_Book(output).get_metadata()
    assert metadata.cde_content_type==expected
    assert metadata.cover_image_data[1].startswith(b'\xff\xd8')
    name,jpeg=thumbnail_for(output)
    assert name==f'thumbnail_{metadata.asin}_{expected}_portrait.jpg'
    with Image.open(io.BytesIO(jpeg)) as im:
        assert im.format=='JPEG' and im.width<=330 and im.height<=500
    # Reopening the KFX must still preserve its content and navigable chapters.
    from lume.readers import read_book
    restored=read_book(Path(output),Layout(),Context(),str(tmp_path))
    assert len(restored.chapters)==2
    assert 'English marker remains unchanged.' in ''.join(c.body for c in restored.chapters)
    assert restored.cover_href in restored.resources


def test_worker_automatically_builds_voyage_book(library,tmp_path,monkeypatch,capsys):
    import run
    source,device=library
    request=tmp_path/('c'*32+'.json')
    request.write_text(json.dumps({'source':str(source),'output_dir':str(tmp_path/'out'),
        'format':'kfx','layout':{'kfx_mode':'auto'},'send_to':asdict(device)}),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['run.py','--worker',str(request)])
    assert run.main()==0
    events=[json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    result=next(e['result'] for e in events if e['event']=='done')
    assert not result.get('send_error')
    assert YJ_Book(result['output']).get_metadata().cde_content_type=='EBOK'
    assert digest(result['device_path'])==digest(result['output'])
    name,jpeg=thumbnail_for(result['output'])
    assert (Path(device.path).parent/'system'/'thumbnails'/name).read_bytes()==jpeg


def test_direct_send_keeps_personal_document_bytes(library,tmp_path):
    source,device=library
    output=Path(convert(source,tmp_path/'out','kfx',Layout(kfx_mode='personal')).output)
    original=output.read_bytes()
    target=Path(send_file(output,device))
    assert target.read_bytes()==original==output.read_bytes()
    assert YJ_Book(str(target)).get_metadata().cde_content_type=='PDOC'


@pytest.mark.parametrize('missing',[True,False])
def test_reconnect_restores_missing_or_overwritten_cover(library,tmp_path,missing):
    source,device=library
    output=convert(source,tmp_path/'out','kfx',Layout(kfx_mode='legacy')).output
    target=Path(send_file(output,device))
    name,jpeg=thumbnail_for(output)
    thumb=Path(device.path).parent/'system'/'thumbnails'/name
    other=thumb.with_name('unrelated-cover.jpg')
    other.write_bytes(b'keep this unrelated cover')
    assert restore_usb_covers(device)=={'restored':0,'errors':[]}
    if missing: thumb.unlink()
    else: thumb.write_bytes(b'generic cover downloaded by device')
    snapshot=refresh_books(device)
    assert snapshot['covers']=={'restored':1,'errors':[]}
    assert thumb.read_bytes()==jpeg
    assert digest(target)==digest(output)
    assert other.read_bytes()==b'keep this unrelated cover'
    mtime=thumb.stat().st_mtime_ns
    assert refresh_books(device)['covers']['restored']==0
    assert thumb.stat().st_mtime_ns==mtime


def test_removed_books_do_not_restore_old_covers(library,tmp_path):
    source,device=library
    output=convert(source,tmp_path/'out','kfx',Layout(kfx_mode='legacy')).output
    first=Path(send_file(output,device))
    second=Path(send_file(output,device))
    name,jpeg=thumbnail_for(output)
    thumb=Path(device.path).parent/'system'/'thumbnails'/name
    second.unlink()
    thumb.unlink()
    assert restore_usb_covers(device)['restored']==1  # The first copy still exists.
    first.unlink()
    thumb.unlink()
    assert restore_usb_covers(device)['restored']==0
    assert not thumb.exists()


def test_changed_book_or_unsafe_cache_path_is_not_restored(library,tmp_path):
    source,device=library
    output=convert(source,tmp_path/'out','kfx',Layout(kfx_mode='legacy')).output
    target=Path(send_file(output,device))
    name,jpeg=thumbnail_for(output)
    root=Path(device.path).parent
    thumb=root/'system'/'thumbnails'/name
    thumb.unlink()
    target.write_bytes(b'a different book')
    assert restore_usb_covers(device)['restored']==0
    record=root/'system'/'lume-cover-cache'/(name+'.json')
    saved=json.loads(record.read_text(encoding='utf-8'))
    saved['books'][0]['path']='../outside.kfx'
    record.write_text(json.dumps(saved),encoding='utf-8')
    assert restore_usb_covers(device)['restored']==0
    assert not thumb.exists()


def test_mtp_refresh_does_not_access_usb_cache():
    assert restore_usb_covers(Device('Paperwhite','mtp','not-a-filesystem-path'))=={'restored':0,'errors':[]}


def test_invalid_kfx_mode_is_rejected():
    with pytest.raises(ConversionError):
        Layout(kfx_mode='typo').validate()

def test_existing_pdoc_kfx_can_be_reconverted_for_voyage(library,tmp_path):
    source,device=library
    old=Path(convert(source,tmp_path/'old','kfx',Layout()).output)
    old_bytes=old.read_bytes()
    new=convert(old,tmp_path/'new','kfx',Layout(kfx_mode='legacy')).output
    metadata=YJ_Book(new).get_metadata()
    assert metadata.cde_content_type=='EBOK'
    assert metadata.cover_image_data[1].startswith(b'\xff\xd8')
    target=send_file(new,device)
    assert digest(new)==digest(target)
    assert old.read_bytes()==old_bytes
