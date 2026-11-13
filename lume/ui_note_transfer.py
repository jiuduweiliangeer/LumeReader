"""Choose a detected note app; adapt the format and report actual delivery."""
from pathlib import Path
import subprocess
import threading
from PyQt6.QtCore import Qt,QUrl
from PyQt6.QtGui import QDesktopServices
from PyQt6.QtWidgets import QDialog,QVBoxLayout,QHBoxLayout,QComboBox,QCheckBox,QMessageBox
from .ui_parts import label,button,card
from .ui_theme import FileDialogs
from .storage import ROOT
from .note_transfer import discover_targets,transfer
from . import clippings as notes


class NoteTransferDialog(QDialog):
    def __init__(self,owner,records):
        super().__init__(owner)
        self.owner=owner;self.records=records;self.receipt=''
        self.running=False;self._closed=False;self.cancel_event=threading.Event()
        self.setWindowTitle('导入笔记软件');self.resize(640,450);self.setMinimumWidth(580)
        box=QVBoxLayout(self);box.setContentsMargins(26,22,26,22);box.setSpacing(14)
        box.addWidget(label('导入笔记软件','Title'))
        box.addWidget(label(f'{len(notes.groups(records))} 本书 · {len(records)} 条摘抄','Muted'))
        panel,body=card()
        header=QHBoxLayout();header.addWidget(label('目标软件','Section'),1)
        self.refresh=button('重新检测',self.detect,'Quiet');header.addWidget(self.refresh);body.addLayout(header)
        self.targets=QComboBox();body.addWidget(self.targets)
        self.detection=label('正在检测本机笔记软件…','Muted',True);body.addWidget(self.detection)
        self.destination_label=label('笔记库目录','Section');body.addWidget(self.destination_label)
        row=QHBoxLayout();self.destination=QComboBox();self.destination.setEditable(True);row.addWidget(self.destination,1)
        self.browse=button('选择目录',self.choose_directory);row.addWidget(self.browse);body.addLayout(row)
        self.method=label('','Muted',True);body.addWidget(self.method)
        box.addWidget(panel,1)
        self.open_target=QCheckBox('完成后打开目标软件或文件夹');self.open_target.setChecked(True);box.addWidget(self.open_target)
        self.progress=label('','Muted',True);box.addWidget(self.progress)
        footer=QHBoxLayout();footer.addStretch()
        self.cancel_button=button('取消',self.reject,'Quiet');footer.addWidget(self.cancel_button)
        self.start_button=button('开始导入',self.start,'Primary');self.start_button.setEnabled(False);footer.addWidget(self.start_button)
        box.addLayout(footer)
        self.targets.currentIndexChanged.connect(self.target_changed)
        self.detect()

    def detect(self):
        if self.running:return
        self.refresh.setEnabled(False);self.start_button.setEnabled(False)
        self.detection.setText('正在检测本机笔记软件…')
        previous=getattr(self.targets.currentData(),'id','')
        def done(targets):
            if self._closed:return
            self.targets.blockSignals(True);self.targets.clear()
            for target in targets:
                suffix=' · 已检测到' if target.detected else ' · 指定目录' if target.kind=='vault' else ''
                self.targets.addItem(target.name+suffix,target)
            selected=next((i for i,t in enumerate(targets) if t.id==previous),0)
            self.targets.setCurrentIndex(selected);self.targets.blockSignals(False)
            found=[t.name for t in targets if t.detected]
            self.detection.setText('检测到：'+'、'.join(found) if found else '未检测到支持的笔记软件。可手动指定笔记库目录，或保存为通用文件。')
            self.refresh.setEnabled(True);self.start_button.setEnabled(True);self.target_changed()
        def failed(message):
            if self._closed:return
            self.refresh.setEnabled(True);self.detection.setText('检测未完成：'+message)
        self.owner.task(lambda progress:discover_targets(),done,failed)

    def target_changed(self,*args):
        target=self.targets.currentData()
        if target is None:return
        needs_folder=target.kind in ('vault','folder')
        for w in (self.destination_label,self.destination,self.browse):w.setVisible(needs_folder)
        self.destination.clear();self.destination.addItems(target.libraries)
        previous=self.owner.config.get('note_destinations',{}).get(target.id,'')
        if previous:self.destination.setCurrentText(previous)
        self.destination.lineEdit().setPlaceholderText('选择目标笔记库的根目录' if target.kind=='vault' else '选择保存目录')
        descriptions={
            'obsidian':'自动转为 Markdown，每本书一篇，写入所选 Obsidian 笔记库。保留已有笔记，导入后可直接在 Obsidian 中阅读。',
            'logseq':'自动转为 Markdown，每本书一页，写入现有文件图谱的 pages 目录。仅支持文件图谱。',
            'joplin':'通过 Joplin 内置本地服务创建笔记本并导入。首次使用需启用 Web Clipper，并在 Joplin 中允许本次请求；无需浏览器插件。',
            'markdown':'自动生成每本书的 Markdown 文件，保存到所选目录，供支持 Markdown 的笔记软件读取。',
            'notion':'自动打包为 Markdown ZIP 并打开软件及文件夹。在 Notion 的“导入”中选择生成文件。',
        }
        description=descriptions.get(target.id,'自动转为 ENEX。'+('随后调用系统文件关联，交给 '+target.name+' 导入，完成状态以目标软件为准。' if target.associated else '当前没有匹配的文件关联，将打开文件夹；请在 '+target.name+' 的“文件 → 导入”中选择生成文件。'))
        self.method.setText(description)
        self.start_button.setText('导入' if target.kind in ('vault','joplin') else '转换并打开' if target.kind in ('enex','zip') else '保存')

    def choose_directory(self):
        path=FileDialogs.getExistingDirectory(self,'选择笔记库或保存目录',self.destination.currentText())
        if path:self.destination.setCurrentText(path)

    def start(self):
        target=self.targets.currentData()
        if self.running or target is None:return
        destination=self.destination.currentText().strip()
        if target.kind in ('vault','folder') and not Path(destination).is_dir():
            QMessageBox.information(self,'选择目标位置','请先选择有效的笔记库或保存目录。');return
        if target.kind in ('vault','folder') and not destination:
            QMessageBox.information(self,'选择目标位置','请选择笔记库或保存目录。');return
        self.running=True;self.cancel_event.clear()
        for w in (self.targets,self.destination,self.browse,self.refresh,self.start_button,self.open_target):w.setEnabled(False)
        self.progress.setText('正在转换摘抄并准备导入…')
        self.owner.config.setdefault('note_destinations',{})[target.id]=destination
        open_target=self.open_target.isChecked()
        def release():
            self.running=False
            for w in (self.targets,self.destination,self.browse,self.refresh,self.start_button,self.open_target):w.setEnabled(True)
        def done(result):
            release();self.receipt=result['message']
            if not open_target and result.get('state')=='handoff':self.receipt='已保存导入文件：'+'、'.join(result.get('paths',[]))
            self.progress.setText(self.receipt)
            if open_target:
                failures=[]
                for kind,path in result.get('actions',[]):
                    try:
                        if kind=='obsidian':
                            from urllib.parse import urlencode
                            ok=QDesktopServices.openUrl(QUrl('obsidian://open?'+urlencode({'path':path})))
                        elif kind=='app':
                            subprocess.Popen([path],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0));ok=True
                        else:ok=QDesktopServices.openUrl(QUrl.fromLocalFile(path))
                        if not ok:failures.append(path)
                    except OSError:failures.append(path)
                if failures:self.receipt+=' 目标程序未能打开，文件已保留：'+str(result.get('paths',[''])[0] if result.get('paths') else '')
            self.accept()
        def failed(message):
            release();self.progress.setText(message)
            if self.cancel_event.is_set():self.receipt=message;super(NoteTransferDialog,self).reject()
            else:QMessageBox.warning(self,'导入未完成',message)
        self.owner.task(lambda progress:transfer(self.records,target,destination,ROOT/'output'/'notes-transfer',progress,self.cancel_event),done,failed,self.progress.setText)

    def reject(self):
        if self.running:
            self.cancel_event.set();self.progress.setText('正在取消；已导入的内容会保留。');return
        self._closed=True;super().reject()

    def closeEvent(self,event):
        if self.running:self.reject();event.ignore()
        else:self._closed=True;super().closeEvent(event)