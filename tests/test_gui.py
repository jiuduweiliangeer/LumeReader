import os,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import QTimer
import pytest
from lume.jobs import QueueRunner
from lume.model import Layout

@pytest.fixture(scope='module')
def app():
    return QApplication.instance() or QApplication([])

def wait_until(app,predicate,timeout=20):
    limit=time.monotonic()+timeout
    while not predicate() and time.monotonic()<limit:
        app.processEvents()
        time.sleep(.005)
    assert predicate(),'Qt worker timeout'

def job(source,out):
    return {'source':str(source),'output_dir':str(out),'format':'epub','layout':Layout().to_dict()}

def test_gui_worker_stays_responsive_and_continues_after_error(app,tmp_path):
    good=tmp_path/'中文输入.txt'
    good.write_text('第一章 开始\n中文正文。\n第二章 继续\n第二段文字。',encoding='utf-8')
    runner=QueueRunner()
    state={'done':False,'beats':0,'success':[],'failure':[]}
    timer=QTimer()
    timer.setInterval(10)
    timer.timeout.connect(lambda:state.update(beats=state['beats']+1))
    timer.start()
    runner.success.connect(lambda i,r:state['success'].append(r))
    runner.failure.connect(lambda i,e:state['failure'].append(e))
    runner.finished.connect(lambda c:state.update(done=True))
    runner.start([job(tmp_path/'missing.txt',tmp_path/'out'),job(good,tmp_path/'out')])
    wait_until(app,lambda:state['done'])
    timer.stop()
    assert len(state['success'])==len(state['failure'])==1
    assert Path(state['success'][0]['output']).is_file()
    assert state['beats']>=5

def test_gui_hard_cancel_removes_owned_staging(app,tmp_path):
    source=tmp_path/'cancel.txt'
    source.write_text('第一章 开始\n'+('一段用于验证取消操作的正文。\n'*120000),encoding='utf-8')
    runner=QueueRunner()
    state={'done':False,'cancelled':False}
    runner.progress.connect(lambda value,text:runner.cancel() if value>=22 else None)
    runner.finished.connect(lambda c:state.update(done=True,cancelled=c))
    runner.start([job(source,tmp_path/'out')])
    request_id=runner.request.stem
    wait_until(app,lambda:state['done'])
    assert state['cancelled']
    assert not list((tmp_path/'out').glob('*'))
    assert not (bootstrap.ROOT/'.runtime'/'jobs'/request_id).exists()


def test_preview_has_dark_text_with_dark_system_palette(app):
    from PyQt6.QtGui import QPalette,QColor
    from lume.ui_parts import ReaderPreview
    previous=app.palette()
    palette=QPalette(previous)
    palette.setColor(QPalette.ColorRole.Text,QColor('white'))
    palette.setColor(QPalette.ColorRole.WindowText,QColor('white'))
    app.setPalette(palette)
    preview=ReaderPreview()
    preview.resize(300,390)
    preview.show()
    app.processEvents()
    image=preview.grab().toImage()
    dark=sum(1 for y in range(50,280) for x in range(45,255)
             if image.pixelColor(x,y).lightness()<90)
    app.setPalette(previous)
    preview.close()
    assert dark>350,'Text on the cream page must remain legible in dark Windows themes'

def test_library_filter_sort_and_multiselect_keep_book_identity(app,tmp_path):
    from PyQt6.QtCore import Qt,QItemSelectionModel
    from lume.ui_library import LibraryPanel
    from lume.devices import Device
    from lume.device_library import DeviceBook
    class Owner:
        def current_device(self): return Device('Test','usb',str(tmp_path))
        def refresh_library(self): pass
        def export_selection(self): pass
        def remove_selection(self): pass
    panel=LibraryPanel(Owner())
    books=[DeviceBook('b','同名.txt','B/同名.txt',12),
           DeviceBook('a','同名.txt','A/同名.txt',15),
           DeviceBook('c','另一部.kfx','C/另一部.kfx',20)]
    panel.set_books({'books':books,'free':1024**3})
    panel.table.sortItems(3,Qt.SortOrder.AscendingOrder)
    selection=panel.table.selectionModel()
    for row in (0,1):
        panel.table.item(row,0).setCheckState(Qt.CheckState.Checked)
    assert {b.id for b in panel.selected()}=={'a','b'}
    panel.search.setText('B/')
    assert [b.id for b in panel.selected()]==['b']
    panel.set_busy(True)
    assert not panel.remove.isEnabled()
    panel.close()

