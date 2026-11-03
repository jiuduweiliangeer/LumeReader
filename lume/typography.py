from __future__ import annotations
import hashlib
import io
import uuid
from pathlib import Path
import re
import cssselect2
import tinycss2
from lxml import etree
from .model import ConversionError, Resource
from .util import body_root, fragment, resolve_href

def declarations(text):
    return {d.lower_name: (tinycss2.serialize(d.value).strip(), d.important)
            for d in tinycss2.parse_declaration_list(text,skip_comments=True,skip_whitespace=True)
            if d.type == 'declaration'}

def css_for_chapter(book, chapter):
    seen = set()
    def expand(text, base):
        def replace(match):
            target = match.group(1)
            resolved = resolve_href(base,target)
            if resolved and resolved[0] in book.resources and resolved[0] not in seen:
                seen.add(resolved[0])
                return expand(book.resources[resolved[0]].data.decode('utf-8',errors='replace'),resolved[0])
            return ''
        return re.sub(r'@import\s+(?:url\(\s*)?["\']([^"\']+)["\']\s*\)?\s*;',replace,text,flags=re.I)
    return expand(chapter.css,chapter.href)

def matcher_for(css):
    matcher = cssselect2.Matcher()
    def add(rules):
        for rule in rules:
            if rule.type == 'qualified-rule':
                try:
                    decl = declarations(tinycss2.serialize(rule.content))
                    for selector in cssselect2.compile_selector_list(tinycss2.serialize(rule.prelude)):
                        matcher.add_selector(selector,decl)
                except cssselect2.SelectorError:
                    pass
            elif rule.type == 'at-rule' and rule.lower_at_keyword in ('media','supports') and rule.content:
                add(tinycss2.parse_rule_list(rule.content,skip_comments=True,skip_whitespace=True))
    add(tinycss2.parse_stylesheet(css,skip_comments=True,skip_whitespace=True))
    return matcher

def computed_style(wrapper, matcher, inherited=None):
    result = dict(inherited or {})
    ranked = {}
    for specificity, order, pseudo, decl in matcher.match(wrapper):
        if pseudo:
            continue
        for name,(value,important) in decl.items():
            rank = (int(important),0,*specificity,order)
            if name not in ranked or rank >= ranked[name][0]:
                ranked[name] = (rank,value)
    for name,(value,important) in declarations(wrapper.etree_element.get('style','')).items():
        rank = (int(important),1,0,0,0,0)
        if name not in ranked or rank >= ranked[name][0]:
            ranked[name] = (rank,value)
    result.update((key,value[1]) for key,value in ranked.items())
    return result

def put_style(node, updates):
    current = declarations(node.get('style',''))
    current.update({key:(str(value),True) for key,value in updates.items()})
    node.set('style',';'.join(f'{key}:{value}' + (' !important' if important else '')
                             for key,(value,important) in current.items()))

def normalized_book(book, layout, ctx, cache_dir):
    layout.validate()
    chars = set('0123456789 目录正文' + book.title + book.author)
    total = max(len(book.chapters),1)
    for index,chapter in enumerate(book.chapters):
        if index % 10 == 0:
            ctx.update(22+24*index/total,f'整理排版 · {index+1}/{len(book.chapters)} 章')
        root = body_root(chapter.body)
        root.tag = 'body'
        styles = matcher_for(css_for_chapter(book,chapter))
        effective = {}
        for wrapper in cssselect2.ElementWrapper.from_html_root(root).iter_subtree():
            node = wrapper.etree_element
            if not isinstance(node.tag,str):
                continue
            parent = effective.get(node.getparent(),{})
            inherited = {k:parent[k] for k in ('text-indent','text-align') if k in parent}
            computed = computed_style(wrapper,styles,inherited)
            effective[node] = computed
            if node.text:
                chars.update(node.text)
            if node.tail:
                chars.update(node.tail)
            if layout.font_path and node.tag not in ('svg','path','math'):
                put_style(node,{'font-family':'"LumeEmbedded"'})
            if node.tag == 'p':
                attrs = {'line-height':f'{layout.line_height:g}',
                         'margin-top':'0', 'margin-bottom':f'{layout.paragraph_gap:g}em'}
                protected = any(a.tag in ('li','pre','table','blockquote','figcaption') for a in node.iterancestors())
                special = computed.get('text-align') in ('center','right') or re.search(r'(?:noindent|caption|poem|verse)',node.get('class',''),re.I)
                if not protected and not special:
                    attrs['text-align'] = layout.alignment
                    existing = computed.get('text-indent','0')
                    match = re.match(r'^\s*([+-]?\d*\.?\d+)',existing)
                    positive = bool(match and float(match.group(1)) > 0)
                    if layout.indent_mode == 'none':
                        attrs['text-indent'] = '0'
                    elif layout.indent_mode == 'all' or not positive:
                        attrs['text-indent'] = f'{layout.indent:g}em'
                    else:
                        attrs['text-indent'] = existing
                    # Existing full-width / manual spaces must not double the CSS indent.
                    first_text = next((e for e in node.iter() if e.text and e.text.strip()),None)
                    if first_text is not None and re.match(r'^[ \t\u3000\u00a0]{2,}',first_text.text):
                        first_text.text = first_text.text.lstrip(' \t\u3000\u00a0')
                put_style(node,attrs)
            elif node.tag in ('h1','h2','h3','h4','h5','h6'):
                put_style(node,{'text-indent':'0','line-height':'1.35'})
        chapter.body = fragment(root)
    if layout.font_path:
        # Replacing the font also replaces old embedded faces. Leaving two
        # different subsets with the same internal name can crash KindleGen.
        def without_faces(css):
            return re.sub(r'@font-face\s*\{[^{}]*\}', '', css, flags=re.I)
        for chapter in book.chapters:
            chapter.css=without_faces(chapter.css)
        for key,resource in list(book.resources.items()):
            if 'font' in resource.media_type or resource.href.lower().endswith(('.ttf','.otf','.woff','.woff2')):
                del book.resources[key]
            elif resource.media_type=='text/css':
                book.resources[key]=Resource(resource.href,without_faces(resource.data.decode('utf-8',errors='replace')).encode('utf-8'),resource.media_type)
        ctx.update(48,'嵌入字体' + (' · 生成字形子集' if layout.subset_font else ''))
        embed_font(book,layout,chars,Path(cache_dir),ctx)
    if not book.chapters:
        raise ConversionError('未发现可转换的正文。')
    return book

