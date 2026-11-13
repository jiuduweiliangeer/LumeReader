import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
os.environ.setdefault('QT_QPA_PLATFORM','offscreen')
import pytest
from PyQt6.QtWidgets import QApplication,QDialog
from PyQt6.QtCore import Qt
from lume.ui import MainWindow
from lume.devices import Device

@pytest.fixture(scope='module')
def app():return QApplication.instance() or QApplication([])

@pytest.fixture
def window(app,tmp_path,monkeypatch):
    import lume.storage as storage
    monkeypatch.setattr(storage,'DATA',tmp_path/'data')
    monkeypatch.setattr(MainWindow,'refresh_devices',lambda *a,**kw:None)
    monkeypatch.setattr(MainWindow,'refresh_library',lambda *a,**kw:None)
    w=MainWindow();w.device_timer.stop()
    yield w
    w.busy(False);w.close()


def test_recommendation_is_visible_before_queue_starts(window,monkeypatch,tmp_path):
    import lume.kindle_formats as formats
    monkeypatch.setattr(formats,'find_kindlegen',lambda *a:'kindlegen.exe')
    window.device_combo.addItem('Voyage',Device('Voyage','usb',str(tmp_path),model='voyage'))
    window.device_changed()
    assert window.output_format.currentData()=='azw3'
    assert 'Voyage' in window.recommendation_hint.text()
    assert 'AZW3' in window.recommendation_hint.text()
    window.output_format.setCurrentIndex(window.output_format.findData('kfx'))
    window.device_changed()
    assert window.output_format.currentData()=='kfx','Periodic device refresh must keep the user override'
    assert window.layout_for_source('book.txt')['kfx_mode']=='legacy'
    window.device_model.setCurrentIndex(window.device_model.findData('paperwhite6'))
    assert window.output_format.currentData()=='kfx'
    window.device_combo.clear()
    assert window.output_format.currentData()=='kfx'


def test_preset_retains_cover_and_font(window,tmp_path):
    from lume.fonts import available_fonts
    from PIL import Image
    cover=tmp_path/'cover.png';Image.new('RGB',(30,40),'green').save(cover)
    window.set_cover(str(cover))
    font=list(available_fonts(tmp_path))[0][1]
    window.font_combo.setCurrentIndex(window.font_combo.findData(font))
    window.preset_combo.setCurrentIndex(window.preset_combo.findData('voyage'))
    layout=window.layout_options()
    assert layout.screen_profile=='voyage' and layout.line_height==1.5 and layout.margin==14
    assert layout.cover_path==str(cover) and layout.font_path==font


def test_batch_per_book_covers_are_distinct_and_direct_send_unchanged(window,tmp_path,monkeypatch):
    from PIL import Image
    books=[];covers=[]
    for i in range(2):
        book=tmp_path/f'{i}.txt';book.write_text('第一章\n正文。',encoding='utf-8');books.append(str(book))
        cover=tmp_path/f'{i}.png';Image.new('RGB',(30,40),('red','blue')[i]).save(cover);covers.append(str(cover))
    window.add_files(books)
    monkeypatch.setattr(window,'choose_batch_cover_mode',lambda count:'individual')
    monkeypatch.setattr(window,'edit_cover_choices',lambda books:True)
    window.book_covers=dict(zip(books,covers))
    window.output_format.setCurrentIndex(window.output_format.findData('epub'))
    jobs=[];monkeypatch.setattr(window.runner,'start',lambda value:jobs.extend(value))
    window.start_conversion()
    assert [j['layout']['cover_path'] for j in jobs]==covers
    window.busy(False);jobs.clear()
    window.device_combo.addItem('Kindle',Device('Kindle','usb',str(tmp_path)))
    window.start_direct_send()
    assert len(jobs)==2 and all(j['operation']=='send' and 'layout' not in j for j in jobs)


