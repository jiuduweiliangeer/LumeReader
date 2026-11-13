"""Render packaged Markdown with an explicit Unicode HTML path for Qt."""
from html import escape
from pathlib import Path
from markdown_it import MarkdownIt
from lxml import html
from PyQt6.QtCore import QUrl
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QTextBrowser

CSS="""
body {font-family:'Microsoft YaHei UI','Microsoft YaHei';font-size:11pt;color:#263b3b;background:white;}
h1 {font-size:22pt;color:#244e39;} h2 {font-size:16pt;color:#28775f;} h3 {font-size:13pt;}
p,li {line-height:1.55;} a {color:#28775f;} table {border-collapse:collapse;width:100%;}
td,th {border:1px solid #d7e3db;padding:7px;text-align:left;} th {background:#edf5ef;}
pre {background:#f2f6f3;padding:10px;white-space:pre-wrap;} code {color:#365b4b;}
blockquote {color:#687f73;border-left:3px solid #b7d1bf;}
"""


def markdown_html(text):
    rendered=MarkdownIt('commonmark',{'html':True}).enable('table').render(text)
    # Qt doesn't implement CSS max-width; constrain screenshots explicitly.
    tree=html.fragment_fromstring(rendered,create_parent='div')
    for image in tree.xpath('.//img'):
        width=image.get('width','')
        if not width.isdigit() or int(width)>760:
            image.set('width','760')
            image.attrib.pop('height',None)
    for table in tree.xpath('.//table'):
        table.set('width','98%')
        table.set('cellspacing','0')
        table.set('cellpadding','7')
    return '<html><head><meta charset="utf-8"/><style>'+CSS+'</style></head><body>'+html.tostring(tree,encoding='unicode')+'</body></html>'


class DocumentBrowser(QTextBrowser):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setOpenLinks(False)
        self.setOpenExternalLinks(False)
        self.document().setDocumentMargin(22)
        self.document().setDefaultFont(QFont('Microsoft YaHei UI',11))

    def display(self,path):
        path=Path(path).resolve()
        self.document().setBaseUrl(QUrl.fromLocalFile(str(path.parent)+'/'))
        text=path.read_text(encoding='utf-8-sig')
        if path.suffix.lower()=='.md':
            self.setHtml(markdown_html(text))
        else:
            self.setPlainText(text)
        self.verticalScrollBar().setValue(0)