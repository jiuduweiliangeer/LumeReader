import os,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bootstrap
import pytest
from lume import kindle_formats as formats,paths

@pytest.fixture
def locations(tmp_path,monkeypatch):
    app=tmp_path/'Program Files'/'LumeReader'/'_internal'
    exe=app.parent
    user=tmp_path/'user data'
    for name,value in (('APP_ROOT',app),('EXE_ROOT',exe),('USER_ROOT',user)):
        monkeypatch.setattr(paths,name,value)
    monkeypatch.delenv('KINDLEGEN',raising=False)
    monkeypatch.setattr(formats.shutil,'which',lambda name:None)
    for name in ('LOCALAPPDATA','ProgramFiles','ProgramFiles(x86)'):
        monkeypatch.setenv(name,str(tmp_path/'empty'))
    if os.name=='nt':
        import winreg
        def missing(*a,**kw):raise OSError('no registered external compiler')
        monkeypatch.setattr(winreg,'OpenKey',missing)
    return app,exe,user

def create(path):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_bytes(b'MZ-test-only')
    return str(path)

def test_frozen_internal_compiler_precedes_environment_and_path(locations,monkeypatch,tmp_path):
    bundled=create(locations[0]/'tools'/'kindlegen.exe')
    external=create(tmp_path/'external'/'kindlegen.exe')
    monkeypatch.setenv('KINDLEGEN',external)
    monkeypatch.setattr(formats.shutil,'which',lambda name:external)
    monkeypatch.chdir(tmp_path)
    assert formats.find_kindlegen()==bundled
    assert formats.bundled_kindlegen()==bundled

def test_expired_saved_path_falls_back_to_internal_component(locations,tmp_path):
    bundled=create(locations[0]/'tools'/'kindlegen.exe')
    assert formats.find_kindlegen(str(tmp_path/'removed installation'/'kindlegen.exe'))==bundled

def test_explicit_existing_override_is_preserved(locations,tmp_path):
    create(locations[0]/'tools'/'kindlegen.exe')
    external=create(tmp_path/'custom'/'kindlegen.exe')
    assert formats.find_kindlegen(external)==external

def test_standard_build_keeps_external_compiler_support(locations,monkeypatch,tmp_path):
    external=create(tmp_path/'custom'/'kindlegen.exe')
    monkeypatch.setenv('KINDLEGEN',external)
    assert not formats.bundled_kindlegen()
    assert formats.find_kindlegen()==external

def test_standard_build_without_any_compiler_reports_missing(locations,tmp_path):
    assert formats.find_kindlegen()==''
    assert formats.find_kindlegen(str(tmp_path/'not installed.exe'))==''
