from PyQt6.QtCore import Qt, QRectF, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QFont, QTextDocument, QTextCursor, QTextBlockFormat, QTextCharFormat
from PyQt6.QtWidgets import (QFrame, QWidget, QLabel, QPushButton, QVBoxLayout, QHBoxLayout,
                            QTableWidget, QAbstractItemView, QHeaderView)
from .model import Layout

def load_system_fonts():
    from pathlib import Path
    from PyQt6.QtGui import QFontDatabase
    for name in ("msyh.ttc", "msyhbd.ttc", "segoeui.ttf"):
        path = Path("C:/Windows/Fonts") / name
        if path.is_file():
            QFontDatabase.addApplicationFont(str(path))


STYLE="""
* {font-family:"Microsoft YaHei UI","Segoe UI";font-size:13px;color:#263b3b;}

QDialog,QFileDialog,QMessageBox {background:#f5f7f8;color:#263b3b;}
QMenu {background:#ffffff;color:#263b3b;border:1px solid #d7e3db;border-radius:8px;padding:6px;}
QMenu::item {padding:10px 24px;border-radius:5px;background:transparent;}
QMenu::item:selected {background:#e3f0e8;color:#24563f;}
QMenu::item:disabled {color:#a3b0a8;}
QMenu::separator {height:1px;background:#e5ece7;margin:5px 8px;}
QToolTip {background:#f5faf7;color:#263b3b;border:1px solid #c7dacd;padding:6px;}
QListView,QTreeView {background:#ffffff;color:#263b3b;alternate-background-color:#f5f8f6;selection-background-color:#e3f0e8;selection-color:#263b3b;border:1px solid #e0e8e2;}
QListView::item,QTreeView::item {min-height:27px;padding:3px;}
QListView::item:selected,QTreeView::item:selected {background:#e3f0e8;color:#263b3b;}
QComboBox QAbstractItemView {color:#263b3b;background:#ffffff;selection-background-color:#e3f0e8;selection-color:#263b3b;outline:none;}
QPushButton#Danger {background:#fff9f6;border:1px solid #e4cbc0;color:#9a5443;}
QPushButton#Danger:hover {background:#f9eae3;border-color:#c49b88;}
QPushButton#Danger:disabled {background:#f1f3f1;border-color:#e0e6e1;color:#acb7af;}

QMainWindow,QWidget#Root {background:#f5f7f8;}
QFrame#Sidebar {background:#edf2f0;border-right:1px solid #dfe8e4;}
QFrame#Card {background:white;border:1px solid #e3e9e7;border-radius:14px;}
QFrame#Drop {background:#eef6f2;border:1px dashed #a3beb0;border-radius:12px;}
QLabel {background:transparent;border:none;}
QLabel#Title {font-size:27px;font-weight:700;color:#243f38;}
QLabel#Muted {font-size:12px;color:#7c8986;}
QLabel#Section {font-size:15px;font-weight:600;}
QLabel#Badge {background:#e7f3ed;color:#397a62;border-radius:8px;padding:7px 10px;font-size:11px;}
QPushButton {background:white;border:1px solid #dbe4de;border-radius:8px;padding:9px 14px;}
QPushButton:hover {background:#eef7f2;border-color:#8cb69e;}
QPushButton:pressed {background:#deeee5;}
QPushButton:disabled {background:#edf2ef;border-color:#e6ece8;color:#a3b0a8;}
QPushButton#Primary {background:#28775f;color:white;border:none;font-weight:600;}
QPushButton#Primary:hover {background:#22634f;}
QPushButton#Primary:disabled {background:#9db9ab;}
QPushButton#Nav {text-align:left;border:none;background:transparent;padding:13px 16px;color:#6c7c74;}
QPushButton#Nav:checked {background:#dbeae1;color:#2c6249;font-weight:600;}
QPushButton#Quiet {background:transparent;border:none;color:#688073;padding:6px;}
QLineEdit,QComboBox,QDoubleSpinBox {background:#fbfcfb;border:1px solid #dfe7e1;border-radius:7px;min-height:26px;padding:5px 8px;}
QLineEdit:focus,QComboBox:focus,QDoubleSpinBox:focus {border-color:#669d7f;}
QComboBox::drop-down {border:none;width:23px;}
QComboBox QAbstractItemView {background:white;selection-background-color:#dfede4;padding:5px;}
QTableWidget {background:white;border:none;outline:none;selection-background-color:#eaf3ed;}
QTableWidget::item {border-bottom:1px solid #eff3ef;padding:9px;}
QTableWidget::item:selected {background:#eaf3ed;color:#263b3b;}
QHeaderView::section {background:#f7f9f7;color:#8b968f;border:none;padding:9px;font-size:11px;}
QProgressBar {border:none;border-radius:3px;background:#e6eee8;height:6px;}
QProgressBar::chunk {background:#529b79;border-radius:3px;}
QPlainTextEdit {background:#f7f9f7;border:1px solid #e6ece7;border-radius:8px;padding:8px;font-size:11px;color:#63776b;}
QCheckBox {spacing:7px;}
QCheckBox::indicator {width:16px;height:16px;border:1px solid #a8c1b1;border-radius:4px;background:white;}
QCheckBox::indicator:checked {background:#3b8866;border:3px solid #cee4d6;}
QTabWidget::pane {border:none;}
QTabBar::tab {padding:9px 24px;color:#8b968f;border-bottom:2px solid transparent;}
QTabBar::tab:selected {color:#286b4b;border-bottom-color:#398665;font-weight:600;}
QScrollArea {background:transparent;border:none;}
QScrollBar:vertical {background:transparent;width:7px;margin:2px;}
QScrollBar::handle:vertical {background:#d6dfd7;border-radius:3px;min-height:24px;}
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {height:0;}
QScrollBar::add-page:vertical,QScrollBar::sub-page:vertical {background:transparent;}
"""

