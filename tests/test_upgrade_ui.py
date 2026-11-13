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
    window.individual_covers.blockSignals(True);window.individual_covers.setChecked(True);window.individual_covers.blockSignals(False)
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