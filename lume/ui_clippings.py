"""Book-grouped clippings view with offline ENEX and Markdown export."""
from html import escape
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLineEdit,QListWidget,QListWidgetItem,
                            QComboBox,QSplitter,QMessageBox,QMenu)
from .ui_parts import label,button,card
from .ui_theme import FileDialogs
from .help_view import DocumentBrowser
from . import clippings as notes


class ClippingsPanel(QWidget):
    def __init__(self,owner):
        super().__init__()
        self.owner=owner
        self.records=notes.load_library()
        self.locked=False
        self.current_book=''
        self.page_index=0
        box=QVBoxLayout(self)
        box.setContentsMargins(24,22,24,20)
        box.setSpacing(14)
        box.addWidget(label('摘抄','Title'))
        box.addWidget(label('按书籍整理 My Clippings 中的划线、笔记与书签','Muted'))
        panel,header=card()
        row=QHBoxLayout()
        self.device_import=button('从 Kindle 读取',self.import_device,'Primary')
        row.addWidget(self.device_import)
        self.local_import=button('导入 My Clippings.txt…',self.import_local)
        row.addWidget(self.local_import)
        row.addStretch()
        self.total=label('','Badge')
        row.addWidget(self.total)
        header.addLayout(row)
        box.addWidget(panel)
        split=QSplitter(Qt.Orientation.Horizontal)
        self.splitter=split
        left=QWidget();left.setMinimumWidth(160);left.setMaximumWidth(240);leftbox=QVBoxLayout(left);leftbox.setContentsMargins(0,0,12,0)
        self.search=QLineEdit()
        self.search.setPlaceholderText('搜索书籍或摘抄…')
        self.search.setClearButtonEnabled(True)
        leftbox.addWidget(self.search)
        self.books=QListWidget()
        self.books.setWordWrap(False)
        self.books.setTextElideMode(Qt.TextElideMode.ElideRight)
        self.books.setSpacing(3)
        self.books.setStyleSheet('QListWidget {border-radius:10px;} QListWidget::item {padding:11px 8px;border-radius:7px;}')
        leftbox.addWidget(self.books,1)
        split.addWidget(left)
        right=QWidget();rightbox=QVBoxLayout(right);rightbox.setContentsMargins(0,0,0,0)
        heading=QHBoxLayout()
        self.book_title=label('选择一本书','Section',True)
        self.book_title.setStyleSheet('font-size:20px;font-weight:600;color:#2e6148;')
        heading.addWidget(self.book_title,1)
        self.kind=QComboBox()
        for text,value in [('全部摘抄',''),('划线','highlight'),('笔记','note'),('书签','bookmark')]:self.kind.addItem(text,value)
        heading.addWidget(self.kind)
        rightbox.addLayout(heading)
        self.reader=DocumentBrowser()
        self.reader.setStyleSheet('QTextBrowser {background:white;border:1px solid #dce6df;border-radius:10px;}')
        rightbox.addWidget(self.reader,1)
        pager=QHBoxLayout()
        self.page_label=label('','Muted')
        pager.addWidget(self.page_label,1)
        self.prev_page=button('上一页',lambda:self.change_page(-1),'Quiet')
        self.next_page=button('下一页',lambda:self.change_page(1),'Quiet')
        pager.addWidget(self.prev_page);pager.addWidget(self.next_page)
        rightbox.addLayout(pager)
        split.addWidget(right);split.setSizes([200,1100]);split.setStretchFactor(0,0);split.setStretchFactor(1,1);split.setChildrenCollapsible(False)
        box.addWidget(split,1)
        footer=QHBoxLayout()
        footer.addStretch()
        self.scope=QComboBox()
        self.scope.setEditable(True)
        self.scope.lineEdit().setReadOnly(True)
        self.scope.lineEdit().setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.scope.lineEdit().setStyleSheet('border:none;background:transparent;padding:0;')
        self.scope.setFixedWidth(164)
        self.scope.addItem('当前书籍',False);self.scope.addItem('全部书籍',True)
        for i in range(self.scope.count()):self.scope.setItemData(i,Qt.AlignmentFlag.AlignCenter,Qt.ItemDataRole.TextAlignmentRole)
        footer.addWidget(self.scope)
        self.transfer=button('导入笔记软件…',self.transfer_notes,'Primary')
        self.save_file=button('保存为文件',lambda:None)
        menu=QMenu(self.save_file)
        menu.addAction('Markdown · 通用文本',lambda:self.export('md'))
        menu.addAction('ENEX · 兼容笔记软件',lambda:self.export('enex'))
        self.save_file.setMenu(menu)
        footer.addWidget(self.transfer);footer.addWidget(self.save_file);footer.addStretch()
        rightbox.addLayout(footer)
        self.status=label('选择笔记软件后自动匹配格式，或将摘抄保存为文件。','Muted',True)
        box.addWidget(self.status)
        self.search.textChanged.connect(self.refresh)
        self.kind.currentIndexChanged.connect(self.display)
        self.books.currentItemChanged.connect(self.select_book)
        self.refresh()

    def refresh(self):
        query=self.search.text().strip().casefold()
        grouped=notes.groups(self.records)
        self.books.blockSignals(True);self.books.clear()
        selected=None
        for book in grouped:
            if query and not any(query in (c.title+' '+c.author+' '+c.text).casefold() for c in book):continue
            first=book[0]
            item=QListWidgetItem(first.title)
            item.setToolTip(first.title+(' · '+first.author if first.author else '')+f'\n{len(book)} 条摘抄')
            item.setData(Qt.ItemDataRole.UserRole,first.book_id)
            self.books.addItem(item)
            if first.book_id==self.current_book:selected=item
        self.books.blockSignals(False)
        self.total.setText(f'{len(grouped)} 本书 · {len(self.records)} 条摘抄')
        if self.books.count():self.books.setCurrentItem(selected or self.books.item(0))
        else:self.current_book='';self.display()
        self.update_actions()

    def select_book(self,*args):
        item=self.books.currentItem()
        self.current_book=item.data(Qt.ItemDataRole.UserRole) if item else ''
        self.display()

    def change_page(self,delta):
        self.page_index=max(0,self.page_index+delta)
        self.display(reset=False)

    def display(self,*args,reset=True):
        if reset:self.page_index=0
        selected=[c for c in self.records if c.book_id==self.current_book]
        if not selected:
            self.prev_page.setEnabled(False);self.next_page.setEnabled(False);self.page_label.clear()
            self.book_title.setText('摘抄库')
            message='没有匹配的摘抄，请修改搜索词。' if self.records else '连接 Kindle 后点击“从 Kindle 读取”，或导入 My Clippings.txt。'
            self.reader.setHtml('<html><body style="color:#66796e;"><h2>按书籍查看阅读记录</h2><p>'+message+'</p></body></html>')
            return
        first=selected[0];self.book_title.setText(first.title)
        query=self.search.text().strip().casefold();kind=self.kind.currentData()
        visible=[c for c in selected if (not kind or c.kind==kind) and
                 (not query or query in (c.title+' '+c.author+' '+c.text).casefold())]
        count=len(visible);pages=max(1,(count+99)//100)
        self.page_index=min(self.page_index,pages-1)
        self.prev_page.setEnabled(self.page_index>0);self.next_page.setEnabled(self.page_index+1<pages)
        self.page_label.setText(f'第 {self.page_index+1} / {pages} 页 · 共 {count} 条')
        visible=visible[self.page_index*100:(self.page_index+1)*100]
        title=''
        author='<p style="color:#6d7c73;">'+(escape(first.author)+' · ' if first.author else '')+f'{count} 条摘抄</p>'
        self.reader.setHtml('<html><body style="font-family:Microsoft YaHei UI;font-size:12pt;color:#263b3b;">'+title+author+
                            (notes.notes_html(visible,True) or '<p>没有符合当前筛选条件的摘抄。</p>')+'</body></html>')

    def update_actions(self):
        ready=not self.locked
        owner=self.owner
        self.device_import.setEnabled(ready and bool(owner.current_device()) and not owner._device_busy and not owner._batch_busy and not owner._scanning)
        self.local_import.setEnabled(ready)
        self.transfer.setEnabled(ready and bool(self.records));self.save_file.setEnabled(ready and bool(self.records))

    def import_local(self):
        path,_=FileDialogs.getOpenFileName(self,'导入 Kindle 摘抄','','Kindle 摘抄 (*.txt)')
        if path:self.import_data(lambda:notes.read_file(path),'本地文件')

    def import_device(self):
        device=self.owner.current_device()
        if device and self.device_import.isEnabled():self.import_data(lambda:notes.read_device(device),device.name,True)

    def import_data(self,reader,source,device=False):
        if self.locked:return
        self.locked=True
        if device:self.owner._device_busy=True
        self.owner.update_actions();self.update_actions()
        self.status.setText('正在读取并整理摘抄…')
        existing=list(self.records)
        def work(progress):
            incoming,skipped=notes.parse_clippings(reader())
            if not incoming:raise ValueError('没有识别到有效摘抄，请选择 Kindle 的 My Clippings.txt。')
            merged,duplicates=notes.merge_clippings(existing,incoming)
            notes.save_library(merged)
            return merged,len(merged)-len(existing),duplicates,skipped
        def release():
            self.locked=False
            if device:self.owner._device_busy=False
            self.owner.update_actions();self.update_actions()
        def done(result):
            self.records,added,duplicates,skipped=result
            release();self.refresh()
            self.status.setText(f'{source}：新增 {added} 条 · 已存在 {duplicates} 条'+(f' · 未识别 {skipped} 段' if skipped else '')+'。原始文件未修改。')
        def failed(error):
            release();self.status.setText('导入未完成：'+error)
            QMessageBox.warning(self,'摘抄导入未完成',error)
        self.owner.task(work,done,failed)

    def transfer_notes(self):
        selected=list(self.records) if self.scope.currentData() else [c for c in self.records if c.book_id==self.current_book]
        if not selected:return
        from .ui_note_transfer import NoteTransferDialog
        dialog=NoteTransferDialog(self.owner,selected)
        dialog.exec()
        if dialog.receipt:self.status.setText(dialog.receipt)

    def export(self,fmt):
        selected=list(self.records) if self.scope.currentData() else [c for c in self.records if c.book_id==self.current_book]
        if not selected:return
        title='Kindle 摘抄' if self.scope.currentData() else selected[0].title
        import re
        title=re.sub(r'[<>:"/\\|?*\x00-\x1f]','_',title).strip(' .')[:100] or 'Kindle 摘抄'
        path,_=FileDialogs.getSaveFileName(self,'导出摘抄',title+'.'+fmt,'ENEX 笔记文件 (*.enex)' if fmt=='enex' else 'Markdown (*.md)')
        if not path:return
        if not Path(path).suffix:path+='.'+fmt
        try:
            (notes.export_enex if fmt=='enex' else notes.export_markdown)(selected,path)
            self.status.setText(f'已导出 {len(selected)} 条摘抄：{path}')
            self.status.setToolTip(path)
        except Exception as exc:QMessageBox.warning(self,'导出未完成',str(exc))