def test_main_batch_import_deduplicates_and_removes_only_queue(app,tmp_path,monkeypatch):
    import lume.storage as storage
    from lume.ui import MainWindow
    monkeypatch.setattr(storage,'DATA',tmp_path/'data')
    monkeypatch.setattr(MainWindow,'refresh_devices',lambda self,*args,**kwargs:None)
    folder=tmp_path/'input'
    folder.mkdir()
    for name in ('一.txt','二.txt'):
        (folder/name).write_text('第一章 开始\n正文内容。',encoding='utf-8')
    (folder/'ignored.bin').write_bytes(b'x')
    window=MainWindow()
    window.device_timer.stop()
    window.add_files([str(folder),str(folder/'一.txt')])
    assert len(window.sources)==2
    assert window.convert_button.isEnabled()
    assert not window.send_convert_button.isEnabled()
    window.queue.selectAll()
    window.remove_selected()
    assert not window.sources
    assert (folder/'一.txt').is_file() and (folder/'二.txt').is_file()
    window.close()


def test_main_only_sends_checked_books(app,tmp_path,monkeypatch):
    from PyQt6.QtCore import Qt
    import lume.storage as storage
    from lume.ui import MainWindow
    from lume.devices import Device
    monkeypatch.setattr(storage,'DATA',tmp_path/'data')
    monkeypatch.setattr(MainWindow,'refresh_devices',lambda self,*args,**kwargs:None)
    monkeypatch.setattr(MainWindow,'device_changed',lambda self,*args:None)
    paths=[]
    for name in ('one.txt','two.txt','three.txt'):
        path=tmp_path/name
        path.write_text('第一章\n正文。',encoding='utf-8')
        paths.append(str(path))
    window=MainWindow(paths)
    window.device_timer.stop()
    window.device_combo.addItem('Test',Device('Test','usb',str(tmp_path)))
    window.queue.check_all(False)
    window.queue.item(1,0).setCheckState(Qt.CheckState.Checked)
    captured=[]
    monkeypatch.setattr(window.runner,'start',lambda jobs:captured.extend(jobs))
    window.start_direct_send()
    assert len(captured)==1 and captured[0]['source']==paths[1]
    assert captured[0]['_row']==1 and captured[0]['operation']=='send'
    window.busy(False)
    window.close()

def test_light_theme_and_file_picker_ignore_dark_system_palette(app,monkeypatch):
    from PyQt6.QtGui import QPalette,QColor
    from PyQt6.QtWidgets import QFileDialog,QMenu
    from lume.ui_theme import apply_theme,FileDialogs
    previous=app.palette()
    dark=QPalette(previous)
    dark.setColor(QPalette.ColorRole.Window,QColor('#202020'))
    dark.setColor(QPalette.ColorRole.Base,QColor('#202020'))
    app.setPalette(dark)
    apply_theme(app)
    menu=QMenu()
    menu.addAction('选择文件')
    assert menu.palette().color(QPalette.ColorRole.Window).lightness()>220
    assert menu.palette().color(QPalette.ColorRole.Text).lightness()<100
    received={}
    def picker(*args,**kwargs):
        received.update(kwargs)
        return ('','')
    monkeypatch.setattr(QFileDialog,'getOpenFileName',picker)
    FileDialogs.getOpenFileName(None,'Test')
    assert received['options']&QFileDialog.Option.DontUseNativeDialog
    app.setPalette(previous)
