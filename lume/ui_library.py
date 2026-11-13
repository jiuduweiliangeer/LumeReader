"""Kindle library widgets and device actions shared by the main workspace."""
from datetime import datetime
from pathlib import Path
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QDesktopServices, QColor
from PyQt6.QtWidgets import (QWidget,QHBoxLayout,QVBoxLayout,QLineEdit,QComboBox,
                            QTableWidgetItem,QMessageBox,QFileDialog,QHeaderView)
from .ui_parts import label,button,card,table,check_all_control
from .util import format_size
from .storage import ROOT
from .device_library import device_key
from .ui_theme import FileDialogs as QFileDialog

class LibraryPanel(QWidget):
    def __init__(self,owner):
        super().__init__()
        self.owner=owner
        self.books=[]
        self.locked=False
        layout=QVBoxLayout(self)
        layout.setContentsMargins(0,12,0,0)
        panel,box=card()
        heading=QHBoxLayout()
        self.summary=label('连接 Kindle，书籍会显示在这里','Section')
        heading.addWidget(self.summary,1)
        self.refresh=button('刷新书架',owner.refresh_library)
        heading.addWidget(self.refresh)
        box.addLayout(heading)
        filters=QHBoxLayout()
        self.search=QLineEdit()
        self.search.setPlaceholderText('搜索书名或文件夹…')
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.filter_books)
        filters.addWidget(self.search,1)
        self.formats=QComboBox()
        self.formats.addItem('全部格式','')
        self.formats.currentIndexChanged.connect(self.filter_books)
        filters.addWidget(self.formats)
        box.addLayout(filters)
        self.table=table(['书籍','格式','大小','所在文件夹'])
        self.table.horizontalHeader().setSectionResizeMode(3,QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(3,230)
        self.table.verticalHeader().setDefaultSectionSize(52)
        self.table.setSortingEnabled(True)
        self.table.itemSelectionChanged.connect(self.selection_changed)
        self.table.checkedChanged.connect(self.selection_changed)
        self.select_all=check_all_control(self.table)
        heading.insertWidget(0,self.select_all)
        box.addWidget(self.table,1)
        self.empty=label('用数据线连接并解锁 Kindle，即可查看设备上的书籍。','Muted',True)
        self.empty.setAlignment(Qt.AlignmentFlag.AlignCenter)
        box.addWidget(self.empty)
        footer=QHBoxLayout()
        self.selection=label('选择书籍以进行管理','Muted')
        footer.addWidget(self.selection,1)
        self.export=button('保存到电脑',owner.export_selection)
        self.remove=button('从 Kindle 删除',owner.remove_selection)
        self.remove.setStyleSheet('QPushButton:enabled {color:#a15e4e;}')
        footer.addWidget(self.export)
        footer.addWidget(self.remove)
        box.addLayout(footer)
        layout.addWidget(panel,1)
        self.message=label('删除前自动保存本地备份；批注和阅读记录会保留。','Muted',True)
        self.message.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.message)
        self.selection_changed()

    def set_books(self,snapshot):
        checked={b.id for b in self.selected()}
        self.books=snapshot['books']
        selected=self.formats.currentData()
        self.formats.blockSignals(True)
        self.formats.clear()
        self.formats.addItem('全部格式','')
        for fmt in sorted({b.format for b in self.books}): self.formats.addItem(fmt,fmt)
        self.formats.setCurrentIndex(max(0,self.formats.findData(selected)))
        self.formats.blockSignals(False)
        self.table.blockSignals(True)
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(self.books))
        for row,book in enumerate(self.books):
            folder=str(Path(book.path).parent).replace('\\','/')
            for col,text in enumerate((book.title,book.format,format_size(book.size),
                                       'documents' if folder=='.' else 'documents/'+folder)):
                item=QTableWidgetItem(text)
                item.setToolTip('documents/'+book.path)
                item.setData(Qt.ItemDataRole.UserRole,book)
                if col==0: item.setCheckState(Qt.CheckState.Checked if book.id in checked else Qt.CheckState.Unchecked)
                if col==1: item.setForeground(QColor('#52806e'))
                self.table.setItem(row,col,item)
        self.table.setSortingEnabled(True)
        self.table.blockSignals(False)
        self.table.checkedChanged.emit()
        self.filter_books()
        free=snapshot.get('free')
        capacity=f'  ·  剩余 {free/1024**3:.1f} GB' if free is not None else ''
        self.summary.setText(f'Kindle 书架  /  {len(self.books)} 本{capacity}')
        self.selection_changed()

    def filter_books(self):
        query=self.search.text().strip().casefold()
        fmt=self.formats.currentData()
        visible=0
        for row in range(self.table.rowCount()):
            book=self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
            match=(not query or query in (book.name+' '+book.path).casefold()) and (not fmt or book.format==fmt)
            self.table.setRowHidden(row,not match)
            if match: visible+=1
        self.empty.setVisible(visible==0)
        self.empty.setText('没有匹配的书籍，试试其他关键词。' if self.books else
                           '书架为空。添加本地书籍后，点击「转换并发送」即可。'
                           if self.owner.current_device() else '连接并解锁 Kindle 后，这里会自动显示书籍。')
        self.selection_changed()

    def selected(self):
        return [self.table.item(row,0).data(Qt.ItemDataRole.UserRole)
                for row in self.table.checked_rows()]

    def selection_changed(self):
        books=self.selected()
        self.selection.setText(f'已选择 {len(books)} 本 · {format_size(sum(b.size for b in books))}' if books else '选择书籍以进行管理')
        enabled=bool(books) and not self.locked and bool(self.owner.current_device())
        self.export.setEnabled(enabled)
        self.remove.setEnabled(enabled)

    def set_busy(self,value):
        self.locked=value
        self.refresh.setEnabled(not value and bool(self.owner.current_device()))
        self.selection_changed()

