"""An explicit, transactional cover choice for every book in a batch."""
from pathlib import Path
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QLabel,QMessageBox,QListWidget
from .ui_parts import button,label
from .ui_theme import FileDialogs


class CoverWizard(QDialog):
    def __init__(self,books,choices=None,parent=None):
        super().__init__(parent)
        self.books=list(books)
        self.choices={p:(choices or {})[p] for p in self.books if p in (choices or {})}
        self.setWindowTitle('逐本设置封面')
        self.resize(800,620)
        self.setMinimumSize(680,540)
        box=QVBoxLayout(self)
        box.setContentsMargins(24,22,24,22)
        box.addWidget(label('逐本设置封面','Title'))
        box.addWidget(label('选择图片，或保留原书封面。完成后一次应用到本批书籍。','Muted',True))
        content=QHBoxLayout()
        self.list=QListWidget()
        self.list.setMaximumWidth(265)
        self.list.addItems([Path(p).stem for p in self.books])
        content.addWidget(self.list,1)
        right=QVBoxLayout()
        self.heading=label('','Section',True)
        right.addWidget(self.heading)
        self.preview=QLabel()
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumHeight(280)
        self.preview.setStyleSheet('background:#edf3ef;border:1px dashed #bfd0c4;border-radius:10px;color:#536c5e;')
        right.addWidget(self.preview,1)
        self.path_label=label('','Muted',True)
        right.addWidget(self.path_label)
        right.addWidget(button('选择封面图片…',self.choose,'Primary'))
        right.addWidget(button('保留原书封面',self.keep))
        content.addLayout(right,2)
        box.addLayout(content,1)
        footer=QHBoxLayout()
        self.progress=label('','Muted')
        footer.addWidget(self.progress,1)
        footer.addWidget(button('取消',self.reject,'Quiet'))
        self.previous=button('上一本',lambda:self.move(-1))
        footer.addWidget(self.previous)
        self.next=button('下一本',lambda:self.move(1))
        footer.addWidget(self.next)
        self.finish=button('完成',self.complete,'Primary')
        footer.addWidget(self.finish)
        box.addLayout(footer)
        self.list.currentRowChanged.connect(self.display)
        if self.books:self.list.setCurrentRow(0)

    def display(self,row):
        if not 0<=row<len(self.books):return
        path=self.books[row]
        self.heading.setText(Path(path).stem)
        self.heading.setToolTip(path)
        self.preview.clear()
        image=self.choices.get(path,'')
        pixmap=QPixmap(image) if image else QPixmap()
        if not pixmap.isNull():
            self.preview.setPixmap(pixmap.scaled(270,320,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
        else:self.preview.setText('保留原书封面' if path in self.choices else '尚未选择')
        self.path_label.setText(Path(image).name if image else '保留书中已有的封面；无封面的书籍不添加图片。')
        self.path_label.setToolTip(image)
        self.previous.setEnabled(row>0)
        self.next.setEnabled(row<len(self.books)-1)
        self.progress.setText(f'第 {row+1} / {len(self.books)} 本 · 已确认 {len(self.choices)} 本')
        for i,p in enumerate(self.books):
            self.list.item(i).setText(('✓ ' if p in self.choices else '○ ')+Path(p).stem)

    def choose(self):
        path,_=FileDialogs.getOpenFileName(self,'选择这本书的封面','','图片 (*.jpg *.jpeg *.png *.webp *.bmp)')
        if path:
            if QPixmap(path).isNull():
                QMessageBox.warning(self,'无法读取图片','请选择有效的封面图片。')
                return
            self.choices[self.books[self.list.currentRow()]]=path
            self.display(self.list.currentRow())

    def keep(self):
        self.choices[self.books[self.list.currentRow()]]=''
        self.display(self.list.currentRow())

    def move(self,delta):
        row=self.list.currentRow()
        if delta>0 and self.books[row] not in self.choices:self.choices[self.books[row]]=''
        self.list.setCurrentRow(row+delta)

    def complete(self):
        row=self.list.currentRow()
        if row>=0 and self.books[row] not in self.choices:self.choices[self.books[row]]=''
        missing=next((i for i,p in enumerate(self.books) if p not in self.choices),None)
        if missing is not None:
            self.list.setCurrentRow(missing)
            self.progress.setText('请确认这本书的封面，或点击“保留原书封面”。')
            return
        for path in self.choices.values():
            if path and QPixmap(path).isNull():
                QMessageBox.warning(self,'封面已变化','有封面图片已删除或无法读取，请重新选择。')
                return
        self.accept()