import json
import os
import shutil
from pathlib import Path
import subprocess
import sys
import uuid
if os.name=="nt":
    import comtypes  # Import on the GUI thread; worker threads own a separate COM lifetime.
from PyQt6.QtCore import QObject, QThread, QProcess, QTimer, pyqtSignal
from .storage import ROOT
from .paths import APP_ROOT,FROZEN,EXE_ROOT

class Task(QThread):
    done=pyqtSignal(object)
    failed=pyqtSignal(str)
    progress=pyqtSignal(str)
    def __init__(self,fn,parent=None):
        super().__init__(parent)
        self.fn=fn
    def run(self):
        # Keep COM alive until the callback has returned and released its local
        # WPD interfaces. Session.__exit__ alone runs before those locals die.
        if os.name=='nt': comtypes.CoInitialize()
        try:
            try: self.done.emit(self.fn(self.progress.emit))
            except Exception as e: self.failed.emit(str(e))
        finally:
            if os.name=='nt': comtypes.CoUninitialize()

class QueueRunner(QObject):
    started=pyqtSignal(int)
    progress=pyqtSignal(int,str)
    converted=pyqtSignal(int,dict)
    success=pyqtSignal(int,dict)
    failure=pyqtSignal(int,str)
    finished=pyqtSignal(bool)
    def __init__(self,parent=None):
        super().__init__(parent)
        self.process=None
        self.todo=[]
        self.cancelled=False
        self.index=0
    def start(self,jobs):
        if self.process: return
        self.todo=[(job.get('_row',index),job) for index,job in enumerate(jobs)]
        self.total=len(jobs)
        self.complete=0
        self.cancelled=False
        self.next()
    def next(self):
        if not self.todo or self.cancelled:
            self.process=None
            self.finished.emit(self.cancelled)
            return
        self.index,self.job=self.todo.pop(0)
        folder=ROOT/'.runtime'/'requests'
        folder.mkdir(parents=True,exist_ok=True)
        self.request=folder/(uuid.uuid4().hex+'.json')
        self.request.write_text(json.dumps(self.job,ensure_ascii=False),encoding='utf-8')
        self.buffer=b''
        self.error_text=''
        self.result=None
        self.message=''
        self.process=QProcess(self)
        if FROZEN:
            self.process.setProgram(str(EXE_ROOT/'LumeWorker.exe'))
            self.process.setArguments(['--worker',str(self.request)])
        else:
            python=Path(sys.executable)
            if python.name.lower()=='pythonw.exe': python=python.with_name('python.exe')
            self.process.setProgram(str(python))
            self.process.setArguments(['-u',str(APP_ROOT/'run.py'),'--worker',str(self.request)])
        self.process.setWorkingDirectory(str(ROOT))
        self.process.readyReadStandardOutput.connect(self.read)
        self.process.readyReadStandardError.connect(self.errors)
        self.process.finished.connect(self.end)
        self.process.errorOccurred.connect(self.process_error)
        self.started.emit(self.index)
        self.process.start()
    def read(self):
        if not self.process: return
        self.buffer+=bytes(self.process.readAllStandardOutput())
        while b'\n' in self.buffer:
            line,self.buffer=self.buffer.split(b'\n',1)
            try: event=json.loads(line.decode('utf-8'))
            except (ValueError,UnicodeError): continue
            if event['event']=='progress':
                self.progress.emit(int(100*(self.complete+event['percent']/100)/self.total),
                                   f'{self.complete+1}/{self.total} · '+event['text'])
            elif event['event']=='converted': self.converted.emit(self.index,event['result'])
            elif event['event']=='done': self.result=event['result']
            elif event['event']=='error': self.message=event['message']
    def errors(self):
        if self.process:
            self.error_text=(self.error_text+bytes(self.process.readAllStandardError()).decode('utf-8',errors='replace'))[-16000:]
    def process_error(self,error):
        if error==QProcess.ProcessError.FailedToStart:
            self.message='无法启动转换工作进程'
            self.end(-1,QProcess.ExitStatus.CrashExit)
    def end(self,code,status):
        if not self.process: return
        self.read()
        self.errors()
        logs=ROOT/'data'/'logs'
        logs.mkdir(parents=True,exist_ok=True)
        (logs/(self.request.stem+'.log')).write_text(self.error_text,encoding='utf-8')
        if self.result:
            self.success.emit(self.index,self.result)
        else:
            self.failure.emit(self.index,'已取消' if self.cancelled else self.message or self.error_text[-2000:] or '工作进程意外结束')
        # Clean only this worker's owned staging paths after a hard cancellation.
        shutil.rmtree(ROOT/'.runtime'/'jobs'/self.request.stem,ignore_errors=True)
        partial=Path(self.job['output_dir'])/('.lume-'+self.request.stem+'.part')
        partial.unlink(missing_ok=True)
        self.request.unlink(missing_ok=True)
        self.request.with_suffix('.cancel').unlink(missing_ok=True)
        self.process.deleteLater()
        self.process=None
        self.complete+=1
        QTimer.singleShot(30,self.next)

    def cancel(self):
        if self.cancelled: return
        self.cancelled=True
        self.todo=[]
        if self.process:
            self.request.with_suffix('.cancel').touch()
            process=self.process
            def force_stop():
                if self.process is process and process.state()!=QProcess.ProcessState.NotRunning:
                    pid=int(process.processId())
                    if os.name=='nt' and pid:
                        # Detached helper; never block the GUI event loop on taskkill.
                        subprocess.Popen(['taskkill','/PID',str(pid),'/T','/F'],
                                         stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                                         creationflags=subprocess.CREATE_NO_WINDOW)
                    process.kill()
            QTimer.singleShot(2500,force_stop)
