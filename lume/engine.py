from __future__ import annotations
import os
from pathlib import Path
import shutil
import tempfile
import time
from .model import Layout, Context, Result, ConversionError
from .readers import read_book, INPUTS
from .typography import normalized_book
from .writers import OUTPUTS, write_epub, write_txt, write_html, write_fb2, write_pdf
from .util import safe_name

from .paths import USER_ROOT as ROOT

def publish(partial,directory,name,suffix):
    """Publish atomically without replacing an existing book."""
    for i in range(10000):
        target=directory/(safe_name(name)+(f' ({i})' if i else '')+'.'+suffix)
        try:
            if os.name=='nt':
                os.rename(partial,target) # Windows rename fails if destination exists.
            else:
                os.link(partial,target)
                partial.unlink()
            return target
        except FileExistsError:
            continue
    raise ConversionError('输出目录同名文件过多。')

def convert(source,output_dir,output_format='epub',layout=None,ctx=None,kindlegen=''):
    source=Path(source).resolve()
    layout=layout or Layout()
    ctx=ctx or Context()
    started=time.perf_counter()
    layout.validate()
    output_format=output_format.lower().lstrip('.')
    if output_format not in OUTPUTS:
        raise ConversionError('不支持的输出格式：'+output_format)
    if not source.is_file():
        raise ConversionError('源文件不存在：'+str(source))
    if source.suffix.lower().lstrip('.') not in INPUTS:
        raise ConversionError('不支持的输入文件。')
    if source.stat().st_size>512*1024**2:
        raise ConversionError('单本书上限为 512 MB。')
    import re
    if not re.fullmatch('[0-9a-f]{32}',ctx.job_id):
        raise ConversionError('无效任务标识。')
    workroot=ROOT/'.runtime'/'jobs'/ctx.job_id
    workroot.mkdir(parents=True,exist_ok=False)
    output_dir=Path(output_dir).resolve()
    partial=output_dir/('.lume-'+ctx.job_id+'.part')
    try:
        with tempfile.TemporaryDirectory(prefix='book-',dir=str(workroot)) as tmp:
            ctx.update(2,'准备读取书籍')
            book=read_book(source,layout,ctx,tmp)
            from .covers import apply_cover,remember
            apply_cover(book,layout.cover_path)
            normalized_book(book,layout,ctx,ROOT/'.cache'/'fonts')
            ctx.update(54,'生成 '+output_format.upper())
            staged=Path(tmp)/('final.'+output_format)
            if output_format in ('mobi','azw3'):
                from .kindle_formats import compile_kindle
                compile_kindle(book,staged,layout,ctx,tmp,kindlegen)
            elif output_format=='kfx':
                from .kindle_formats import write_kfx
                write_kfx(book,staged,layout,ctx)
            else:
                {'epub':write_epub,'txt':write_txt,'html':write_html,
                 'fb2':write_fb2,'pdf':write_pdf}[output_format](book,staged,layout,ctx)
            ctx.check()
            if not staged.is_file() or not staged.stat().st_size:
                raise ConversionError('转换没有生成有效文件。')
            output_dir.mkdir(parents=True,exist_ok=True)
            with open(staged,'rb') as src,open(partial,'xb') as dest:
                while True:
                    ctx.check()
                    block=src.read(1024**2)
                    if not block:
                        break
                    dest.write(block)
                dest.flush()
                os.fsync(dest.fileno())
            ctx.check()
            output=publish(partial,output_dir,source.stem,output_format)
            try:
                remember(book,output)
            except Exception as exc:
                book.warnings.append('封面已嵌入，但缩略图缓存失败：'+str(exc))
            seconds=time.perf_counter()-started
            result=Result(str(source),str(output),book.title,len(book.chapters),round(seconds,3),
                          output.stat().st_size,list(dict.fromkeys(book.warnings)))
            ctx.update(100,f'完成 · {seconds:.2f} 秒')
            return result
    finally:
        if partial.exists():
            partial.unlink()
        shutil.rmtree(workroot,ignore_errors=True)
