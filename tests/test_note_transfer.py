import sys,json,threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from lume.clippings import Clipping
from lume.note_transfer import NoteTarget,transfer,obsidian_libraries,discover_targets
from lume.model import ConversionError

@pytest.fixture
def records():
    return [Clipping('山河/测试','作者','highlight','原文 < & >','12','3'),
            Clipping('另一部书','','note','一条笔记。','24')]


def test_obsidian_library_discovery_and_real_markdown_delivery(tmp_path,records):
    vault=tmp_path/'我的库';(vault/'.obsidian').mkdir(parents=True)
    roaming=tmp_path/'roaming';(roaming/'obsidian').mkdir(parents=True)
    (roaming/'obsidian/obsidian.json').write_text(json.dumps({'vaults':{'a':{'path':str(vault)},'b':{'path':str(tmp_path/'missing')}}}),encoding='utf-8')
    assert obsidian_libraries(roaming)==[str(vault)]
    existing=vault/'原有笔记.md';existing.write_text('保持不变',encoding='utf-8')
    target=NoteTarget('obsidian','Obsidian','vault',detected=True)
    result=transfer(records,target,str(vault),tmp_path/'staging',lambda x:None,threading.Event())
    assert result['state']=='written' and len(result['paths'])==2
    assert result['actions'][0][0]=='obsidian'
    first=Path(result['paths'][0]);assert vault in first.parents
    assert '原文 < & >' in first.read_text(encoding='utf-8') and '位置 12' in first.read_text(encoding='utf-8')
    again=transfer(records,target,str(vault),tmp_path/'staging',lambda x:None,threading.Event())
    assert set(again['paths']).isdisjoint(result['paths']) and first.is_file()
    assert existing.read_text(encoding='utf-8')=='保持不变'


def test_invalid_vault_is_not_silently_written(tmp_path,records):
    with pytest.raises(ConversionError,match='Obsidian'):
        transfer(records,NoteTarget('obsidian','Obsidian','vault'),str(tmp_path),tmp_path/'staging',lambda x:None,threading.Event())
    assert not list(tmp_path.iterdir())


def test_logseq_writes_pages_and_preserves_existing(tmp_path,records):
    (tmp_path/'logseq').mkdir();(tmp_path/'pages').mkdir()
    existing=tmp_path/'pages/原文.md';existing.write_text('keep',encoding='utf-8')
    result=transfer(records,NoteTarget('logseq','Logseq','vault'),str(tmp_path),tmp_path/'stage',lambda x:None,threading.Event())
    assert all(Path(p).parent==tmp_path/'pages' for p in result['paths'])
    assert existing.read_text(encoding='utf-8')=='keep'


def test_enex_receipt_does_not_claim_confirmed_import(tmp_path,records):
    target=NoteTarget('evernote','Evernote','enex',detected=True,associated=True)
    result=transfer(records,target,'',tmp_path,lambda x:None,threading.Event())
    assert result['state']=='handoff' and result['actions'][0][0]=='file'
    assert '以目标软件' in result['message'] and Path(result['paths'][0]).suffix=='.enex'
    target.associated=False
    result=transfer(records,target,'',tmp_path,lambda x:None,threading.Event())
    assert result['actions'][0][0]=='folder' and '文件 → 导入' in result['message']


def test_notion_zip_and_cancel(tmp_path,records):
    import zipfile
    result=transfer(records,NoteTarget('notion','Notion','zip'),'',tmp_path,lambda x:None,threading.Event())
    with zipfile.ZipFile(result['paths'][0]) as archive:
        assert len(archive.namelist())==2 and all(n.endswith('.md') and '/' not in n for n in archive.namelist())
    event=threading.Event();event.set()
    with pytest.raises(ConversionError,match='取消'):
        transfer(records,NoteTarget('markdown','通用','folder'),str(tmp_path),tmp_path/'s',lambda x:None,event)


