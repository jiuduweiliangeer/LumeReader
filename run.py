import bootstrap
import argparse
import contextlib
from dataclasses import asdict
import json
import logging
from pathlib import Path
import sys
import traceback

def main():
    parser=argparse.ArgumentParser(description='轻阅 Lume — independent ebook converter')
    parser.add_argument('--worker',help='JSON job description (internal)')
    parser.add_argument('--convert',metavar='FILE')
    parser.add_argument('--to',default='kfx')
    from lume.paths import USER_ROOT
    parser.add_argument('--output',default=str(USER_ROOT/'output'))
    parser.add_argument('--font',default='')
    parser.add_argument('--cover',default='',help='Cover image (JPEG/PNG/WebP)')
    parser.add_argument('--kfx-mode',choices=('auto','personal','legacy'),default='auto',
                        help='KFX cover compatibility: legacy for Kindle Voyage / older USB Kindles')
    parser.add_argument('--open',nargs='*',default=[])
    parser.add_argument('--self-check',action='store_true')
    args=parser.parse_args()
    if args.self_check:
        from PyQt6.QtCore import qVersion, PYQT_VERSION_STR
        from lume.kindle_formats import find_kindlegen
        from kfxgen.native_generator import NativeKFXGenerator
        import pymupdf, lxml, tinycss2, cssselect2, pypdf, bz2, ctypes
        from lume import __version__
        from lume.help_view import markdown_html
        from lume.fonts import available_fonts
        from lume.presets import PRESETS
        assert '中文帮助' in markdown_html('# 中文帮助')
        from lume.clippings import export_enex
        from lume.paths import USER_ROOT,APP_ROOT
        device_count=None
        if sys.platform=='win32':
            from lume.wpd import Session
            with Session() as session: device_count=len(session.kindle_ids())
        print(json.dumps({'version':__version__,'python':sys.executable,'python_version':sys.version.split()[0],
                          'qt':qVersion(),'pyqt':PYQT_VERSION_STR,'data_dir':str(USER_ROOT),
                          'kindlegen':find_kindlegen(),'kfx':'native Python','calibre':'not used',
                          'mtp_devices':device_count,'bundled_fonts':len(list(available_fonts(APP_ROOT/'missing-fonts'))),
                          'reading_presets':len(PRESETS),'clippings_export':['enex','md']},ensure_ascii=False))
        return 0
    if args.worker or args.convert:
        if hasattr(sys.stdout,'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8',errors='replace')
            sys.stderr.reconfigure(encoding='utf-8',errors='replace')
        channel=sys.stdout
        def emit(event,**data):
            channel.write(json.dumps({'event':event,**data},ensure_ascii=False)+'\n')
            channel.flush()
        try:
            from lume.engine import convert
            from lume.model import Layout,Context
            job=json.loads(Path(args.worker).read_text(encoding='utf-8')) if args.worker else {
                'source':args.convert,'output_dir':args.output,'format':args.to,'layout':{'font_path':args.font,'cover_path':args.cover,'kfx_mode':args.kfx_mode}}
            logging.basicConfig(stream=sys.stderr,level=logging.WARNING)
            sending=bool(job.get('send_to'))
            context=Context(lambda p,t:emit('progress',percent=int(p*.85) if sending else p,text=t))
            if args.worker:
                context.job_id=Path(args.worker).stem
                context.cancel_file=Path(args.worker).with_suffix('.cancel')
            if job.get('operation')=='send':
                from lume.devices import Device,send_file
                import time
                source=Path(job['source']).resolve()
                started=time.perf_counter()
                def direct_progress(text):
                    context.check()
                    emit('progress',percent=50,text=text)
                with contextlib.redirect_stdout(sys.stderr):
                    device_path=send_file(source,Device(**job['send_to']),direct_progress)
                result={'source':str(source),'output':str(source),'title':source.stem,'chapters':0,
                        'seconds':time.perf_counter()-started,'size':source.stat().st_size,'warnings':[],
                        'device_path':device_path,'operation':'send'}
                emit('done',result=result)
                return 0
            layout=Layout(**job.get('layout',{}))
            if sending and job['format'].lower().lstrip('.')=='kfx':
                from lume.devices import Device,kfx_mode_for_device
                layout.kfx_mode=kfx_mode_for_device(layout.kfx_mode,Device(**job['send_to']))
            with contextlib.redirect_stdout(sys.stderr):
                result=convert(job['source'],job['output_dir'],job['format'],layout,
                               context,job.get('kindlegen',''))
            result=asdict(result)
            if sending:
                emit('converted',result=result)
                from lume.devices import Device,send_file
                def transfer_progress(text):
                    context.check()
                    emit('progress',percent=90,text=text)
                try:
                    context.check()
                    with contextlib.redirect_stdout(sys.stderr):
                        result['device_path']=send_file(result['output'],Device(**job['send_to']),transfer_progress)
                    emit('progress',percent=100,text='转换并发送完成')
                except Exception as exc:
                    result['send_error']=str(exc)
            emit('done',result=result)
            return 0
        except Exception as exc:
            emit('error',message=str(exc))
            traceback.print_exc(file=sys.stderr)
            return 1
    from lume.ui import launch
    return launch(args.open)

if __name__=='__main__':
    raise SystemExit(main())
