"""Best-effort USB identity; never guess a model from a drive letter alone."""
import ctypes
import json
import os
import re
import subprocess
import time
from .presets import identify_model

_cache={}


def usb_model(drive,name=''):
    known=identify_model(name)
    if known or os.name!='nt':return known
    match=re.fullmatch(r'([A-Za-z]):[\\/]?',str(drive))
    if not match:return ''
    letter=match[1].upper()+':'
    volume_id=ctypes.c_ulong()
    ctypes.windll.kernel32.GetVolumeInformationW(letter+'\\',None,0,ctypes.byref(volume_id),None,None,None,0)
    key=(letter,volume_id.value)
    cached=_cache.get(key)
    if cached and time.monotonic()-cached[0]<60:return cached[1]
    script=("$ErrorActionPreference='Stop'; [Console]::OutputEncoding=[System.Text.Encoding]::UTF8; "
            "$d=Get-CimInstance Win32_LogicalDisk -Filter \"DeviceID='"+letter+"'\"; "
            "$p=$d|Get-CimAssociatedInstance -Association Win32_LogicalDiskToPartition; "
            "$p|Get-CimAssociatedInstance -Association Win32_DiskDriveToDiskPartition|"
            "Select-Object SerialNumber,PNPDeviceID,Model|ConvertTo-Json -Compress")
    result=''
    try:
        run=subprocess.run(['powershell.exe','-NoProfile','-NonInteractive','-Command',script],
                           capture_output=True,timeout=5,creationflags=subprocess.CREATE_NO_WINDOW)
        rows=json.loads(run.stdout.decode('utf-8-sig'))
        for item in rows if isinstance(rows,list) else [rows]:
            candidates=[item.get('SerialNumber',''),(item.get('PNPDeviceID') or '').split('\\')[-1].split('&')[0]]
            for serial in candidates:
                result=identify_model(item.get('Model') or '',serial or '')
                if result:break
            if result:break
    except (OSError,subprocess.TimeoutExpired,ValueError,TypeError,AttributeError):pass
    _cache[key]=(time.monotonic(),result)
    return result