def test_cover_wizard_requires_each_choice_and_cancel_is_transactional(app):
    from lume.ui_covers import CoverWizard
    prior={'first.txt':''}
    wizard=CoverWizard(['first.txt','second.epub','third.azw3'],prior)
    wizard.complete()
    assert wizard.result()!=QDialog.DialogCode.Accepted and wizard.list.currentRow()==1
    wizard.keep();wizard.move(1);wizard.keep();wizard.complete()
    assert wizard.result()==QDialog.DialogCode.Accepted and len(wizard.choices)==3
    assert prior=={'first.txt':''}
    cancelled=CoverWizard(['first.txt'],prior);cancelled.keep();cancelled.reject()
    assert prior=={'first.txt':''}


def test_help_preserves_chinese_tables_and_image_dimensions(app,tmp_path):
    from lume.help_view import DocumentBrowser,markdown_html
    path=tmp_path/'help.md'
    path.write_text('# 中文帮助\n\n这是正文与设置说明。\n\n| 格式 | 需要安装 |\n|---|---|\n| KFX | 不需要 |\n\n<img src="icon.png" width="88">',encoding='utf-8')
    browser=DocumentBrowser();browser.display(path)
    assert all(text in browser.toPlainText() for text in ('中文帮助','这是正文与设置说明','需要安装','不需要'))
    assert 'width="88"' in markdown_html(path.read_text(encoding='utf-8'))
    browser.close()


def test_clipping_search_and_filter_keep_book_grouping(window):
    from lume.clippings import Clipping
    panel=window.clippings
    panel.records=[Clipping('第一本','作者','highlight','春日山色'),Clipping('第一本','作者','note','我的想法'),Clipping('第二本','','highlight','另一段')]
    panel.refresh()
    assert panel.books.count()==2 and '春日山色' in panel.reader.toPlainText()
    panel.kind.setCurrentIndex(panel.kind.findData('note'))
    assert '我的想法' in panel.reader.toPlainText() and '春日山色' not in panel.reader.toPlainText()
    panel.search.setText('另一段')
    assert panel.books.count()==1 and '第二本' in panel.book_title.text()
def test_clippings_paginate_large_books(window):
    from lume.clippings import Clipping
    panel=window.clippings
    panel.records=[Clipping('同一本书','','highlight',f'摘抄标记 {i:04}',str(i)) for i in range(205)]
    panel.refresh()
    assert '共 205 条' in panel.page_label.text()
    assert '摘抄标记 0099' in panel.reader.toPlainText() and '摘抄标记 0100' not in panel.reader.toPlainText()
    panel.change_page(2)
    assert '摘抄标记 0204' in panel.reader.toPlainText() and not panel.next_page.isEnabled()
    assert '摘抄标记 0000' not in panel.reader.toPlainText()


def test_clippings_import_runs_in_worker_and_deduplicates(window,app):
    import time
    from lume.clippings import load_library
    data='书名 (作者)\n- Your Highlight | Location 42 | Added on 2026-11-14\n\n后台导入测试。\n==========\n'.encode('utf-8')
    def wait():
        limit=time.monotonic()+10
        while window.clippings.locked or window.tasks:
            app.processEvents();time.sleep(.005)
            assert time.monotonic()<limit
    window.clippings.import_data(lambda:data,'本地验证');wait()
    assert len(window.clippings.records)==1 and len(load_library())==1
    window.clippings.import_data(lambda:data,'本地验证');wait()
    assert len(window.clippings.records)==1 and '已存在 1 条' in window.clippings.status.text()
def test_navigation_collapses_and_clippings_controls_are_compact(window,app):
    window.resize(1340,900);window.show();window.switch(2);app.processEvents()
    window.sidebar.set_collapsed(True);app.processEvents()
    assert window.sidebar.width()==60 and all(b.text()=='' for b in window.nav)
    assert window.clippings.splitter.widget(0).width()<=240
    assert window.clippings.scope.lineEdit().alignment() & Qt.AlignmentFlag.AlignHCenter
    window.sidebar.toggle.click();app.processEvents()
    assert window.sidebar.width()==152 and window.nav[2].text()=='摘抄'
    assert not any(b.text().startswith(('01','02','03','04')) for b in window.nav)
    assert window.config['sidebar_collapsed'] is False