def label(text,kind='',wrap=False):
    w=QLabel(text)
    if kind: w.setObjectName(kind)
    w.setWordWrap(wrap)
    return w

def button(text,fn,kind=''):
    w=QPushButton(text)
    if kind: w.setObjectName(kind)
    w.setCursor(Qt.CursorShape.PointingHandCursor)
    w.clicked.connect(fn)
    return w

def card():
    w=QFrame()
    w.setObjectName('Card')
    layout=QVBoxLayout(w)
    layout.setContentsMargins(20,18,20,18)
    layout.setSpacing(14)
    return w,layout


class BookTable(QTableWidget):
    checkedChanged=pyqtSignal()
    def __init__(self,*args):
        super().__init__(*args)
        self.itemChanged.connect(self._check_changed)
    def setItem(self,row,column,item):
        if column==0:
            item.setFlags(item.flags()|Qt.ItemFlag.ItemIsUserCheckable)
            if item.data(Qt.ItemDataRole.CheckStateRole) is None:
                item.setCheckState(Qt.CheckState.Unchecked)
        super().setItem(row,column,item)
    def _check_changed(self,item):
        if item.column()==0: self.checkedChanged.emit()
    def checked_rows(self):
        return [row for row in range(self.rowCount()) if not self.isRowHidden(row)
                and self.item(row,0) and self.item(row,0).checkState()==Qt.CheckState.Checked]
    def check_all(self,value=True):
        blocked=self.blockSignals(True)
        for row in range(self.rowCount()):
            if not self.isRowHidden(row) and self.item(row,0):
                self.item(row,0).setCheckState(Qt.CheckState.Checked if value else Qt.CheckState.Unchecked)
        self.blockSignals(blocked)
        if not blocked: self.checkedChanged.emit()
    def selectAll(self):
        super().selectAll()
        self.check_all(True)
    def setRowHidden(self,row,hidden):
        super().setRowHidden(row,hidden)
        if hidden and self.item(row,0):
            self.item(row,0).setCheckState(Qt.CheckState.Unchecked)

def check_all_control(widget):
    from PyQt6.QtWidgets import QCheckBox
    checkbox=QCheckBox('全选')
    def update():
        visible=[row for row in range(widget.rowCount()) if not widget.isRowHidden(row)]
        count=len(widget.checked_rows())
        checkbox.blockSignals(True)
        checkbox.setCheckState(Qt.CheckState.Unchecked if not count else
                               Qt.CheckState.Checked if count==len(visible) else Qt.CheckState.PartiallyChecked)
        checkbox.blockSignals(False)
        checkbox.setEnabled(bool(visible))
    checkbox.clicked.connect(lambda:widget.check_all(checkbox.checkState()!=Qt.CheckState.Unchecked))
    widget.checkedChanged.connect(update)
    update()
    return checkbox


def table(headers):
    w=BookTable(0,len(headers))
    w.setHorizontalHeaderLabels(headers)
    w.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    w.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
    w.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
    w.verticalHeader().hide()
    w.verticalHeader().setDefaultSectionSize(58)
    w.setShowGrid(False)
    w.horizontalHeader().setDefaultAlignment(Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter)
    w.horizontalHeader().setSectionResizeMode(0,QHeaderView.ResizeMode.Stretch)
    for i in range(1,len(headers)):
        w.horizontalHeader().setSectionResizeMode(i,QHeaderView.ResizeMode.ResizeToContents)
    return w

