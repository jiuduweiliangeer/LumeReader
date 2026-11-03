
"""Build public screenshots from self-authored text and a simulated library."""
import os,sys,json
from pathlib import Path
root=Path(__file__).resolve().parents[1]
os.environ['LUME_DATA_DIR']=str(root/'build-support'/'screenshot-user')
os.environ['QT_QPA_PLATFORM']='offscreen'
sys.path.insert(0,str(root))
import bootstrap
from dataclasses import asdict
from PyQt6.QtWidgets import QApplication,QTabWidget
from PyQt6.QtCore import Qt
from lume.ui import MainWindow
from lume.ui_theme import apply_theme
from lume.ui_parts import load_system_fonts
from lume.engine import convert
from lume.model import Layout
from lume.devices import Device
from lume.device_library import DeviceBook
# Disable all hardware operations for documentation screenshots.
MainWindow.refresh_devices=lambda self,*args,**kwargs:None
MainWindow.refresh_library=lambda self,*args,**kwargs:None
data=root/'build-support'/'screenshot-user';data.mkdir(parents=True,exist_ok=True)
sample=root/'examples'/'阅读示例.txt'
outputs=[]
for fmt in ('epub','pdf','kfx'):
    outputs.append(convert(sample,data/'books',fmt,Layout(cover_path=str(root/'lume'/'assets'/'lume.png'))))
app=QApplication([])
load_system_fonts();apply_theme(app)
window=MainWindow([str(sample),outputs[0].output,outputs[1].output])
window.device_timer.stop()
window.show()
window.device_combo.blockSignals(True)
window.device_combo.addItem('Kindle Paperwhite · 演示设备',Device('Kindle Paperwhite · 演示设备','usb',str(data/'documents')))
window.device_combo.setCurrentIndex(window.device_combo.count()-1)
window.device_combo.blockSignals(False)
window.device_status.setText('● Kindle 已连接')
window.library.set_books({'books':[
    DeviceBook('demo-1','清晨的书桌.kfx','清晨的书桌.kfx',892136),
    DeviceBook('demo-2','河岸散步.azw3','散文/河岸散步.azw3',1348021),
    DeviceBook('demo-3','阅读笔记.pdf','资料/阅读笔记.pdf',2469130),
    DeviceBook('demo-4','夜航故事.mobi','小说/夜航故事.mobi',732801)],'free':24*1024**3})
window.library.message.setText('演示书架 · 删除前自动备份，保留批注和阅读记录。')
window.queue.check_all(True)
window.queue.selectRow(0);window.select_preview()
window.set_cover(str(root/'lume'/'assets'/'lume.png'))
window.output_path.setText('C:\\Users\\Reader\\Documents\\Lume Books')
window.history=[asdict(r) for r in outputs]
window.refresh_history()
window.update_actions()
inspector=next(t for t in window.findChildren(QTabWidget) if t is not window.workspace_tabs)
dest=root/'docs'/'images';dest.mkdir(parents=True,exist_ok=True)
def capture(name):
    app.processEvents()
    assert window.grab().save(str(dest/name))
inspector.setCurrentIndex(1);capture('workspace.png')
inspector.setCurrentIndex(2);capture('cover.png')
window.workspace_tabs.setCurrentIndex(1)
window.library.table.item(0,0).setCheckState(Qt.CheckState.Checked)
window.library.table.item(1,0).setCheckState(Qt.CheckState.Checked)
capture('kindle-library.png')
window.switch(1)
window.history_table.item(0,0).setCheckState(Qt.CheckState.Checked)
# Avoid leaking any real machine paths even in a self-authored demo.
window.notes.setPlainText('C:\\Users\\Reader\\Documents\\Lume Books\\阅读示例.epub\n\n已完成 · 目录、封面与正文已生成。')
capture('completed.png')
print('Public screenshots generated:',len(list(dest.glob('*.png'))))
app.quit()
