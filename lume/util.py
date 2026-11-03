from __future__ import annotations
import mimetypes
import os
from pathlib import Path, PurePosixPath
import posixpath
import re
from urllib.parse import unquote, urlsplit
from zipfile import ZipFile
from lxml import etree, html
from .model import ConversionError

XHTML = 'http://www.w3.org/1999/xhtml'
XML = 'http://www.w3.org/XML/1998/namespace'
EPUB = 'http://www.idpf.org/2007/ops'

def xml(data):
    return etree.fromstring(data, etree.XMLParser(resolve_entities=False, no_network=True,
                            load_dtd=False, recover=False, huge_tree=False))

def body_root(content):
    return html.fragment_fromstring(content or '<p></p>', create_parent='div')

def fragment(root):
    return (root.text or '') + ''.join(etree.tostring(c, encoding='unicode', method='xml') for c in root)

def plain_text(content):
    return ''.join(body_root(content).itertext()).strip()

def inner_body(data):
    if isinstance(data, bytes):
        try:
            data = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            data = data.decode('gb18030', errors='replace')
    data = re.sub(r'^\s*<\?xml[^>]*\?>', '', data)
    root = html.document_fromstring(data)
    for bad in root.xpath('//script|//iframe|//object|//embed|//form'):
        bad.drop_tree()
    for el in root.iter():
        for attr in list(el.attrib):
            if attr.lower().startswith('on'):
                del el.attrib[attr]
    bodies = root.xpath('//body')
    return bodies[0] if bodies else root

def resolve_href(base, target):
    parsed = urlsplit(target)
    if parsed.scheme or parsed.netloc:
        return None
    path = posixpath.normpath(posixpath.join(posixpath.dirname(base), unquote(parsed.path)))
    if not parsed.path:
        path = base
    if path == '..' or path.startswith('../') or path.startswith('/') or ':' in path:
        return None
    return path, parsed.fragment

def relative_link(source, target, anchor=''):
    rel = posixpath.relpath(target, posixpath.dirname(source))
    return rel + ('#' + anchor if anchor else '')

def safe_zip(path):
    archive = ZipFile(path)
    try:
        entries = archive.infolist()
        if len(entries) > 50000 or sum(x.file_size for x in entries) > 1024 ** 3:
            raise ConversionError('压缩文件展开后过大（上限 1 GB / 50,000 项）。')
        for entry in entries:
            p = PurePosixPath(entry.filename.replace('\\', '/'))
            if p.is_absolute() or '..' in p.parts or ':' in str(p):
                raise ConversionError('电子书包含无效的资源路径。')
            if entry.file_size > 128 * 1024 ** 2:
                raise ConversionError('单个书籍资源超过 128 MB。')
        return archive
    except Exception:
        archive.close()
        raise

def safe_name(name):
    clean = re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', name).strip(' .')[:110] or 'book'
    reserved = {'CON', 'PRN', 'AUX', 'NUL'}
    reserved.update('COM' + str(i) for i in range(1, 10))
    reserved.update('LPT' + str(i) for i in range(1, 10))
    if clean.upper() in reserved:
        clean = '_' + clean
    return clean

def reserve_output(directory, name, suffix):
    """O_EXCL prevents overwriting originals and concurrent jobs."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    for number in range(10000):
        stem = safe_name(name) + (f' ({number})' if number else '')
        path = directory / (stem + '.' + suffix)
        try:
            fd = os.open(str(path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
            return path
        except FileExistsError:
            continue
    raise ConversionError('输出目录同名文件过多。')

def mime(path):
    return {'.ttf':'font/ttf', '.otf':'font/otf', '.xhtml':'application/xhtml+xml',
            '.ncx':'application/x-dtbncx+xml'}.get(Path(path).suffix.lower(),
            mimetypes.guess_type(path)[0] or 'application/octet-stream')

def format_size(size):
    return f'{size / 1024 ** 2:.1f} MB' if size >= 1024 ** 2 else f'{size / 1024:.0f} KB'
