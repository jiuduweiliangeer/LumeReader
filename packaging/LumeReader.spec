# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
import sys
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata
root=Path(SPECPATH).parent
vendor=root/'vendor'
sys.path[:0]=[str(root),str(vendor),str(vendor/'kfxgen'/'vendor')]
import comtypes.client
comtypes.client.GetModule('portabledeviceapi.dll')
comtypes.client.GetModule('portabledevicetypes.dll')
hidden=['PyQt6.QtSvg','PyQt6.QtPrintSupport','comtypes.gen.PortableDeviceApiLib','comtypes.gen.PortableDeviceTypesLib']
for module in ('lume','kindleunpack','kfxgen','kfxlib','comtypes','ziafont','ziamath','latex2mathml','markdown_it','mdurl'):
    hidden+=collect_submodules(module)
datas=[(str(root/'lume'/'assets'),'lume/assets'),
       (str(root/'licenses'),'licenses'),(str(root/'docs'),'docs'),(str(root/'examples'),'examples')]
for path in vendor.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts and path.suffix not in ('.pyc','.pyo'):
        datas.append((str(path),'vendor/'+path.parent.relative_to(vendor).as_posix()))
for filename in ('README.md','LICENSE','LICENSE.md','THIRD_PARTY.md','requirements.txt'):
    datas.append((str(root/filename),'.'))
for module in ('reportlab','pymupdf'):
    datas+=collect_data_files(module)
for name in ('PyQt6','PyQt6-Qt6','PyQt6-sip','lxml','PyMuPDF','beautifulsoup4','soupsieve',
             'tinycss2','cssselect2','webencodings','fonttools','reportlab','Pillow','comtypes','charset-normalizer','pypdf','markdown-it-py','mdurl'):
    datas+=copy_metadata(name)
binaries=[]
for filename in ('sqlite3.dll','libcrypto-3-x64.dll','libssl-3-x64.dll','libbz2.dll','ffi-8.dll'):
    path=Path(sys.base_prefix)/'Library'/'bin'/filename
    if path.exists(): binaries.append((str(path),'.'))
a=Analysis([str(root/'packaging'/'gui_entry.py'),str(root/'packaging'/'worker_entry.py')],
           pathex=[str(root),str(vendor),str(vendor/'kfxgen'/'vendor')],
           binaries=binaries,datas=datas,hiddenimports=hidden,
           excludes=['tkinter','IPython','matplotlib','numpy','pandas','scipy','torch','pytest',
                     'PyQt5','PySide2','PySide6','calibre'],noarchive=False)
pyz=PYZ(a.pure)
runtime=[s for s in a.scripts if s[0] not in ('gui_entry','worker_entry')]
gui=EXE(pyz,runtime+[s for s in a.scripts if s[0]=='gui_entry'],[],
        exclude_binaries=True,name='LumeReader',console=False,debug=False,strip=False,upx=False,
        icon=str(root/'lume'/'assets'/'lume.ico'),version=str(root/'packaging'/'version_info.txt'))
worker=EXE(pyz,runtime+[s for s in a.scripts if s[0]=='worker_entry'],[],
           exclude_binaries=True,name='LumeWorker',console=True,debug=False,strip=False,upx=False,
           icon=str(root/'lume'/'assets'/'lume.ico'),version=str(root/'packaging'/'version_info.txt'))
coll=COLLECT(gui,worker,a.binaries,a.datas,strip=False,upx=False,name='LumeReader')
