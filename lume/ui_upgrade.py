"""Device recommendations, reading presets and per-book cover controls."""
from dataclasses import replace
from pathlib import Path
from PyQt6.QtWidgets import QDialog,QMessageBox
from .presets import PRESETS,MODEL_NAMES,preset_values,recommend
from .device_library import device_key


class UpgradeControls:
    def current_device(self):
        device=super().current_device()
        if device and hasattr(self,'device_model') and self.device_model.currentData():
            return replace(device,model=self.device_model.currentData())
        return device

    def device_changed(self):
        if hasattr(self,'device_model'):
            raw=self.device_combo.currentData()
            key=device_key(raw)
            if key!=getattr(self,'_model_device_key',None):
                self._model_device_key=key
                override=self.config.get('device_models',{}).get(key,'')
                self.device_model.blockSignals(True)
                self.device_model.setCurrentIndex(max(0,self.device_model.findData(override)))
                self.device_model.blockSignals(False)
            if raw:
                self.device_model.setItemText(0,'自动识别 · '+MODEL_NAMES.get(raw.model,'型号未知'))
            else:self.device_model.setItemText(0,'自动识别型号')
        self.apply_recommendation()
        super().device_changed()

    def model_changed(self):
        raw=self.device_combo.currentData()
        if raw:
            self.config.setdefault('device_models',{})[device_key(raw)]=self.device_model.currentData() or ''
        self.apply_recommendation()

    def apply_recommendation(self):
        if not hasattr(self,'recommendation_hint') or not hasattr(self,'kindlegen') or self._batch_busy:return
        from .kindle_formats import find_kindlegen
        device=self.current_device()
        compiler=bool(find_kindlegen(self.kindlegen.text().strip()))
        self.recommendation=recommend(device,compiler)
        key=(device_key(device),device.model if device else '',compiler)
        changed=key!=getattr(self,'_recommend_key',None)
        previous=getattr(self,'_recommend_key',None)
        self._recommend_key=key
        if changed and (device or previous and previous[0]):
            index=self.output_format.findData(self.recommendation.format)
            if index>=0:self.output_format.setCurrentIndex(index)
        self.show_recommendation()

    def show_recommendation(self):
        if not hasattr(self,'recommendation_hint'):return
        rec=getattr(self,'recommendation',recommend(None))
        current=self.output_format.currentData()
        extra=' 当前选择 '+str(current).upper()+'，可在上方修改。' if current!=rec.format else ' 可手动修改格式。'
        self.recommendation_hint.setText(rec.reason+extra)

    def use_preset(self,*args):
        if not hasattr(self,'cover_path') or not hasattr(self,'pdf_margin'):return
        data=self.layout_options().to_dict()
        data['cover_path']=self.cover_path.text()
        data.update(preset_values(self.preset_combo.currentData()))
        self.apply_layout(data)
        self.pdf_margin.setValue(data['margin'])
        self.update_preview()

    def edit_cover_choices(self,books=None):
        if self._batch_busy:return False
        if books is None or isinstance(books,bool):
            books=[self.sources[row] for row in self.queue.checked_rows()]
        if not books:return True
        from .ui_covers import CoverWizard
        wizard=CoverWizard(books,self.book_covers,self)
        if wizard.exec()!=QDialog.DialogCode.Accepted:return False
        self.book_covers.update(wizard.choices)
        for row,path in enumerate(self.sources):
            if path in wizard.choices:
                cover=self.book_covers[path]
                message='独立封面：'+(Path(cover).name if cover else '保留原封面')
                self.queue.item(row,0).setToolTip(path+'\n'+message)
                self.queue.item(row,3).setText('已选封面' if cover else '保留原封面')
        return True

    def choose_batch_cover_mode(self,count):
        dialog=QMessageBox(self)
        dialog.setWindowTitle('本批书籍的封面')
        dialog.setText(f'本次转换 {count} 本书，是否为每本书单独设置封面？')
        dialog.setInformativeText('逐本设置可以分别选图或保留原封面。使用当前设置会应用封面页中的选择。')
        individual=dialog.addButton('逐本设置封面',QMessageBox.ButtonRole.AcceptRole)
        shared=dialog.addButton('使用当前封面设置',QMessageBox.ButtonRole.NoRole)
        dialog.addButton('取消',QMessageBox.ButtonRole.RejectRole)
        dialog.setDefaultButton(shared)
        dialog.exec()
        if dialog.clickedButton()==individual:return 'individual'
        if dialog.clickedButton()==shared:return 'shared'
        return None

    def layout_for_source(self,path):
        layout=self.layout_options()
        if self._individual_covers:layout.cover_path=self.book_covers.get(path,'')
        device=self.current_device()
        if layout.kfx_mode=='auto' and device:
            rec=getattr(self,'recommendation',recommend(device))
            layout.kfx_mode=rec.kfx_mode
        layout.validate()
        return layout.to_dict()

    def build_clippings(self):
        from .ui_clippings import ClippingsPanel
        self.clippings=ClippingsPanel(self)
        self.stack.addWidget(self.clippings)