class DropZone(QFrame):
    files=pyqtSignal(list)
    clicked=pyqtSignal()
    def __init__(self):
        super().__init__()
        self.setObjectName('Drop')
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        row=QHBoxLayout(self)
        row.setContentsMargins(22,19,22,19)
        mark=label('＋')
        mark.setStyleSheet('font-size:31px;color:#428764;')
        row.addWidget(mark)
        text=QVBoxLayout()
        text.addWidget(label('添加书籍','Section'))
        text.addWidget(label('拖入文件或文件夹，或点击选择多个文件','Muted'))
        row.addLayout(text,1)
    def mousePressEvent(self,e):
        if e.button()==Qt.MouseButton.LeftButton: self.clicked.emit()
    def dragEnterEvent(self,e):
        if e.mimeData().hasUrls(): e.acceptProposedAction()
    def dropEvent(self,e):
        self.files.emit([u.toLocalFile() for u in e.mimeData().urls() if u.isLocalFile()])
        e.acceptProposedAction()

class ReaderPreview(QWidget):
    def __init__(self):
        super().__init__()
        self.options=Layout()
        self.family='Microsoft YaHei'
        self.title='第一章 章节标题'
        self.paragraphs=['这是正文排版预览。调整字号、行间距和段后距离，可以查看段落布局的变化。',
          '默认首行缩进两个汉字。可以选择只补齐缺失的缩进，也可以统一全部正文段落。',
          '选择字体文件后，预览使用所选字体。Kindle 上的最终显示也会受到设备阅读设置影响。']
        self.setMinimumHeight(375)
    def paintEvent(self,e):
        p=QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        width=min(self.width()-16,282)
        rect=QRectF((self.width()-width)/2,5,width,min(self.height()-12,width*1.38))
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(QColor('#293a35'))
        p.drawRoundedRect(rect,19,19)
        paper=rect.adjusted(13,17,-13,-26)
        p.setBrush(QColor('#f6f3e9'))
        p.drawRoundedRect(paper,5,5)
        p.save()
        p.setClipRect(paper.adjusted(11,12,-11,-12))
        doc=QTextDocument()
        font=QFont(self.family)
        font.setPixelSize(round(self.options.font_size*.8))
        doc.setDefaultFont(font)
        doc.setDocumentMargin(0)
        doc.setTextWidth(paper.width()-28)
        cursor=QTextCursor(doc)
        fmt=QTextBlockFormat()
        fmt.setBottomMargin(16)
        cursor.setBlockFormat(fmt)
        cf=QTextCharFormat()
        cf.setForeground(QColor('#202923'))
        cf.setFontWeight(QFont.Weight.Bold)
        cursor.insertText(self.title,cf)
        cf.setFontWeight(QFont.Weight.Normal)
        for text in self.paragraphs:
            cursor.insertBlock()
            block=QTextBlockFormat()
            block.setTextIndent(0 if self.options.indent_mode=='none' else font.pixelSize()*self.options.indent)
            block.setLineHeight(self.options.line_height*100,QTextBlockFormat.LineHeightTypes.ProportionalHeight.value)
            block.setBottomMargin(self.options.paragraph_gap*font.pixelSize())
            block.setAlignment(Qt.AlignmentFlag.AlignJustify if self.options.alignment=='justify' else Qt.AlignmentFlag.AlignLeft)
            cursor.setBlockFormat(block)
            cursor.insertText(text,cf)
        p.translate(paper.x()+14,paper.y()+18)
        doc.drawContents(p)
        p.restore()
        p.setPen(QColor('#b0beb3'))
        p.setFont(QFont('Segoe UI',8))
        p.drawText(QRectF(rect.x(),rect.bottom()-24,rect.width(),18),Qt.AlignmentFlag.AlignCenter,'KPW6  /  排版预览')

from pathlib import Path as _Path
_ICON_DIR=_Path(__file__).parent/'assets'
STYLE += """
QCheckBox::indicator:checked,QTableView::indicator:checked {background:#3b8866;border:1px solid #3b8866;border-radius:3px;image:url("%s");}
QCheckBox::indicator:indeterminate {background:#3b8866;border:1px solid #3b8866;border-radius:3px;image:url("%s");}
QTableView::indicator {width:16px;height:16px;border:1px solid #a8c1b1;border-radius:3px;background:white;}
""" % ((_ICON_DIR/'check.svg').as_posix(),(_ICON_DIR/'partial.svg').as_posix())
