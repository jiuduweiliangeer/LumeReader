"""Joplin's built-in localhost Data API and interactive authorisation."""
import json
import time
from urllib.request import Request,build_opener,ProxyHandler,HTTPRedirectHandler
from urllib.parse import urlencode
from .model import ConversionError
from . import clippings as notes


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class JoplinClient:
    def __init__(self,port):
        if not 41184<=int(port)<=41194:raise ValueError('Invalid Joplin port')
        self.base=f'http://127.0.0.1:{int(port)}'
        self.opener=build_opener(ProxyHandler({}),NoRedirect())
        self.token=''

    def call(self,method,path,data=None,query=None,timeout=3,plain=False):
        if not path.startswith('/') or '?' in path or '://' in path:raise ValueError('Invalid API path')
        params=dict(query or {})
        if self.token:params['token']=self.token
        url=self.base+path+('?' + urlencode(params) if params else '')
        payload=json.dumps(data).encode('utf-8') if data is not None else None
        request=Request(url,data=payload,method=method,headers={'Content-Type':'application/json'})
        try:
            with self.opener.open(request,timeout=timeout) as response:
                raw=response.read(2*1024*1024)
            value=raw.decode('utf-8')
            return value if plain else json.loads(value)
        except Exception as exc:
            # Never echo URLs containing the one-session authorisation token.
            raise ConversionError('Joplin 本地连接未完成，请确认软件和 Web Clipper 服务仍在运行。') from None

    def authorize(self,progress,cancel,timeout=120):
        value=self.call('POST','/auth',data={})
        token=value.get('auth_token','')
        if not token:raise ConversionError('Joplin 没有返回授权请求。')
        progress('请在 Joplin 窗口中允许 Lume Reader 的导入请求…')
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            if cancel.wait(.7):raise ConversionError('已取消 Joplin 导入。')
            result=self.call('GET','/auth/check',query={'auth_token':token})
            if result.get('status')=='accepted' and result.get('token'):
                self.token=result['token'];return
            if result.get('status')=='rejected':raise ConversionError('Joplin 中的授权被拒绝，没有导入摘抄。')
        raise ConversionError('等待 Joplin 授权超时，请重新点击导入。')


def find_client(cancel):
    for port in range(41184,41195):
        if cancel.is_set():raise ConversionError('已取消导入。')
        client=JoplinClient(port)
        try:
            if client.call('GET','/ping',timeout=.2,plain=True).strip()=='JoplinClipperServer':return client
        except ConversionError:continue
    raise ConversionError('请先在 Joplin 的“工具 → 选项 → Web Clipper”中启用内置服务，然后重试；不需要安装浏览器插件。')


def import_joplin(records,progress,cancel):
    from datetime import datetime
    client=find_client(cancel)
    client.authorize(progress,cancel)
    books=notes.groups(records);created=[];folder=None
    try:
        if cancel.is_set():raise ConversionError('已取消导入。')
        folder=client.call('POST','/folders',{'title':'Kindle 摘抄 '+datetime.now().strftime('%Y-%m-%d %H:%M:%S')})
        parent=folder.get('id')
        if not parent:raise ConversionError('Joplin 创建笔记本失败。')
        for i,book in enumerate(books):
            if cancel.is_set():raise ConversionError('已取消后续导入。')
            progress(f'导入 Joplin {i+1} / {len(books)} · {book[0].title}')
            result=client.call('POST','/notes',{'title':book[0].title,'parent_id':parent,'body':notes.markdown_text(book),'source':'LumeReader'},timeout=15)
            if not result.get('id'):raise ConversionError('Joplin 没有确认新笔记。')
            created.append(result['id'])
    except ConversionError as exc:
        raise ConversionError(str(exc)+f' 已导入的 {len(created)} 本书会保留，请在 Joplin 查看。') from None
    finally:client.token=''
    return {'message':f'已导入 Joplin：{len(created)} 本书、{len(records)} 条摘抄。','state':'written','paths':[],
            'actions':[],'notes':created,'notebook':folder['id']}