def embed_font(book, layout, chars, cache_dir, ctx):
    from fontTools.ttLib import TTFont
    from fontTools import subset
    path = Path(layout.font_path)
    if path.stat().st_size > 64*1024**2:
        raise ConversionError('字体文件超过 64 MB，请选择 TTF 或 OTF 字体。')
    original = path.read_bytes()
    try:
        font = TTFont(io.BytesIO(original),recalcTimestamp=False)
    except Exception as exc:
        raise ConversionError(f'无法读取字体：{path.name}。请选择单个 TTF/OTF 文件。') from exc
    try:
        cmap = font.getBestCmap() or {}
        needed = {ord(c) for c in chars if not c.isspace()}
        missing = needed - set(cmap)
        if missing:
            book.warnings.append(f'字体「{path.stem}」缺少 {len(missing)} 个字符，阅读器可能对这些字符使用回退字体。')
        book.font_family = next((n.toUnicode() for n in font['name'].names if n.nameID in (16,1)),path.stem)
        ctx.check()
        if layout.subset_font:
            key = hashlib.sha256(original + ''.join(sorted(chars)).encode('utf-8') + b'lume-subset-v1').hexdigest()
            cache_dir.mkdir(parents=True,exist_ok=True)
            cached = cache_dir/(key+'.font')
            if cached.is_file():
                data = cached.read_bytes()
            else:
                options = subset.Options()
                options.layout_features = ['*']
                options.recalc_timestamp = False
                subsetter = subset.Subsetter(options=options)
                subsetter.populate(unicodes=needed | set(range(32,127)))
                subsetter.subset(font)
                output = io.BytesIO()
                font.save(output)
                data = output.getvalue()
                tmp = cached.with_name(cached.name + '.' + uuid.uuid4().hex + '.tmp')
                tmp.write_bytes(data)
                tmp.replace(cached)
        else:
            data = original
    finally:
        font.close()
    book.embedded_font = data
    suffix = '.otf' if data[:4] == b'OTTO' else '.ttf'
    href = 'fonts/selected'+suffix
    book.resources[href] = Resource(href,data,'font/otf' if suffix == '.otf' else 'font/ttf')

def stylesheet(layout, book):
    family = "font-family: LumeEmbedded, serif;" if book.embedded_font else ""
    font = next((r for r in book.resources.values() if r.href.startswith('fonts/selected')),None)
    face = ('@font-face { font-family: "LumeEmbedded"; font-style: normal; font-weight: normal; '
            'src: url("../'+font.href+'"); }\n') if font else ''
    return face + f'''
html {{ font-size: 100%; }}
body {{ {family} font-size: {layout.font_size/18:g}em; line-height: {layout.line_height:g}; margin: 0; padding: 0; }}
p {{ orphans: 2; widows: 2; }}
h1 {{ font-size: 1.45em; margin: 1.6em 0 1.1em; text-align: left; }}
h2 {{ font-size: 1.25em; margin: 1.3em 0 0.9em; }}
img, svg {{ max-width: 100%; height: auto; }}
a {{ color: inherit; }}
pre {{ white-space: pre-wrap; }}
'''
