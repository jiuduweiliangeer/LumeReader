"""Recoverable removal of generated outputs. Imported originals are protected."""
from pathlib import Path
import json,shutil
from .devices import digest
from .util import reserve_output

def trash_outputs(results,destination,progress=None):
    progress=progress or (lambda text:None)
    destination=Path(destination).resolve()
    destination.mkdir(parents=True,exist_ok=True)
    moved,errors=[],[]
    seen=set()
    receipt={'moved':moved,'errors':errors}
    manifest=destination/'receipt.json'
    def save():
        temp=manifest.with_suffix('.json.part')
        temp.write_text(json.dumps(receipt,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(manifest)
    for record in results:
        output=Path(record['output'])
        source=Path(record['source'])
        resolved=output.resolve()
        if resolved in seen: continue
        seen.add(resolved)
        if record.get('operation')=='send' or resolved==source.resolve() or not output.exists():
            continue
        try:
            if output.is_symlink() or not output.is_file():
                raise ValueError('文件位置已变化，未删除')
            if output.stat().st_size!=record['size']:
                raise ValueError('文件已修改，未删除')
            backup=reserve_output(destination,output.stem,output.suffix.lstrip('.'))
            if destination not in backup.resolve().parents:
                raise ValueError('回收目录无效')
            progress('备份转换结果：'+output.name)
            shutil.copyfile(output,backup)
            value=digest(output)
            if digest(backup)!=value:
                raise ValueError('备份校验不一致，未删除')
            moved.append({'source':str(resolved),'backup':str(backup),'sha256':value,'removed':False})
            save()
            output.unlink()
            moved[-1]['removed']=True
            save()
        except Exception as exc:
            errors.append({'output':str(output),'message':str(exc)})
            save()
    save()
    return receipt
