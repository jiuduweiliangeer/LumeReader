from __future__ import annotations
from dataclasses import dataclass, field, asdict
from pathlib import Path
import re
import threading
import uuid

class ConversionError(Exception):
    pass

class Cancelled(ConversionError):
    pass

@dataclass
class Layout:
    font_size: float = 18.0
    line_height: float = 1.65
    paragraph_gap: float = 0.35
    indent: float = 2.0
    indent_mode: str = 'missing'
    alignment: str = 'justify'
    margin: float = 18.0
    font_path: str = ''
    cover_path: str = ''
    subset_font: bool = True
    encoding: str = 'auto'
    join_lines: bool = False
    chapter_pattern: str = ''

    def validate(self):
        for key, lo, hi in [('font_size',10,40), ('line_height',1,3),
                           ('paragraph_gap',0,3), ('indent',0,4), ('margin',8,50)]:
            if not lo <= float(getattr(self, key)) <= hi:
                raise ConversionError(f'排版参数 {key} 超出范围：{lo}–{hi}')
        if self.indent_mode not in ('missing', 'all', 'none'):
            raise ConversionError('无效的首行缩进方式')
        if self.alignment not in ('left', 'justify'):
            raise ConversionError('无效的对齐方式')
        if self.font_path and not Path(self.font_path).is_file():
            raise ConversionError('选中的字体文件不存在，请重新选择。')
        if self.font_path and Path(self.font_path).stat().st_size < 12:
            raise ConversionError('字体文件为空或损坏，请选择有效的 TTF/OTF 文件。')
        if self.cover_path and not Path(self.cover_path).is_file():
            raise ConversionError('封面图片不存在，请重新选择。')
        if self.chapter_pattern:
            try:
                re.compile(self.chapter_pattern)
            except re.error as exc:
                raise ConversionError(f'章节表达式无效：{exc}') from exc

    def to_dict(self):
        return asdict(self)

@dataclass
class Chapter:
    title: str
    body: str
    href: str = ''
    css: str = ''

    def __post_init__(self):
        self.title=str(self.title)
        self.href=str(self.href)

@dataclass
class Resource:
    href: str
    data: bytes
    media_type: str

@dataclass
class TocEntry:
    title: str
    href: str
    level: int = 1

    def __post_init__(self):
        self.title=str(self.title)
        self.href=str(self.href)

@dataclass
class Book:
    title: str
    author: str = '佚名'
    language: str = 'zh-CN'
    chapters: list[Chapter] = field(default_factory=list)
    resources: dict[str, Resource] = field(default_factory=dict)
    toc: list[TocEntry] = field(default_factory=list)
    uid: str = field(default_factory=lambda: 'urn:uuid:' + str(uuid.uuid4()))
    warnings: list[str] = field(default_factory=list)
    embedded_font: bytes = b''
    font_family: str = ''
    cover_href: str = ''
    device_asin: str = ''
    device_cdetype: str = 'PDOC'

    def __post_init__(self):
        # XPath smart strings inherit str but Ion requires plain Python strings.
        self.title=str(self.title)
        self.author=str(self.author)
        self.language=str(self.language)

    def add_chapter(self, title, body):
        chapter = Chapter(title, body, f'text/ch{len(self.chapters)+1:05d}.xhtml')
        self.chapters.append(chapter)
        self.toc.append(TocEntry(title, chapter.href))

@dataclass
class Result:
    source: str
    output: str
    title: str
    chapters: int
    seconds: float
    size: int
    warnings: list[str] = field(default_factory=list)

class Context:
    def __init__(self, progress=None, cancelled=None):
        self.progress = progress or (lambda percent, text: None)
        self.cancelled = cancelled or threading.Event()
        self.job_id = uuid.uuid4().hex
        self.cancel_file = None

    def check(self):
        if self.cancelled.is_set() or (self.cancel_file and self.cancel_file.exists()):
            raise Cancelled('任务已取消')

    def update(self, percent, text):
        self.check()
        self.progress(int(percent), str(text))