def test_registry_detection_does_not_guess_installed_apps(tmp_path,monkeypatch):
    import lume.note_transfer as module
    exe=tmp_path/'Evernote.exe';exe.write_bytes(b'test fixture')
    monkeypatch.setattr(module,'_registry_apps',lambda:([('Evernote','',str(exe))],str(exe)))
    monkeypatch.setattr(module,'obsidian_libraries',lambda:[])
    targets=module.discover_targets();target=next(t for t in targets if t.id=='evernote')
    assert target.detected and target.associated and target.executable==str(exe)


def test_joplin_import_auth_then_creates_notes(records,monkeypatch):
    import lume.note_joplin as module
    calls=[]
    class Client:
        token=''
        def authorize(self,progress,cancel):self.token='session';calls.append('authorize')
        def call(self,method,path,data=None,**kwargs):
            assert self.token=='session';calls.append((method,path,data));return {'id':str(len(calls))}
    client=Client();monkeypatch.setattr(module,'find_client',lambda cancel:client)
    result=module.import_joplin(records,lambda x:None,threading.Event())
    assert calls[0]=='authorize' and calls[1][1]=='/folders'
    assert [c[1] for c in calls[2:]]==['/notes','/notes']
    assert '原文' in calls[2][2]['body'] and result['state']=='written'
    assert client.token=='' and len(result['notes'])==2


def test_joplin_uses_localhost_and_redacts_connection_errors(monkeypatch):
    from lume.note_joplin import JoplinClient
    with pytest.raises(ValueError):JoplinClient(80)
    client=JoplinClient(41184);client.token='private-session-token'
    class Broken:
        def open(self,*args,**kwargs):raise OSError('private-session-token')
    client.opener=Broken()
    with pytest.raises(ConversionError) as error:client.call('GET','/notes')
    assert 'private-session-token' not in str(error.value)
    with pytest.raises(ValueError):client.call('GET','https://remote.invalid/notes')


def test_joplin_authorization_rejection_does_not_write(monkeypatch):
    from lume.note_joplin import JoplinClient
    client=JoplinClient(41184)
    calls=[]
    def fake(method,path,**kwargs):
        calls.append(path);return {'auth_token':'temporary'} if path=='/auth' else {'status':'rejected'}
    class NoWait:
        def wait(self,seconds):return False
    client.call=fake
    with pytest.raises(ConversionError,match='拒绝'):client.authorize(lambda x:None,NoWait())
    assert calls==['/auth','/auth/check'] and not client.token
def test_joplin_real_http_auth_and_note_creation(records,monkeypatch):
    from http.server import ThreadingHTTPServer,BaseHTTPRequestHandler
    from urllib.parse import urlsplit,parse_qs
    import lume.note_joplin as module
    written=[]
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def reply(self,value):
            data=json.dumps(value).encode('utf-8');self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(data)
        def do_GET(self):
            parts=urlsplit(self.path)
            assert parts.path=='/auth/check' and parse_qs(parts.query)['auth_token']==['request-code']
            self.reply({'status':'accepted','token':'test-session-only'})
        def do_POST(self):
            parts=urlsplit(self.path);data=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))) or b'{}')
            if parts.path=='/auth':self.reply({'auth_token':'request-code'});return
            assert parse_qs(parts.query)['token']==['test-session-only']
            written.append((parts.path,data));self.reply({'id':str(len(written))})
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    client=module.JoplinClient(41184)
    client.base='http://127.0.0.1:'+str(server.server_port)
    monkeypatch.setattr(module,'find_client',lambda cancel:client)
    try:
        result=module.import_joplin(records,lambda x:None,threading.Event())
        assert result['state']=='written' and [v[0] for v in written]==['/folders','/notes','/notes']
        assert written[1][1]['parent_id']=='1' and '位置 12' in written[1][1]['body']
        assert client.token==''
    finally:server.shutdown();server.server_close();thread.join(timeout=3)