class DeviceWorkspace:
    def build_device_bar(self):
        self._device_busy=False
        self._scanning=False
        self._batch_busy=False
        self._manual_device=None
        self._library_key=''
        panel,box=card()
        box.setContentsMargins(16,10,16,10)
        row=QHBoxLayout()
        self.device_status=label('正在检测 Kindle…','Badge')
        row.addWidget(self.device_status)
        self.device_combo=QComboBox()
        self.device_combo.setMinimumWidth(230)
        self.device_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.device_combo.currentIndexChanged.connect(self.device_changed)
        row.addWidget(self.device_combo,1)
        from .presets import MODEL_NAMES
        self.device_model=QComboBox()
        self.device_model.setMinimumWidth(190)
        self.device_model.setMaximumWidth(260)
        self.device_model.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.device_model.addItem('自动识别型号','')
        for key,name in MODEL_NAMES.items():self.device_model.addItem(name,key)
        self.device_model.currentIndexChanged.connect(self.model_changed)
        row.addWidget(self.device_model)
        self.refresh_button=button('刷新',lambda:self.refresh_devices(force=True),'Quiet')
        row.addWidget(self.refresh_button)
        self.manual_button=button('指定设备目录',self.choose_device,'Quiet')
        row.addWidget(self.manual_button)
        box.addLayout(row)
        return panel

    def current_device(self):
        return self.device_combo.currentData() if hasattr(self,'device_combo') else None

    def update_actions(self):
        if not hasattr(self,'send_convert_button'): return
        from .devices import USB_FORMATS
        ready=not self._batch_busy
        connected=bool(self.current_device())
        compatible='.'+str(self.output_format.currentData()) in USB_FORMATS
        self.convert_button.setEnabled(ready and bool(self.queue.checked_rows()))
        self.send_convert_button.setEnabled(ready and bool(self.queue.checked_rows()) and connected and compatible
                                            and not self._device_busy and not self._scanning)
        reason=('连接 Kindle 后可一键转换并发送' if not connected else
                '此格式请通过亚马逊 Send to Kindle 上传；有线发送请选择 KFX / AZW3' if not compatible else
                '转换后自动写入 Kindle，并校验文件与封面')
        self.send_convert_button.setToolTip(reason)
        self.direct_send_button.setEnabled(ready and bool(self.queue.checked_rows()) and connected
                                           and not self._device_busy and not self._scanning)
        if hasattr(self,'history_send_button'):
            self.history_send_button.setEnabled(connected and ready and bool(self.history_rows()) and not self._device_busy and not self._scanning)
            self.history_delete_button.setEnabled(ready and bool(self.history_rows()) and not self._device_busy)
        if hasattr(self,'library'):
            self.library.set_busy(self._device_busy or self._scanning or self._batch_busy)
        self.device_combo.setEnabled(not self._device_busy and ready and not self._scanning)
        self.device_model.setEnabled(connected and ready and not self._device_busy)
        if hasattr(self,'clippings'):self.clippings.update_actions()
        self.refresh_button.setEnabled(not self._device_busy and ready and not self._scanning)
        self.manual_button.setEnabled(not self._device_busy and ready and not self._scanning)

    def refresh_devices(self,force=False):
        from .devices import scan_devices
        if self._device_busy or self._batch_busy or self._scanning: return
        self._scanning=True
        self.update_actions()
        previous=device_key(self.current_device())
        previous_model=getattr(self.current_device(),'model','')
        def done(devices):
            if self._manual_device and Path(self._manual_device.path).is_dir():
                if device_key(self._manual_device) not in {device_key(d) for d in devices}:
                    devices.append(self._manual_device)
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            if not devices: self.device_combo.addItem('未连接 Kindle',None)
            for d in devices: self.device_combo.addItem(d.name,d)
            selected=next((i for i in range(self.device_combo.count())
                           if device_key(self.device_combo.itemData(i))==previous),0)
            self.device_combo.setCurrentIndex(selected)
            self.device_combo.blockSignals(False)
            self._scanning=False
            current=device_key(self.current_device())
            self.device_status.setText('● Kindle 已连接' if current else '○ Kindle 未连接')
            if previous!=current or self._library_key!=current or force or previous_model!=getattr(self.current_device(),'model',''):
                self.device_changed()
                if force and current==self._library_key: self.refresh_library()
            self.update_actions()
        def failed(message):
            self._scanning=False
            self.device_combo.blockSignals(True)
            self.device_combo.clear()
            self.device_combo.addItem('连接检测失败',None)
            self.device_combo.blockSignals(False)
            self._library_key=''
            self.library.set_books({'books':[]})
            self.device_status.setText('○ 检测未完成')
            self.device_status.setToolTip(message)
            self.library.message.setText(message)
            self.update_actions()
        self.task(lambda progress:scan_devices(),done,failed)

    def device_changed(self):
        if not hasattr(self,'library'): return
        current=device_key(self.current_device())
        if current!=self._library_key:
            self._library_key=''
            self.library.set_books({'books':[]})
            if current:
                self.refresh_library()
                if not self.sources: self.workspace_tabs.setCurrentIndex(1)
        if not current:
            self.device_status.setText('○ Kindle 未连接')
            self.library.summary.setText('Kindle 书架')
            self.library.message.setText('用数据线连接并解锁 Kindle，书架会自动加载。')
        self.update_actions()

    def refresh_library(self):
        from .device_library import refresh_books
        device=self.current_device()
        if not device or self._device_busy or self._batch_busy or self._scanning: return
        self._device_busy=True
        self.library.message.setText('正在读取 Kindle 书架…')
        self.update_actions()
        def done(snapshot):
            self._device_busy=False
            self._library_key=device_key(device)
            self.library.set_books(snapshot)
            message='书架已更新 · 删除前自动备份，保留批注和阅读记录。'
            covers=snapshot.get('covers',{})
            if covers.get('restored'):
                message=f"书架已更新 · 已恢复 {covers['restored']} 张封面，安全弹出 Kindle 后查看。"
            if covers.get('errors'):
                message+=' 封面恢复未完成：'+covers['errors'][0]
            self.library.message.setText(message)
            self.device_status.setText('● Kindle 已连接')
            self.update_actions()
        def failed(message):
            self._device_busy=False
            self._library_key=''
            self.library.message.setText(message)
            self.update_actions()
        self.task(lambda progress:refresh_books(device,progress),done,failed,self.library.message.setText)

    def choose_device(self):
        from .devices import Device
        path=QFileDialog.getExistingDirectory(self,'选择 Kindle 的 documents 目录')
        if path:
            self._manual_device=Device('Kindle · 手动目录','usb',path,'documents')
            self.device_combo.addItem(self._manual_device.name,self._manual_device)
            self.device_combo.setCurrentIndex(self.device_combo.count()-1)
            self.device_status.setText('● Kindle 目录已连接')

    def export_selection(self):
        books=self.library.selected()
        device=self.current_device()
        if not books or not device or self._device_busy or self._batch_busy: return
        path=QFileDialog.getExistingDirectory(self,'保存所选书籍到电脑',self.config['output'])
        if path:
            from .device_library import export_books
            self.device_operation(lambda progress:export_books(device,books,path,progress),
                                  f'已保存 {len(books)} 本到 {path}')

    def remove_selection(self):
        books=self.library.selected()
        device=self.current_device()
        if not books or not device or self._device_busy or self._batch_busy: return
        names='\n'.join('• '+b.name for b in books[:6])
        if len(books)>6: names+=f'\n…等 {len(books)} 本'
        backup=ROOT/'data'/'device-backups'/datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        answer=QMessageBox.question(self,'从 Kindle 删除所选书籍',
            f'将移除这 {len(books)} 本书：\n\n{names}\n\n先保存完整备份到：\n{backup}\n\n批注和阅读记录会保留。是否继续？',
            QMessageBox.StandardButton.Yes|QMessageBox.StandardButton.No,QMessageBox.StandardButton.No)
        if answer!=QMessageBox.StandardButton.Yes: return
        from .device_library import remove_books
        self.device_operation(lambda progress:remove_books(device,books,backup,progress),
                              f'已从 Kindle 移除 {len(books)} 本 · 备份：{backup}',reload=True)

    def device_operation(self,fn,message,reload=False):
        self._device_busy=True
        self.update_actions()
        def done(result):
            self._device_busy=False
            self.library.message.setText(message)
            self.device_status.setText('● 操作完成')
            self.device_status.setToolTip(message)
            self.update_actions()
            if reload:
                # Keep the operation receipt visible after the shelf refresh.
                self.refresh_library()
                self.library.message.setText(message)
            self.status.setText(message)
            self.status.setToolTip(message)
        def failed(error):
            self._device_busy=False
            self.library.message.setText(error)
            self.device_status.setText('○ 操作未完成')
            self.update_actions()
            QMessageBox.warning(self,'设备操作未完成',error)
        self.task(fn,done,failed,self.library.message.setText)

    def send_history(self):
        from .devices import send_file,USB_FORMATS
        rows=self.history_rows()
        results=[self.history[row] for row in rows]
        device=self.current_device()
        if not results or not device or self._device_busy or self._batch_busy or self._scanning: return
        def send_batch(progress):
            sent,failed=[],[]
            for index,result in enumerate(results):
                source=Path(result['output'])
                progress(f'发送 {index+1}/{len(results)} · {source.name}')
                try:
                    if source.suffix.lower() not in USB_FORMATS:
                        raise ValueError('此格式请使用 Send to Kindle，或先转换成 KFX / AZW3')
                    sent.append(send_file(source,device,lambda text:progress(f'{index+1}/{len(results)} · '+text)))
                except Exception as exc:
                    failed.append(source.name+'：'+str(exc))
            return {'sent':sent,'failed':failed}
        self.switch(0)
        self.workspace_tabs.setCurrentIndex(1)
        self._device_busy=True
        self.update_actions()
        def done(result):
            self._device_busy=False
            message=f'已发送 {len(result["sent"])} 本 · 未完成 {len(result["failed"])} 本'
            self.status.setText(message)
            self.status.setToolTip('\n'.join(result['failed']) or message)
            self.update_actions()
            self.refresh_library()
            if result['failed']: QMessageBox.warning(self,'部分书籍未发送',message+'\n\n'+'\n'.join(result['failed']))
        def failed(message):
            self._device_busy=False
            self.update_actions()
            self.library.message.setText(message)
        self.task(send_batch,done,failed,self.library.message.setText)