def test_note_target_picker_imports_selected_vault(window,app,tmp_path,monkeypatch):
    import time
    import lume.ui_note_transfer as ui
    from lume.note_transfer import NoteTarget
    from lume.clippings import Clipping
    vault=tmp_path/'vault';(vault/'.obsidian').mkdir(parents=True)
    monkeypatch.setattr(ui,'discover_targets',lambda:[NoteTarget('obsidian','Obsidian','vault',detected=True,libraries=[str(vault)])])
    dialog=ui.NoteTransferDialog(window,[Clipping('书名','','highlight','测试导入正文。','12')])
    limit=time.monotonic()+10
    while not dialog.start_button.isEnabled():
        app.processEvents();time.sleep(.005);assert time.monotonic()<limit
    dialog.open_target.setChecked(False)
    assert dialog.destination.currentText()==str(vault)
    dialog.start()
    while dialog.running or window.tasks:
        app.processEvents();time.sleep(.005);assert time.monotonic()<limit
    assert '已导入' in dialog.receipt and len(list(vault.rglob('*.md')))==1
    assert dialog.result()==QDialog.DialogCode.Accepted
@pytest.mark.parametrize('count,choice,expected',[(2,'shared',2),(2,None,0),(1,'unused',1)])
def test_cover_question_only_occurs_on_batch_conversion(window,tmp_path,monkeypatch,count,choice,expected):
    paths=[]
    for i in range(count):
        p=tmp_path/f'book{i}.txt';p.write_text('第一章\n正文。',encoding='utf-8');paths.append(str(p))
    calls=[]
    monkeypatch.setattr(window,'choose_batch_cover_mode',lambda n:calls.append(n) or choice)
    window.add_files(paths)
    assert calls==[] and not hasattr(window,'individual_covers')
    window.output_format.setCurrentIndex(window.output_format.findData('epub'))
    jobs=[];monkeypatch.setattr(window.runner,'start',lambda value:jobs.extend(value))
    window.start_conversion()
    assert calls==([2] if count==2 else [])
    assert len(jobs)==expected and len(window.sources)==count
    assert all(Path(p).is_file() for p in paths)

def test_integrated_compiler_has_no_install_prompt_and_recommends_voyage(window,tmp_path,monkeypatch):
    import lume.paths as paths
    bundle=tmp_path/'bundle';compiler=bundle/'tools'/'kindlegen.exe'
    compiler.parent.mkdir(parents=True);compiler.write_bytes(b'MZ-test-only')
    monkeypatch.setattr(paths,'APP_ROOT',bundle)
    window.kindlegen.clear();window.compiler_changed()
    assert '已内置' in window.compiler_status.text()
    assert window.compiler_status.toolTip()==str(compiler)
    window.device_combo.addItem('Voyage',Device('Voyage','usb',str(tmp_path),model='voyage'))
    window.device_changed()
    assert window.output_format.currentData()=='azw3'
    assert '就绪' in window.hint.text() and '需要 KindleGen' not in window.hint.text()


def test_expired_compiler_setting_reports_automatic_recovery(window,tmp_path,monkeypatch):
    import lume.paths as paths
    compiler=tmp_path/'bundle'/'tools'/'kindlegen.exe'
    compiler.parent.mkdir(parents=True);compiler.write_bytes(b'MZ-test-only')
    monkeypatch.setattr(paths,'APP_ROOT',compiler.parent.parent)
    window.kindlegen.setText(str(tmp_path/'old install'/'kindlegen.exe'))
    window.compiler_changed()
    assert window._compiler_path==str(compiler)
    assert '已自动使用内置组件' in window.compiler_status.text()
