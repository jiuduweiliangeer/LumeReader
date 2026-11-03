import json
from dataclasses import asdict
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from lume.devices import Device,digest
from lume.device_library import DeviceBook,list_books,export_books,remove_books
from lume.model import ConversionError

def test_usb_library_backup_delete_preserves_other_files(tmp_path):
    root=tmp_path/'Kindle'/'documents'
    (root/'小说').mkdir(parents=True)
    (root/'小说'/'阅读记录.sdr').mkdir()
    (root/'小说'/'阅读记录.sdr'/'keep.txt').write_text('批注',encoding='utf-8')
    (root/'My Clippings.txt').write_text('摘录',encoding='utf-8')
    (root/'小说'/'一.txt').write_text('第一本书',encoding='utf-8')
    (root/'二.txt').write_text('第二本书',encoding='utf-8')
    (root/'ignored.bin').write_bytes(b'private')
    device=Device('Test','usb',str(root))
    books=list_books(device)['books']
    assert {b.name for b in books}=={'一.txt','二.txt'}
    saved=export_books(device,books,tmp_path/'export')
    assert len(saved)==2 and all(digest(r['output'])==r['sha256'] for r in saved)
    receipt=remove_books(device,books,tmp_path/'backup')
    assert len(receipt['removed'])==2
    assert all(Path(r['output']).is_file() for r in receipt['files'])
    assert not list_books(device)['books']
    assert (root/'小说'/'阅读记录.sdr'/'keep.txt').read_text(encoding='utf-8')=='批注'
    assert (root/'My Clippings.txt').exists()
    assert (root/'ignored.bin').read_bytes()==b'private'
    assert json.loads((tmp_path/'backup'/'backup.json').read_text(encoding='utf-8'))['removed']==receipt['removed']

def test_device_manager_rejects_paths_outside_documents(tmp_path):
    root=tmp_path/'documents'
    root.mkdir()
    outside=tmp_path/'original.txt'
    outside.write_text('must keep',encoding='utf-8')
    book=DeviceBook('x',outside.name,'../original.txt',outside.stat().st_size)
    with pytest.raises(ConversionError):
        remove_books(Device('Test','usb',str(root)),[book],tmp_path/'backup')
    assert outside.read_text(encoding='utf-8')=='must keep'

def test_changed_book_is_not_deleted(tmp_path):
    root=tmp_path/'documents'
    root.mkdir()
    source=root/'书.txt'
    source.write_text('old',encoding='utf-8')
    device=Device('Test','usb',str(root))
    book=list_books(device)['books'][0]
    source.write_text('new contents',encoding='utf-8')
    with pytest.raises(ConversionError):
        remove_books(device,[book],tmp_path/'backup')
    assert source.read_text(encoding='utf-8')=='new contents'

@pytest.mark.parametrize('connected',[True,False])
def test_worker_convert_and_send_retains_local_output(tmp_path,monkeypatch,capsys,connected):
    import run
    import lume.storage as storage
    monkeypatch.setattr(storage,'DATA',tmp_path/'data')
    source=tmp_path/'输入.txt'
    source.write_text('第一章 开始\n这是一段中文正文。\n第二章 继续\n这是第二段正文。',encoding='utf-8')
    target=tmp_path/'device'/'documents'
    if connected: target.mkdir(parents=True)
    job={'source':str(source),'format':'txt','output_dir':str(tmp_path/'out'),
         'send_to':asdict(Device('Test','usb',str(target)))}
    request=tmp_path/('a'*32+'.json')
    request.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['run.py','--worker',str(request)])
    assert run.main()==0
    events=[json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    converted=next(e['result'] for e in events if e['event']=='converted')
    result=next(e['result'] for e in events if e['event']=='done')
    assert Path(converted['output']).is_file()
    if connected:
        assert digest(result['device_path'])==digest(result['output'])
        assert not result.get('send_error')
    else:
        assert result.get('send_error') and not result.get('device_path')
        assert Path(result['output']).is_file()


def test_direct_send_bypasses_converter_and_invalid_layout(tmp_path,monkeypatch,capsys):
    import run
    import lume.engine as engine
    import lume.storage as storage
    monkeypatch.setattr(storage,'DATA',tmp_path/'data')
    def forbidden_conversion(*args,**kwargs):
        raise AssertionError('Direct send must never call a converter')
    monkeypatch.setattr(engine,'convert',forbidden_conversion)
    source=tmp_path/'原文件.txt'
    raw=b'\xff\xfe'+('保持原始编码与内容。\r\n第二行。\r\n').encode('utf-16le')
    source.write_bytes(raw)
    target=tmp_path/'documents'
    target.mkdir()
    job={'source':str(source),'operation':'send','send_to':asdict(Device('Test','usb',str(target))),
         'layout':{'font_path':str(tmp_path/'missing.ttf')}}
    request=tmp_path/('b'*32+'.json')
    request.write_text(json.dumps(job,ensure_ascii=False),encoding='utf-8')
    monkeypatch.setattr(sys,'argv',['run.py','--worker',str(request)])
    assert run.main()==0
    events=[json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith('{')]
    result=next(e['result'] for e in events if e['event']=='done')
    assert result['operation']=='send'
    assert Path(result['device_path']).read_bytes()==raw
    assert source.read_bytes()==raw
    assert not any(e['event']=='converted' for e in events)


def test_history_removal_backs_up_outputs_and_keeps_imported_originals(tmp_path):
    from lume.local_history import trash_outputs
    source=tmp_path/'source.txt'
    source.write_bytes(b'original bytes')
    output=tmp_path/'converted.txt'
    output.write_bytes(b'converted bytes')
    records=[{'source':str(source),'output':str(output),'size':output.stat().st_size},
             {'source':str(source),'output':str(source),'size':source.stat().st_size,'operation':'send'}]
    receipt=trash_outputs(records,tmp_path/'trash')
    assert not receipt['errors']
    assert len(receipt['moved'])==1 and receipt['moved'][0]['removed']
    assert Path(receipt['moved'][0]['backup']).read_bytes()==b'converted bytes'
    assert source.read_bytes()==b'original bytes'
    assert not output.exists()
