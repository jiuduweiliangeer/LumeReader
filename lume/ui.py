from __future__ import annotations
import json
from dataclasses import asdict
from pathlib import Path
import sys
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QFont, QFontDatabase, QColor, QDesktopServices, QPixmap, QIcon
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QFrame,QLabel,QPushButton,QVBoxLayout,
    QHBoxLayout,QGridLayout,QStackedWidget,QTableWidgetItem,QFileDialog,QComboBox,QDoubleSpinBox,
    QCheckBox,QLineEdit,QProgressBar,QPlainTextEdit,QMessageBox,QScrollArea,QTabWidget,QFormLayout,QMenu,QDialog,QTextBrowser)
from .model import Layout
from .paths import APP_ROOT
from . import __version__
from .storage import ROOT,load_json,save_json,settings
from .util import format_size
from .readers import INPUTS,detect_encoding
from .ui_parts import STYLE,label,button,card,table,DropZone,ReaderPreview,check_all_control
from .jobs import Task,QueueRunner
from .ui_library import DeviceWorkspace,LibraryPanel
from .ui_theme import FileDialogs as QFileDialog,apply_theme

from .ui_upgrade import UpgradeControls
from .presets import PRESETS

class MainWindow(UpgradeControls,DeviceWorkspace,QMainWindow):
    def __init__(self,files=None):
        super().__init__()
        self.config=settings()
        self.history=load_json('history.json',[])
        self.sources=[]
        self.book_covers={}
        self._individual_covers=False
        self.tasks=[]
        self.font_id=-1
        self.runner=QueueRunner(self)
        self.runner.started.connect(self.job_started)
        self.runner.progress.connect(self.job_progress)
        self.runner.converted.connect(self.job_converted)
        self.runner.success.connect(self.job_success)
        self.runner.failure.connect(self.job_failure)
        self.runner.finished.connect(self.batch_finished)
        self.setWindowTitle('轻阅 Lume · 电子书工作台')
        self.setWindowIcon(QIcon(str(APP_ROOT/'lume'/'assets'/'lume.ico')))
        self.resize(1340,900)
        self.setMinimumSize(1180,800)
        root=QWidget()
        root.setObjectName('Root')
        self.setCentralWidget(root)
        outer=QHBoxLayout(root)
        outer.setContentsMargins(0,0,0,0)
        outer.setSpacing(0)
        from .ui_navigation import Navigation
        self.sidebar=Navigation(self)
        self.nav=self.sidebar.buttons
        outer.addWidget(self.sidebar)
        self.stack=QStackedWidget()
        outer.addWidget(self.stack,1)
        self.build_workspace()
        self.build_history()
        self.build_clippings()
        self.build_settings()
        self.kindlegen.editingFinished.connect(self.apply_recommendation)
        self.fill_fonts()
        self.apply_layout(self.config['layout'])
        self.refresh_history()
        self.add_files(files or [])
        self.switch(0)
        self.setAcceptDrops(True)
        self.update_actions()
        self.device_timer=QTimer(self)
        self.device_timer.setInterval(8000)
        self.device_timer.timeout.connect(self.refresh_devices)
        self.device_timer.start()
        QTimer.singleShot(400,self.refresh_devices)

    def page(self,title,subtitle):
        w=QWidget()
        box=QVBoxLayout(w)
        box.setContentsMargins(24,22,24,20)
        box.setSpacing(14)
        box.addWidget(label(title,'Title'))
        box.addWidget(label(subtitle,'Muted'))
        self.stack.addWidget(w)
        return box

    def build_workspace(self):
        page=self.page('书籍工作台','批量转换、直接发送与设备书籍管理')
        page.addWidget(self.build_device_bar())
        self.workspace_tabs=QTabWidget()
        self.workspace_tabs.tabBar().setUsesScrollButtons(False)
        self.workspace_tabs.tabBar().setMinimumWidth(300)
        self.workspace_tabs.tabBar().setExpanding(False)
        local=QWidget()
        row=QHBoxLayout(local)
        row.setContentsMargins(0,12,0,0)
        row.setSpacing(18)
        main=QVBoxLayout()
        drop=DropZone()
        drop.files.connect(self.add_files)
        drop.clicked.connect(self.choose_files)
        main.addWidget(drop)
        panel,q=card()
        head=QHBoxLayout()
        self.queue_label=label('本地书籍  /  0 本','Section')
        head.addWidget(self.queue_label)
        head.addStretch()
        self.add_button=button('＋ 添加书籍',lambda:None)
        menu=QMenu(self.add_button)
        menu.addAction('选择文件（可多选）',self.choose_files)
        menu.addAction('导入整个文件夹',self.choose_input_folder)
        self.add_button.setMenu(menu)
        head.addWidget(self.add_button)
        self.remove_button=button('移除选中',self.remove_selected,'Quiet')
        head.addWidget(self.remove_button)
        self.clear_button=button('清空',self.clear_queue,'Quiet')
        head.addWidget(self.clear_button)
        q.addLayout(head)
        self.queue=table(['书籍','格式','大小','状态'])
        self.queue.setMinimumHeight(130)
        self.queue.itemSelectionChanged.connect(self.select_preview)
        self.queue.checkedChanged.connect(self.queue_checks_changed)
        self.queue_all=check_all_control(self.queue)
        head.insertWidget(0,self.queue_all)
        q.addWidget(self.queue,1)
        self.empty=label('拖入文件或文件夹，或点击「添加书籍」。','Muted')
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        q.addWidget(self.empty)
        main.addWidget(panel,1)
        panel,export=card()
        outrow=QHBoxLayout()
        outrow.addWidget(label('输出格式','Section'))
        self.output_format=QComboBox()
        for fmt,text in [('epub','EPUB · 通用 / 无线发送'),('azw3','AZW3 · Kindle 兼容'),
                         ('kfx','KFX · Kindle 增强排版'),('mobi','MOBI · 双格式兼容'),
                         ('pdf','PDF · 设备页面'),('txt','TXT · 纯文本'),
                         ('html','HTML · 单文件网页'),('fb2','FB2 · 结构化文本')]:
            self.output_format.addItem(text,fmt)
        outrow.addWidget(self.output_format,1)
        export.addLayout(outrow)
        self.hint=label('保留目录、排版与字体；可通过 Send to Kindle 上传。','Muted',True)
        export.addWidget(self.hint)
        self.recommendation_hint=label('默认推荐 KFX。连接 Kindle 后根据型号推荐，可手动调整。','Muted',True)
        self.recommendation_hint.setStyleSheet('color:#44715a;font-size:12px;')
        export.addWidget(self.recommendation_hint)
        self.output_format.currentIndexChanged.connect(self.format_changed)
        self.output_format.setCurrentIndex(max(0,self.output_format.findData(self.config.get('format','kfx'))))
        self.format_changed()
        outrow=QHBoxLayout()
        self.output_path=QLineEdit(self.config['output'])
        self.output_path.setToolTip('输出文件夹；同名文件自动编号')
        outrow.addWidget(self.output_path,1)
        outrow.addWidget(button('选择目录',self.choose_output))
        export.addLayout(outrow)
        main.addWidget(panel)
        footer=QHBoxLayout()
        self.status=label('支持批量添加 · 可拖入整个文件夹','Muted',True)
        main.addWidget(self.status)
        footer.addStretch()
        self.cancel_button=button('取消',self.runner.cancel)
        self.cancel_button.setEnabled(False)
        footer.addWidget(self.cancel_button)
        self.direct_send_button=button('直接发送',self.start_direct_send)
        self.direct_send_button.setToolTip('将队列中的原文件直接发送到 Kindle，不转换、不修改排版')
        footer.addWidget(self.direct_send_button)
        self.convert_button=button('仅转换',lambda:self.start_conversion(False))
        self.convert_button.setMinimumWidth(100)
        footer.addWidget(self.convert_button)
        self.send_convert_button=button('转换并发送  →',lambda:self.start_conversion(True),'Primary')
        self.send_convert_button.setMinimumWidth(146)
        footer.addWidget(self.send_convert_button)
        main.addLayout(footer)
        self.progress=QProgressBar()
        self.progress.setTextVisible(False)
        self.progress.setFixedHeight(6)
        main.addWidget(self.progress)
        row.addLayout(main,1)
        inspector,ins=card()
        inspector.setFixedWidth(320)
        ins.addWidget(label('阅读样式','Section'))
        self.preset_combo=QComboBox()
        for key,profile in PRESETS.items():self.preset_combo.addItem(profile['name'],key)
        self.preset_combo.currentIndexChanged.connect(self.use_preset)
        ins.addWidget(self.preset_combo)
        tabs=QTabWidget()
        sw=QWidget()
        sl=QVBoxLayout(sw)
        sl.setContentsMargins(0,14,0,0)
        sl.setSpacing(13)
        grid=QGridLayout()
        grid.setSpacing(12)
        self.spins={}
        for i,(key,text,lo,hi,step,suffix) in enumerate([
            ('font_size','字号基准 / PDF',10,40,1,' px'),('line_height','行间距',1,3,.05,' 倍'),
            ('paragraph_gap','段后距离',0,3,.05,' em'),('indent','首行缩进',0,4,.5,' 字')]):
            column=QVBoxLayout()
            column.addWidget(label(text,'Muted'))
            spin=QDoubleSpinBox()
            spin.setButtonSymbols(QDoubleSpinBox.ButtonSymbols.NoButtons)
            spin.setRange(lo,hi)
            spin.setSingleStep(step)
            spin.setDecimals(2 if step<1 else 0)
            spin.setSuffix(suffix)
            spin.valueChanged.connect(self.update_preview)
            self.spins[key]=spin
            column.addWidget(spin)
            grid.addLayout(column,i//2,i%2)
        sl.addLayout(grid)
        self.indent_mode=QComboBox()
        for text,value in [('只补齐没有缩进的段落','missing'),('统一所有正文段落缩进','all'),('取消首行缩进','none')]:
            self.indent_mode.addItem(text,value)
        self.indent_mode.currentIndexChanged.connect(self.update_preview)
        sl.addWidget(self.indent_mode)
        self.alignment=QComboBox()
        self.alignment.addItem('两端对齐','justify')
        self.alignment.addItem('左对齐','left')
        self.alignment.currentIndexChanged.connect(self.update_preview)
        sl.addWidget(self.alignment)
        sl.addSpacing(6)
        sl.addWidget(label('嵌入字体','Section'))
        self.font_combo=QComboBox()
        self.font_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.font_combo.currentIndexChanged.connect(self.font_changed)
        sl.addWidget(self.font_combo)
        sl.addWidget(button('选择 TTF / OTF 字体文件…',self.choose_font))
        self.subset=QCheckBox('只嵌入本书用到的字形')
        self.subset.setChecked(True)
        sl.addWidget(self.subset)
        sl.addWidget(label('Kindle 阅读时请选择“出版商字体”。AZW3 字号随设备设置缩放；此处调整默认比例。','Muted',True))
        sl.addWidget(button('恢复当前预设默认值',self.use_preset,'Quiet'))
        sl.addStretch()
        style_scroll=QScrollArea()
        style_scroll.setWidgetResizable(True)
        style_scroll.setWidget(sw)
        tabs.addTab(style_scroll,'排版')
        pw=QWidget()
        pl=QVBoxLayout(pw)
        pl.setContentsMargins(0,10,0,0)
        self.preview=ReaderPreview()
        pl.addWidget(self.preview,1)
        pl.addWidget(label('排版示意 · 实际效果随 Kindle 阅读设置变化','Muted',True))
        tabs.addTab(pw,'预览')
        cw=QWidget()
        cl=QVBoxLayout(cw)
        cl.setContentsMargins(0,14,0,0)
        self.cover_preview=QLabel('保留原书封面')
        self.cover_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.cover_preview.setMinimumHeight(300)
        self.cover_preview.setStyleSheet('background:#f0f4f1;border:1px dashed #bccfc3;border-radius:10px;color:#7c8986;')
        cl.addWidget(self.cover_preview,1)
        self.cover_path=QLineEdit()
        self.cover_path.setReadOnly(True)
        self.cover_path.setPlaceholderText('未选图片 · 保留原书封面')
        cl.addWidget(self.cover_path)
        cl.addWidget(button('选择封面图片…',self.choose_cover,'Primary'))
        cl.addWidget(button('清除选择 · 保留原书封面',lambda:self.set_cover(''),'Quiet'))
        cl.addWidget(label('单本转换使用当前封面；批量转换时可选择逐本设置。直接发送保留原文件。','Muted',True))
        cover_scroll=QScrollArea()
        cover_scroll.setWidgetResizable(True)
        cover_scroll.setWidget(cw)
        tabs.addTab(cover_scroll,'封面')
        ins.addWidget(tabs,1)
        ins.addWidget(label('自动识别章节  ·  生成可导航目录','Muted'))
        row.addWidget(inspector)
        self.workspace_tabs.addTab(local,'本地书籍')
        self.library=LibraryPanel(self)
        self.workspace_tabs.addTab(self.library,'Kindle 书架')
        page.addWidget(self.workspace_tabs,1)

    def build_history(self):
        page=self.page('已完成','勾选记录以批量发送或删除')
        panel,layout=card()
        head=QHBoxLayout()
        self.history_count=label('完成记录','Section')
        head.addWidget(self.history_count,1)
        self.history_search=QLineEdit()
        self.history_search.setPlaceholderText('搜索书名或格式…')
        self.history_search.setClearButtonEnabled(True)
        self.history_search.setMaximumWidth(280)
        self.history_search.textChanged.connect(self.filter_history)
        head.addWidget(self.history_search)
        self.history_delete_button=button('删除选中',self.remove_history,'Danger')
        head.addWidget(self.history_delete_button)
        layout.addLayout(head)
        self.history_table=table(['书籍 / 格式','处理方式','耗时','大小','目录'])
        self.history_table.itemSelectionChanged.connect(self.show_notes)
        self.history_table.checkedChanged.connect(self.show_notes)
        self.history_all=check_all_control(self.history_table)
        head.insertWidget(0,self.history_all)
        layout.addWidget(self.history_table,1)
        row=QHBoxLayout()
        row.addWidget(button('打开文件',self.open_result))
        row.addWidget(button('打开所在目录',lambda:self.open_result(folder=True)))
        row.addWidget(button('回收目录',lambda:QDesktopServices.openUrl(
            QUrl.fromLocalFile(str(ROOT/'data'/'local-trash'))),'Quiet'))
        row.addStretch()
        self.history_send_button=button('发送选中书籍到 Kindle',self.send_history,'Primary')
        row.addWidget(self.history_send_button)
        layout.addLayout(row)
        self.notes=QPlainTextEdit()
        self.notes.setReadOnly(True)
        self.notes.setMaximumHeight(100)
        self.notes.setPlaceholderText('选择结果，查看文件路径、转换说明与发送状态。')
        layout.addWidget(self.notes)
        page.addWidget(panel,1)

    def build_settings(self):
        page=self.page('设置','文本识别、字体与输出选项')
        scroll=QScrollArea()
        scroll.setWidgetResizable(True)
        panel,layout=card()
        form=QFormLayout()
        form.setVerticalSpacing(16)
        self.kfx_mode=QComboBox()
        for title,value in (('自动 · 发送时适配设备','auto'),
                            ('旧款 Kindle / Voyage · 书架封面兼容','legacy'),
                            ('新款 Kindle · 个人文档','personal')):
            self.kfx_mode.addItem(title,value)
        self.kfx_mode.setCurrentIndex(max(0,self.kfx_mode.findData(self.config['layout'].get('kfx_mode','auto'))))
        form.addRow('KFX 封面兼容',self.kfx_mode)
        form.addRow('',label('自动模式：USB 盘符设备用旧款模式，MTP 设备用个人文档。\n'
                             '仅转换给 Voyage 使用时，请选旧款模式，再用软件发送以同步书架封面。','Muted',True))
        self.encoding=QComboBox()
        for value in ('auto','utf-8','utf-8-sig','gb18030','utf-16','big5'):
            self.encoding.addItem('自动检测' if value=='auto' else value,value)
        self.encoding.setCurrentIndex(max(0,self.encoding.findData(self.config['layout'].get('encoding','auto'))))
        form.addRow('TXT 文本编码',self.encoding)
        self.join_lines=QCheckBox('连续行合并为段落（以空行分段）')
        self.join_lines.setChecked(self.config['layout'].get('join_lines',False))
        form.addRow('硬换行文本',self.join_lines)
        self.chapter_pattern=QLineEdit(self.config['layout'].get('chapter_pattern',''))
        self.chapter_pattern.setPlaceholderText('留空自动识别中文章节、卷、Chapter 等')
        form.addRow('自定义章节正则',self.chapter_pattern)
        self.pdf_margin=QDoubleSpinBox()
        self.pdf_margin.setRange(8,50)
        self.pdf_margin.setSuffix(' pt')
        self.pdf_margin.setValue(self.config['layout'].get('margin',18))
        form.addRow('PDF 页面留白',self.pdf_margin)
        self.kindlegen=QLineEdit(self.config.get('kindlegen',''))
        self.kindlegen.setPlaceholderText('留空自动发现 KindleGen')
        row=QHBoxLayout()
        row.addWidget(self.kindlegen,1)
        row.addWidget(button('浏览',self.choose_kindlegen))
        form.addRow('MOBI / AZW3 编译器',row)
        self.font_dir=QLineEdit(self.config['font_dir'])
        form.addRow('字体文件夹',self.font_dir)
        layout.addLayout(form)
        layout.addWidget(button('保存设置并刷新字体列表',self.save_settings,'Primary'))
        layout.addSpacing(12)
        layout.addWidget(label('格式与能力','Section'))
        layout.addWidget(label('EPUB / TXT / HTML / PDF / FB2：本地转换。\n'
            'KFX：支持目录、字体与封面。\n'
            'MOBI / AZW3：导入可直接使用；导出需配置 KindleGen。\n'
            'DOCX / Markdown：支持导入正文与章节。\n'
            '扫描 PDF 按图片保留，不含 OCR；复杂版式请复核。\n'
            'TXT / FB2 的字体、行距受到格式限制。\n'
            '当前处理未加密的电子书。','Muted',True))
        layout.addWidget(label('所有处理都在本机完成。原始书籍不会被修改，输出同名时自动编号。','Muted',True))
        links=QHBoxLayout()
        links.addWidget(button('使用说明',lambda:self.show_document('README.md')))
        links.addWidget(button('开源协议',lambda:self.show_document('LICENSE.md')))
        links.addWidget(button('数据目录',lambda:QDesktopServices.openUrl(QUrl.fromLocalFile(str(ROOT)))))
        links.addStretch()
        layout.addLayout(links)
        layout.addWidget(label('Lume Reader '+__version__+' · AGPL-3.0-only\nCopyright © 2026 Lume Reader contributors.\n按开源协议提供源代码，软件不提供担保。','Muted',True))
        scroll.setWidget(panel)
        page.addWidget(scroll,1)

    def show_document(self,filename):
        dialog=QDialog(self)
        dialog.setWindowTitle('轻阅 · '+('使用说明' if filename=='README.md' else '开源协议'))
        dialog.resize(950,760)
        dialog.setMinimumSize(850,600)
        layout=QVBoxLayout(dialog)
        from .help_view import DocumentBrowser
        browser=DocumentBrowser()
        browser.setOpenLinks(False)
        browser.setOpenExternalLinks(False)
        def display(path):
            path=path.resolve()
            if not path.is_file(): return
            browser.display(path)
        def navigate(url):
            if url.scheme() in ('http','https'):
                QDesktopServices.openUrl(url)
            else:
                target=Path(url.toLocalFile()) if url.isLocalFile() else APP_ROOT/url.path()
                if target.is_file(): display(target)
        browser.anchorClicked.connect(navigate)
        display(APP_ROOT/filename)
        layout.addWidget(browser)
        layout.addWidget(button('关闭',dialog.accept))
        dialog.exec()

    def switch(self,index):
        self.stack.setCurrentIndex(index)
        for i,b in enumerate(self.nav): b.setChecked(i==index)

    def layout_options(self):
        data=dict(self.config['layout'])
        data.update({key:spin.value() for key,spin in self.spins.items()})
        data.update(indent_mode=self.indent_mode.currentData(),alignment=self.alignment.currentData(),
                    font_path=self.font_combo.currentData() or '',subset_font=self.subset.isChecked(),
                    cover_path='' if self._individual_covers else self.cover_path.text(),
                    screen_profile=self.preset_combo.currentData() or 'paperwhite6')
        from .fonts import allow_subset
        data['subset_font']=data['subset_font'] and allow_subset(data['font_path'])
        if hasattr(self,'encoding'):
            data.update(encoding=self.encoding.currentData(),join_lines=self.join_lines.isChecked(),
                        chapter_pattern=self.chapter_pattern.text().strip(),margin=self.pdf_margin.value(),
                        kfx_mode=self.kfx_mode.currentData())
        return Layout(**data)

    def apply_layout(self,data):
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentIndex(max(0,self.preset_combo.findData(data.get('screen_profile','paperwhite6'))))
        self.preset_combo.blockSignals(False)
        if hasattr(self,'pdf_margin'):self.pdf_margin.setValue(data.get('margin',18))
        for key,spin in self.spins.items(): spin.setValue(data.get(key,getattr(Layout(),key)))
        self.indent_mode.setCurrentIndex(max(0,self.indent_mode.findData(data.get('indent_mode','missing'))))
        self.alignment.setCurrentIndex(max(0,self.alignment.findData(data.get('alignment','justify'))))
        self.subset.setChecked(data.get('subset_font',True))
        path=data.get('font_path','')
        if path and self.font_combo.findData(path)<0: self.font_combo.addItem(Path(path).stem,path)
        self.font_combo.setCurrentIndex(max(0,self.font_combo.findData(path)))
        self.font_changed()
        self.set_cover(data.get('cover_path',''))

    def fill_fonts(self):
        previous=self.font_combo.currentData() or self.config['layout'].get('font_path','')
        self.font_combo.blockSignals(True)
        self.font_combo.clear()
        self.font_combo.addItem('使用阅读器默认字体','')
        from .fonts import available_fonts
        for title,path in available_fonts(self.config['font_dir']):self.font_combo.addItem(title,path)
        if previous and self.font_combo.findData(previous)<0: self.font_combo.addItem(Path(previous).stem,previous)
        self.font_combo.setCurrentIndex(max(0,self.font_combo.findData(previous)))
        self.font_combo.blockSignals(False)

    def font_changed(self):
        if not hasattr(self,'preview'): return
        if self.font_id>=0: QFontDatabase.removeApplicationFont(self.font_id)
        self.font_id=-1
        self.preview.family='Microsoft YaHei'
        path=self.font_combo.currentData()
        from .fonts import allow_subset
        allowed=allow_subset(path or '')
        self.subset.setEnabled(allowed)
        if not allowed:self.subset.setChecked(False)
        self.subset.setToolTip('此字体保留完整原文件，不生成字形子集。' if not allowed else '')
        if path and Path(path).is_file():
            self.font_id=QFontDatabase.addApplicationFont(path)
            families=QFontDatabase.applicationFontFamilies(self.font_id)
            if families: self.preview.family=families[0]
        self.update_preview()

    def update_preview(self,*args):
        if all(hasattr(self,x) for x in ('preview','font_combo','subset')):
            self.preview.options=self.layout_options()
            self.preview.update()

    def select_preview(self):
        row=self.queue.currentRow()
        if not 0<=row<len(self.sources): return
        path=Path(self.sources[row])
        if path.suffix.lower() in ('.txt','.md'):
            try:
                with open(path,encoding=detect_encoding(path),errors='replace') as f: text=f.read(2800)
                lines=[s.strip() for s in text.splitlines() if s.strip()]
                self.preview.title=path.stem
                self.preview.paragraphs=[s for s in lines if len(s)>22][:4] or lines[:4]
                self.preview.update()
            except OSError: pass

    def choose_files(self):
        paths,_=QFileDialog.getOpenFileNames(self,'添加书籍',self.config['last_input'],
                         '电子书 ('+' '.join('*.'+x for x in INPUTS)+')')
        if paths:
            self.config['last_input']=str(Path(paths[0]).parent)
            self.add_files(paths)

    def choose_input_folder(self):
        path=QFileDialog.getExistingDirectory(self,'批量导入文件夹',self.config['last_input'])
        if path:
            self.config['last_input']=path
            self.add_files([path])

    def add_files(self,paths):
        if self._batch_busy: return
        paths=list(paths)
        if paths:
            self.switch(0)
            self.workspace_tabs.setCurrentIndex(0)
        expanded=[]
        for value in paths:
            candidate=Path(value)
            if candidate.is_dir():
                import os
                for directory,dirs,files in os.walk(candidate,followlinks=False):
                    dirs[:]=[d for d in dirs if not d.startswith('.') and not (Path(directory)/d).is_symlink()]
                    expanded.extend(str(Path(directory)/name) for name in sorted(files)
                                    if Path(name).suffix.lower().lstrip('.') in INPUTS)
            else: expanded.append(value)
        paths=expanded
        rejected=[]
        existing={value.casefold() for value in self.sources}
        for value in paths:
            path=Path(value)
            if not path.is_file() or path.suffix.lower().lstrip('.') not in INPUTS:
                rejected.append(path.name)
                continue
            full=str(path.resolve())
            if full.casefold() in existing: continue
            existing.add(full.casefold())
            self.sources.append(full)
            row=self.queue.rowCount()
            self.queue.insertRow(row)
            for col,text in enumerate((path.stem,path.suffix[1:].upper(),format_size(path.stat().st_size),'待转换')):
                item=QTableWidgetItem(text)
                item.setToolTip(full)
                if col==0: item.setCheckState(Qt.CheckState.Checked)
                if col==1: item.setForeground(QColor('#52806e'))
                self.queue.setItem(row,col,item)
        self.queue_checks_changed()
        self.empty.setVisible(not self.sources)
        if self.sources and self.queue.currentRow()<0: self.queue.selectRow(0)
        self.update_actions()
        if rejected: QMessageBox.information(self,'未添加的文件','格式不受支持：\n'+'\n'.join(rejected[:10]))

    def queue_checks_changed(self):
        self.queue_label.setText(f'本地书籍 / {len(self.sources)} 本 · 已选 {len(self.queue.checked_rows())} 本')
        self.update_actions()

    def remove_selected(self):
        if self._batch_busy: return
        for row in reversed(self.queue.checked_rows()):
            self.book_covers.pop(self.sources[row],None)
            self.sources.pop(row)
            self.queue.removeRow(row)
        self.queue_checks_changed()
        self.empty.setVisible(not self.sources)
        self.update_actions()

    def clear_queue(self):
        if self._batch_busy: return
        self.sources.clear()
        self.book_covers.clear()
        self.queue.setRowCount(0)
        self.queue_label.setText('本地书籍  /  0 本')
        self.empty.show()
        self.queue.checkedChanged.emit()
        self.update_actions()

    def dragEnterEvent(self,event):
        if event.mimeData().hasUrls() and not self._batch_busy: event.acceptProposedAction()

    def dropEvent(self,event):
        self.add_files([url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()])
        event.acceptProposedAction()

    def choose_output(self):
        path=QFileDialog.getExistingDirectory(self,'选择输出目录',self.output_path.text())
        if path: self.output_path.setText(path)

    def choose_font(self):
        path,_=QFileDialog.getOpenFileName(self,'选择嵌入字体',self.config['font_dir'],'字体 (*.ttf *.otf)')
        if path:
            if self.font_combo.findData(path)<0: self.font_combo.addItem(Path(path).stem,path)
            self.font_combo.setCurrentIndex(self.font_combo.findData(path))

    def choose_cover(self):
        path,_=QFileDialog.getOpenFileName(self,'选择书籍封面',self.config['last_input'],
                                         '封面图片 (*.jpg *.jpeg *.png *.webp *.bmp)')
        if path: self.set_cover(path)

    def set_cover(self,path):
        self.cover_path.setText(path)
        self.cover_path.setToolTip(path)
        self.cover_preview.clear()
        if path:
            pixmap=QPixmap(path)
            if not pixmap.isNull():
                self.cover_preview.setPixmap(pixmap.scaled(260,350,Qt.AspectRatioMode.KeepAspectRatio,
                                                         Qt.TransformationMode.SmoothTransformation))
                return
        self.cover_preview.setText('保留原书封面')

    def choose_kindlegen(self):
        path,_=QFileDialog.getOpenFileName(self,'选择 KindleGen',str(ROOT.parent),'KindleGen (kindlegen.exe)')
        if path: self.kindlegen.setText(path)

    def save_settings(self,checked=False,notify=True):
        try:
            layout=self.layout_options()
            layout.validate()
            self.config.update(layout=layout.to_dict(),output=self.output_path.text().strip() or str(ROOT/'output'),
                               kindlegen=self.kindlegen.text().strip(),font_dir=self.font_dir.text().strip(),
                               format=self.output_format.currentData())
            self.config.pop('individual_covers',None)
            self.config['layout']['cover_path']=self.cover_path.text()
            save_json('settings.json',self.config)
            if notify:
                self.fill_fonts()
                self.status.setText('设置已保存')
            return True
        except Exception as e:
            QMessageBox.warning(self,'设置有误',str(e))
            return False

    def format_changed(self):
        hints={'epub':'保留目录、排版和字体；可通过 Send to Kindle 上传。',
               'azw3':'Kindle USB 推荐格式，保留嵌入字体；需要 KindleGen。',
               'kfx':'支持 Kindle 有线发送、目录、字体与封面。',
               'mobi':'双格式兼容文件；旧 MOBI7 不支持嵌入字体。',
               'pdf':'按所选阅读预设的屏幕尺寸生成页面，带目录链接和书签。',
               'txt':'全角空格缩进与文本目录；无法保存字体和精确行距。',
               'html':'含图片与字体的单文件 HTML。',
               'fb2':'保留章节结构；字体和段落显示由阅读器控制。'}
        self.hint.setText(hints.get(self.output_format.currentData(),''))
        self.show_recommendation()
        self.update_actions()

    def start_direct_send(self):
        if self._batch_busy or self._device_busy or self._scanning or not self.sources: return
        device=self.current_device()
        if not device: return
        self._batch_rows=self.queue.checked_rows()
        if not self._batch_rows: return
        self._batch_send=True
        self._batch_direct=True
        self._batch_results={}
        self._batch_errors={}
        self.busy(True)
        self.progress.setValue(0)
        for row in self._batch_rows:
            self.queue.item(row,3).setText('等待发送')
            self.queue.item(row,3).setToolTip('')
        jobs=[{'source':self.sources[row],'operation':'send','send_to':asdict(device),
               'output_dir':str(ROOT/'output'),'_row':row} for row in self._batch_rows]
        self.runner.start(jobs)

    def start_conversion(self,send=False):
        if self._batch_busy or not self.sources: return
        device=self.current_device()
        if send:
            from .devices import USB_FORMATS
            if not device or self._device_busy or self._scanning: return
            if '.'+self.output_format.currentData() not in USB_FORMATS: return
        self._batch_rows=self.queue.checked_rows()
        if not self._batch_rows: return
        self._individual_covers=False
        if len(self._batch_rows)>1 and self.output_format.currentData()!='txt':
            choice=self.choose_batch_cover_mode(len(self._batch_rows))
            if choice is None:return
            if choice=='individual':
                self._individual_covers=True
                if not self.edit_cover_choices([self.sources[r] for r in self._batch_rows]):
                    self._individual_covers=False
                    return
        if not self.save_settings(notify=False):return
        try:
            layouts={r:self.layout_for_source(self.sources[r]) for r in self._batch_rows}
        except Exception as exc:
            QMessageBox.warning(self,'排版或封面有误',str(exc))
            return
        self._batch_send=send
        self._batch_direct=False
        self._batch_results={}
        self._batch_errors={}
        self.busy(True)
        self.progress.setValue(0)
        jobs=[{'source':self.sources[row],'format':self.output_format.currentData(),'output_dir':self.config['output'],
               'layout':layouts[row],'kindlegen':self.config['kindlegen'],'_row':row} for row in self._batch_rows]
        if send:
            for job in jobs: job['send_to']=asdict(device)
        for row in self._batch_rows:
            self.queue.item(row,3).setText('等待处理')
            self.queue.item(row,3).setToolTip('')
        self.runner.start(jobs)

    def busy(self,value):
        self._batch_busy=value
        for b in (self.add_button,self.remove_button,self.clear_button): b.setEnabled(not value)
        self.cancel_button.setEnabled(value)
        self.output_format.setEnabled(not value)
        self.preset_combo.setEnabled(not value)
        self.update_actions()

    def job_started(self,row):
        self.queue.item(row,3).setText('直接发送中…' if self._batch_direct else '转换中…')
        self.queue.item(row,3).setForeground(QColor('#27775e'))

    def job_progress(self,value,text):
        self.progress.setValue(value)
        self.status.setText(text)
        if '发送' in text or 'MTP' in text or '回读' in text or '封面' in text:
            self.queue.item(self.runner.index,3).setText('发送中…')

    def remember_result(self,result):
        self.history=[r for r in self.history if r['output']!=result['output']]
        self.history.insert(0,result)
        self.history=self.history[:200]
        save_json('history.json',self.history)
        self.refresh_history()

    def job_converted(self,row,result):
        self._batch_results[row]=result
        self.remember_result(result)
        self.queue.item(row,3).setText('已转换 · 准备发送')
        self.queue.item(row,3).setToolTip(result['output'])

    def job_success(self,row,result):
        self._batch_results[row]=result
        if result.get('send_error'):
            status='已转换 · 发送失败'
            self._batch_errors[row]=result['send_error']
            self.queue.item(row,3).setForeground(QColor('#ad6a55'))
        elif result.get('device_path'):
            status='原文件已发送' if result.get('operation')=='send' else '已发送到 Kindle'
        else:
            status=f"完成 · {result['seconds']:.1f}s"
        self.queue.item(row,3).setText(status)
        self.queue.item(row,3).setToolTip(result['output']+'\n'+result.get('send_error',result.get('device_path','')))
        if result.get('operation')!='send' or not any(r['output']==result['output'] for r in self.history):
            self.remember_result(result)

    def job_failure(self,row,message):
        self._batch_errors[row]=message
        if row in self._batch_results:
            status='已转换 · 发送未完成'
        else:
            status='已取消' if message=='已取消' else '失败 · 悬停查看'
        self.queue.item(row,3).setText(status)
        self.queue.item(row,3).setToolTip(message)
        self.queue.item(row,3).setForeground(QColor('#ad6a55'))

    def batch_finished(self,cancelled):
        self._individual_covers=False
        self.busy(False)
        self.apply_recommendation()
        converted=sum(r.get('operation')!='send' for r in self._batch_results.values())
        sent=sum(bool(r.get('device_path')) for r in self._batch_results.values())
        message=f'原文件已发送 {sent} 本' if self._batch_direct else f'已转换 {converted} 本'
        if self._batch_send and not self._batch_direct: message+=f' · 已发送 {sent} 本'
        if self._batch_errors: message+=f' · {len(self._batch_errors)} 项未完成（悬停状态查看）'
        if cancelled:
            message+=' · 已取消剩余任务'
            for row in self._batch_rows:
                if self.queue.item(row,3).text().startswith('等待'):
                    self.queue.item(row,3).setText('未处理 · 已取消')
        self.status.setText(message)
        self.status.setToolTip('\n'.join(self._batch_errors.values()) or message)
        if not cancelled: self.progress.setValue(100)
        if self._batch_send: self.refresh_library()

    def refresh_history(self):
        selected={self.history_table.item(row,0).toolTip() for row in self.history_rows()
                  if self.history_table.item(row,0)}
        self.history_table.blockSignals(True)
        self.history_table.setRowCount(len(self.history))
        for row,r in enumerate(self.history):
            mode='直接发送' if r.get('operation')=='send' else '转换并发送' if r.get('device_path') else '转换'
            texts=[Path(r['output']).name,mode,f"{r['seconds']:.2f} 秒",format_size(r['size']),
                   '—' if r.get('operation')=='send' else f"{r['chapters']} 节"]
            for col,text in enumerate(texts):
                item=QTableWidgetItem(text)
                item.setToolTip(r['output'])
                if col==0: item.setCheckState(Qt.CheckState.Checked if r['output'] in selected else Qt.CheckState.Unchecked)
                self.history_table.setItem(row,col,item)
        self.history_table.blockSignals(False)
        self.history_table.checkedChanged.emit()
        self.filter_history()
        if self.history and not selected: self.history_table.selectRow(0)
        self.show_notes()

    def history_rows(self):
        return self.history_table.checked_rows()

    def filter_history(self):
        query=self.history_search.text().strip().casefold()
        for row,r in enumerate(self.history):
            self.history_table.setRowHidden(row,bool(query and query not in Path(r['output']).name.casefold()))
        self.show_notes()

    def remove_history(self):
        from datetime import datetime
        selected=[self.history[row] for row in self.history_rows()]
        if not selected or self._batch_busy or self._device_busy: return
        removable=[r for r in selected if r.get('operation')!='send'
                   and Path(r['output']).resolve()!=Path(r['source']).resolve() and Path(r['output']).is_file()]
        dialog=QMessageBox(self)
        dialog.setWindowTitle('删除已完成记录')
        dialog.setText(f'删除选中的 {len(selected)} 条记录？')
        dialog.setInformativeText('原始导入书籍和 Kindle 上的书籍会保留。')
        checkbox=QCheckBox(f'同时移除 {len(removable)} 个转换输出文件（先保存到回收目录）')
        checkbox.setChecked(bool(removable))
        checkbox.setEnabled(bool(removable))
        dialog.setCheckBox(checkbox)
        delete=dialog.addButton('删除',QMessageBox.ButtonRole.DestructiveRole)
        cancel=dialog.addButton('取消',QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(cancel)
        dialog.exec()
        if dialog.clickedButton()!=delete: return
        paths={r['output'] for r in selected}
        def finish(errors=None):
            failed={e['output'] for e in errors or []}
            self.history=[r for r in self.history if r['output'] not in paths or r['output'] in failed]
            save_json('history.json',self.history)
            self.refresh_history()
            self._device_busy=False
            self.update_actions()
            message=f'已删除 {len(paths-failed)} 条记录'
            if errors: message+='\n未删除：\n'+'\n'.join(e['output']+'：'+e['message'] for e in errors)
            self.notes.setPlainText(message)
        if not checkbox.isChecked():
            finish()
            return
        from .local_history import trash_outputs
        destination=ROOT/'data'/'local-trash'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        self._device_busy=True
        self.update_actions()
        def done(receipt):
            finish(receipt['errors'])
            self.notes.appendPlainText('文件备份：'+str(destination))
        def failed(message):
            self._device_busy=False
            self.update_actions()
            QMessageBox.warning(self,'删除未完成',message)
        self.task(lambda progress:trash_outputs(removable,destination,progress),done,failed,self.notes.setPlainText)

    def selected_result(self):
        row=self.history_table.currentRow()
        return self.history[row] if 0<=row<len(self.history) and not self.history_table.isRowHidden(row) else None

    def show_notes(self):
        if not hasattr(self,'notes'): return
        rows=self.history_rows()
        self.history_count.setText(f'完成记录 / {len(self.history)} 条'+(f' · 已选 {len(rows)} 条' if rows else ''))
        self.history_delete_button.setEnabled(bool(rows) and not self._batch_busy and not self._device_busy)
        r=self.selected_result()
        if r:
            warnings=[message.replace('KFX 采用独立开源编码器；','') for message in r.get('warnings',[])]
            self.notes.setPlainText(r['output']+'\n\n'+'\n'.join(warnings)+'\n'+r.get('send_error',r.get('device_path','')))
        else: self.notes.clear()
        self.update_actions()

    def open_result(self,checked=False,folder=False):
        r=self.selected_result()
        if r:
            path=Path(r['output'])
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(path.parent if folder else path)))

    def task(self,fn,done,failed,progress=None):
        task=Task(fn,self)
        self.tasks.append(task)
        task.done.connect(done)
        task.failed.connect(failed)
        if progress: task.progress.connect(progress)
        task.finished.connect(lambda:self.tasks.remove(task))
        task.start()

    def closeEvent(self,event):
        if self.runner.process:
            answer=QMessageBox.question(self,'转换仍在进行','退出会取消当前任务，已经完成的结果会保留。是否退出？',
                    QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
            if answer!=QMessageBox.StandardButton.Yes:
                event.ignore()
                return
            self.runner.cancel()
            if self.runner.process: self.runner.process.waitForFinished(3000)
        if self.tasks:
            QMessageBox.information(self,'后台任务进行中','请等待设备检测或发送完成后再退出。')
            event.ignore()
            return
        self.device_timer.stop()
        self.save_settings(notify=False)
        event.accept()

def launch(files=None):
    app=QApplication(sys.argv[:1])
    app.setApplicationName('轻阅 Lume')
    app.setOrganizationName('LumeReader')
    app.setApplicationVersion(__version__)
    app.setWindowIcon(QIcon(str(APP_ROOT/'lume'/'assets'/'lume.ico')))
    from .ui_parts import load_system_fonts
    load_system_fonts()
    apply_theme(app)
    window=MainWindow(files)
    window.show()
    return app.exec()
