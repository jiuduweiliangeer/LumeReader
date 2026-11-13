
"""Validate the packaged worker with a clean PATH and a cross-format matrix."""
import os,sys,json,subprocess,time,re,contextlib,io
from pathlib import Path
root=Path(__file__).resolve().parents[1]
folder=Path(os.environ.get('LUME_VERIFY_DIR',str(root/'build-support'/'release-verification')))
folder.mkdir(parents=True,exist_ok=True)
os.environ['LUME_DATA_DIR']=str(folder/'user data')
sys.path.insert(0,str(root))
import bootstrap
from lume.model import Layout,Context
from lume.readers import read_book
from lume.util import body_root
exe=Path(os.environ.get('LUME_VERIFY_EXE',str(root/'dist'/'LumeReader'/'LumeWorker.exe')))
env=dict(os.environ)
env['PATH']=str(Path(os.environ.get('WINDIR','C:/Windows'))/'System32')
for key in ('PYTHONPATH','PYTHONHOME','CONDA_PREFIX','CONDA_DEFAULT_ENV','VIRTUAL_ENV'):
    env.pop(key,None)
font=Path(os.environ.get('LUME_TEST_FONT',str(Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts'/'simhei.ttf')))
cover=root/'lume'/'assets'/'lume.png'
records=[]
markers=['窗外的树影落在书桌上','Readingstartswithasmallpage.','河水缓缓流过旧桥','示例到这里结束']
def call(source,fmt,group):
    target=folder/group/(source.suffix.lstrip('.')+'-'+fmt)
    args=[str(exe),'--convert',str(source),'--to',fmt,'--output',str(target),'--cover',str(cover)]
    if font.is_file():args.extend(['--font',str(font)])
    begin=time.perf_counter()
    process=subprocess.run(args,env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=120,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    stdout=process.stdout.decode('utf-8','replace')
    events=[]
    for line in stdout.splitlines():
        try:events.append(json.loads(line))
        except ValueError:pass
    done=next((event['result'] for event in reversed(events) if event.get('event')=='done'),None)
    record={'group':group,'from':source.suffix.lstrip('.'),'to':fmt,'ok':False,'seconds':round(time.perf_counter()-begin,3)}
    if process.returncode!=0 or done is None:
        record['error']=next((event['message'] for event in events if event.get('event')=='error'),process.stderr.decode('utf-8','replace')[-3000:])
    else:
        try:
            output=Path(done['output'])
            with contextlib.redirect_stdout(io.StringIO()):
                book=read_book(output,Layout(),Context(),str(folder/'decode'))
            body=re.sub(r'\s+','',''.join(''.join(body_root(c.body).itertext()) for c in book.chapters))
            absent=[marker for marker in markers if marker not in body]
            assert not absent,'Missing markers: '+repr(absent)
            record.update(ok=True,chapters=len(book.chapters),toc=len(book.toc),cover=bool(book.cover_href),
                          fonts=sum(r.href.lower().endswith(('.ttf','.otf')) for r in book.resources.values()),bytes=output.stat().st_size)
        except Exception as exc:record['error']=str(exc)
    records.append(record)
    (folder/'matrix.json').write_text(json.dumps(records,ensure_ascii=False,indent=2),encoding='utf-8')
    print(group,record['from'],'->',fmt,'OK' if record['ok'] else 'FAIL '+record.get('error',''),flush=True)
    if not record['ok']:raise RuntimeError(record.get('error','Unknown failure'))
    return Path(done['output'])
check=subprocess.run([str(exe),'--self-check'],env=env,stdout=subprocess.PIPE,stderr=subprocess.PIPE,timeout=45,
                     creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
assert check.returncode==0,check.stderr.decode('utf-8','replace')
diagnostics=json.loads(check.stdout)
(folder/'self-check.json').write_text(json.dumps(diagnostics,ensure_ascii=False,indent=2),encoding='utf-8')
formats=['epub','kfx','pdf','html','fb2','txt']
if env.get('KINDLEGEN') and Path(env['KINDLEGEN']).is_file():formats+=['mobi','azw3']
sources={fmt:call(root/'examples'/'阅读示例.txt',fmt,'seed') for fmt in formats if fmt!='txt'}
for source_format,source in sources.items():
    for fmt in formats:
        if fmt!=source_format:call(source,fmt,'matrix')
print('PASS',len(records),'packaged conversions; matrix',sum(r['group']=='matrix' for r in records),flush=True)
