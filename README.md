<p align="center"><img src="lume/assets/lume.png" width="88" alt="Lume Reader 图标"></p>

# 轻阅 · Lume Reader

Windows 电子书转换与 Kindle 书架管理工具，使用 Python / PyQt6 开发。支持批量转换、字体与封面设置、USB / MTP 有线传输，运行时不调用 Calibre。

[下载 Windows 安装包](https://github.com/jiuduweiliangeer/LumeReader/releases/latest) · [完整使用说明](docs/USAGE.md) · [构建安装包](docs/BUILD.md) · [开源协议](LICENSE.md)

## v1.1.0 更新：新增与修复

1. **兼容与界面修复**：增加 Voyage 等旧款 Kindle 的 KFX 书架封面兼容与封面缓存恢复；修复帮助页中文正文丢失、Markdown 表格和图片显示；主导航可收起为图标栏，并记住展开状态。
2. **逐本设置封面**：批量添加时可勾选“为每本书单独设置封面”，按向导逐本选图或保留原封面；也可编辑已加入队列的书籍。直接发送保持原文件。
3. **设备预设与格式推荐**：提供七种阅读预设，连接 Kindle 后在转换前显示推荐格式与原因，特殊机型自动切换，也可手动指定型号和格式。内置霞鹜文楷、汇文明朝、悠哉字体，保留自备字体入口。
4. **摘抄管理与导出**：读取或导入 My Clippings.txt，按书籍分类查看划线、笔记和书签，使用窄书名列表与宽阅读区，支持搜索、分页与重复导入去重；检测本机笔记软件，按目标自动转换并导入或打开文件导入流程，也可保存为 ENEX / Markdown。[查看摘抄界面示例](docs/images/clippings.png)。

验证：105 项自动测试通过，独立 EXE 完成 56 次格式转换（其中 49 次为非 TXT 输入互转）；ENEX / ENML 通过官方 DTD 校验。Voyage 真机书架显示仍需设备复核，旧 PDOC KFX 请重新转换并发送。详见 [更新记录](docs/CHANGELOG.md) 和 [Voyage 封面说明](docs/VOYAGE_COVERS.md)。

![书籍工作台](docs/images/workspace.png)

## 安装与功能介绍

- Windows 10 / 11，64 位。下载 Release 中的 `LumeReader-1.1.0-Setup-x64.exe` 并运行。
- 安装包已包含 Python、PyQt6 和转换所需的开源组件，**不用安装 Python、Calibre 或 Calibre 插件**。
- **TXT、EPUB、KFX、PDF、HTML、FB2 之间互转，安装本软件即可使用。**
- **MOBI / AZW / AZW3 导入后转为上述六种格式，也不需要 KindleGen。**
- **只有导出 MOBI / AZW3 需要额外提供 KindleGen**，详见下面的表格和官方下载链接。
- Kindle Previewer 是可选的桌面预览工具；KFX 转换本身不依赖它。

当前安装包未做代码签名。Release 同时提供 `SHA256SUMS-1.1.0.txt`，可使用 PowerShell 的 `Get-FileHash` 核对文件。

## 格式与额外依赖

“直接使用”指已经安装 Lume Reader。转换依赖由**目标格式**决定；原文件必须未加密、内容完整。

| 格式 | 导入本格式 | 导出为此格式 | 额外安装 | 主要限制 |
|---|---|---|---|---|
| TXT | 直接使用 | 直接使用 | 无 | 无法保存字体、图片、精确行距或可点击目录 |
| EPUB | 直接使用 | 直接使用 | 无 | 支持导航目录、封面、嵌入字体与图片 |
| KFX | 直接使用 | 直接使用 | 无 | 支持完整、未加密的单文件 KFX；缺失分包无法补全 |
| PDF | 直接使用 | 直接使用 | 无 | 文本可重排；扫描页保留为图片，无 OCR；输出包含目录书签 |
| HTML / HTM | 直接使用 | 直接使用，输出 HTML | 无 | 单文件输出内嵌图片与字体 |
| FB2 | 直接使用 | 直接使用 | 无 | 支持章节与图片；字体、行距受格式及阅读器限制 |
| MOBI | 直接使用 | **需要 KindleGen** | 仅导出需要外部编译器 | 输出 MOBI7 + KF8；旧 MOBI7 不支持嵌入字体 |
| AZW3 | 直接使用 | **需要 KindleGen** | 仅导出需要外部编译器 | KF8 格式，支持封面、目录及出版商字体 |
| AZW | 直接使用（MOBI/KF8 类型） | 不导出 AZW | 无 | 可转其他目标格式；并非所有 .azw 都是同一种容器 |
| KFX-ZIP / KPF | 直接使用 | 不导出 | 无 | 只读取可解析且完整的未加密内容 |
| DOCX | 直接使用 | 不导出 | 无 | 导入正文、标题和图片，复杂表格会简化 |
| Markdown / MD | 直接使用 | 不导出 | 无 | 导入文字与章节标题 |

例如：`MOBI → KFX`、`AZW3 → EPUB`、`EPUB → PDF`、`PDF → EPUB` 均可直接转换；`EPUB → AZW3`、`KFX → MOBI` 才需要 KindleGen。支持格式不代表复杂版式可以无损互转。

### 可选软件与官方下载链接

| 软件 / 文件 | 哪些情况需要 | 官方来源 | 配置方式 |
|---|---|---|---|
| Amazon KindleGen (`kindlegen.exe`) | **导出 MOBI / AZW3 必需**；其他目标格式不需要 | Amazon 已将工作流转向 [Kindle Previewer 官方页面](https://kdp.amazon.com/en_US/help/topic/G202131170)；本机验证使用 Previewer 3 发行版附带的 KindleGen | 自动查找常见位置；也可在“设置与帮助 → MOBI / AZW3 编译器”选择该文件 |
| Amazon Kindle Previewer | 可选，用于电脑上检查 EPUB 排版 | [Amazon 官方下载与说明](https://kdp.amazon.com/en_US/help/topic/G202131170) | 安装后用它打开生成的 EPUB；并非 KFX 转换依赖 |
| TTF / OTF 字体 | 可选，内置字体之外希望自行选用时 | 使用自己有权使用的字体，例如 [霞鹜文楷官方项目](https://github.com/lxgw/LxgwWenKai) | 在阅读样式中选择字体，或设置字体文件夹 |

**KindleGen 与 Kindle Previewer 不是同一个依赖。** Amazon 后续发行版可能调整内置文件，不能保证最新 Previewer 一定带有 `kindlegen.exe`。软件实际检测的是该编译器；如果安装后没有它，EPUB / KFX / PDF 等仍可直接转换。本项目不捆绑 KindleGen，也不提供第三方修改版编译器。

## 使用流程

1. “添加书籍”支持多选文件、导入整个文件夹，也可拖入文件 / 文件夹。
2. 勾选要处理的书籍。“全选”复选框支持全选和取消全选。
3. 按需选择输出格式、目录、排版、TTF / OTF 字体和封面。
4. 点击对应操作：

| 操作 | 结果 | 是否应用排版 / 字体 / 封面 |
|---|---|---|
| **直接发送** | 原文件直接传输到当前 Kindle | 否，保留原文件内容 |
| **仅转换** | 转换后保存在电脑 | 是 |
| **转换并发送** | 转换完成后自动发送到 Kindle | 是 |

批量任务逐本处理，一本失败后继续下一本。发送失败时保留本地转换结果。同名输出自动编号，不覆盖原始输入。

### 设备推荐、预设和逐本封面

默认输出 KFX。连接设备后，**转换前**在输出格式下方显示推荐及原因，特殊机型自动切换；用户仍可自行选择。自动检测不到型号时，可在设备栏手动指定。

| 设备 | 默认推荐 | 说明 |
|---|---|---|
| Paperwhite、Oasis、Scribe、较新的入门 Kindle | KFX | USB 盘符同步旧款书架缩略图，MTP 使用个人文档模式 |
| Voyage | 已配置 KindleGen 时 AZW3，否则 KFX 旧款封面兼容模式 | KFX 需要通过软件发送来同步独立缩略图 |
| Paperwhite 1、Kindle 3 / 4 / Touch | AZW3；无 KindleGen 时 PDF | 不推荐 KFX |
| Kindle 1 / 2 / DX | MOBI；无 KindleGen 时 PDF | 不使用 KFX 或 AZW3 |

阅读预设包含 **Paperwhite 6、Voyage、6 英寸入门版、Paperwhite 5、Oasis、Scribe 10.2 / 11 英寸**。可自由调整行距、段距、缩进和字号；PDF 页面尺寸跟随预设。切换预设保留已选字体和封面。

批量添加前勾选 **“为每本书单独设置封面”**，即可逐本选图或保留原封面。已添加书籍可在“封面”页点击“逐本设置选中书籍的封面”。取消向导不会丢失队列；开始转换时会继续引导尚未确认的书籍。直接发送不改封面。

内置 **霞鹜文楷、汇文明朝（符号修正版）、悠哉字体**，安装后可直接选择。仓耳今楷、京华老宋、上图东观体等自备字体仍可从本地字体目录选择。字体来源和分发范围见 [字体说明](docs/FONTS.md)。

### 摘抄

侧栏“摘抄”支持从当前 Kindle 的 `My Clippings.txt` 读取，或导入电脑上的副本。按书名与作者分组，区分划线、笔记、书签，支持全文搜索和分页；重复导入自动去重，原始文件不修改。

点击 **“导入笔记软件”**，软件检测本机已安装的适配应用；选择目标后自动匹配格式。左侧仅显示书名，点击后在主栏阅读摘抄。主导航可收起，底部范围选择器与操作按钮居中。

| 目标 | 自动转换与导入方式 | 需要用户设置的内容 |
|---|---|---|
| Obsidian | 自动生成每本书的 Markdown，直接写入所选笔记库并可打开该笔记 | 自动读取已配置的笔记库列表，也可手动选库 |
| Logseq 文件图谱 | 自动生成 Markdown 并写入现有图谱的 pages 目录 | 指定文件图谱目录；不直接写入数据库图谱 |
| Joplin | 通过本地 Data API 自动创建笔记本与笔记 | 首次启用内置 Web Clipper 服务，并在 Joplin 中允许请求；无需浏览器插件 |
| Evernote / 印象笔记 | 自动生成 ENEX；匹配系统文件关联时调用目标软件接收文件 | 若没有匹配的文件关联，在已打开的软件中选择生成文件；是否完成以目标软件为准 |
| Notion | 自动生成 Markdown ZIP，打开软件与文件夹 | 在 Notion“导入”中选择生成文件 |
| 其他软件 | 自动生成逐本 Markdown 文件 | 指定保存目录，按目标软件支持的方式读取 |

导入保留已有笔记，不覆盖同名文件。也可使用 **“保存为文件”** 菜单直接导出 ENEX 或 Markdown，范围可选当前书籍或全部书籍。未检测到应用时，仍可指定 Obsidian / Logseq 的现有库目录。程序不会替用户安装插件。

![摘抄界面示例](docs/images/clippings.png)

![笔记软件选择窗口](docs/images/note-transfer.png)

以上截图使用演示数据；实际软件列表根据本机安装情况检测。

### Kindle 书架

连接并解锁 Kindle 后，书架显示设备书籍、格式、所在目录和剩余空间。支持搜索、筛选、勾选、保存到电脑及批量删除。删除前先备份原文件，批注与阅读记录文件保留。

![Kindle 书架](docs/images/kindle-library.png)

| 有线发送能力 | 格式 |
|---|---|
| 可直接发送 | 完整单文件 KFX、AZW3、MOBI、MOBI/KF8 型 AZW、PDF、TXT |
| 不能直接放入 documents 阅读 | EPUB 等；先转为设备支持的格式，或使用 [Amazon Send to Kindle](https://www.amazon.com/sendtokindle) |

支持传统 USB 盘符和新款 Kindle 的 MTP。本项目不修改 Kindle 原生收藏夹。发送时会同步可用封面缩略图并回读校验；设备最终显示受固件和缓存影响。

**Kindle Voyage / 旧款封面：** 1.1.0 起，“转换并发送”的 KFX 自动模式会对 USB 盘符设备生成 EBOK 书籍，并同步书架缩略图；MTP 设备继续使用 PDOC 个人文档。“仅转换”给 Voyage 使用时，在“设置 → KFX 封面兼容”选“旧款 Kindle / Voyage”，随后用软件发送。直接拖入 documents 不会同步独立缩略图。

已用旧版生成的 PDOC KFX，需要以旧款模式重新转换并发送；“直接发送”保留原文件，无法改变它的文档类型。USB 设备若联网后封面消失，重新连接并刷新软件书架，会恢复本软件缓存且仍有关联书籍的缩略图。恢复只处理封面，不修改书籍、批注或阅读记录。固件限制及操作步骤见 [Voyage 封面说明](docs/VOYAGE_COVERS.md)。

### 排版与封面

KPW6 默认预设：首行缩进 2 字、行距 1.65、段后距 0.35em，参数均可修改。EPUB / AZW3 使用相对字号，阅读器字号设置仍可调整。

嵌入字体默认做字形子集化。Kindle 选择“出版商字体”可使用书内字体；字体缺字会提示回退。PDF 为固定页面，TXT 无法嵌入字体。封面支持自选图片。

![封面设置](docs/images/cover.png)

### 已完成记录

支持全选、再次发送、打开结果和删除。可只删记录，或将转换输出先备份到回收目录后移除；不会删除原始导入文件。

![已完成记录](docs/images/completed.png)

## 数据与隐私

书籍在本机处理，不上传书籍，不要求账号，不内置遥测。

安装版数据目录为 `%LOCALAPPDATA%\LumeReader`：`output` 保存默认输出，`data` 保存设置与历史，`data/device-backups` 保存设备删除备份，`data/local-trash` 保存已移除的输出。卸载保留这些用户文件。

截图使用自编示例内容与模拟设备列表，不包含真实设备书库、私人字体或测试小说。

## 验证与限制

- 开发阶段通过 45 项自动测试和 54 组跨格式转换检查；独立 EXE 另通过 56 次转换验证，其中 49 组使用 EPUB、MOBI、AZW3、KFX、PDF、HTML、FB2 等非 TXT 输入。
- Kindle Previewer 已核对代表性 EPUB 的封面、目录跳转、标题和正文；并非所有格式均逐页人工检查。
- 部分 AZW3 被 Previewer 以旧版 KindleGen / 第三方文件为由拒绝直接预览；回读 EPUB 不能等同于 AZW3 直接预览。
- 不处理 DRM，不含 OCR，不承诺复杂公式、固定版式及扫描 PDF 的无损重排。
- [验证说明](docs/VALIDATION.md) 提供本机耗时。

## 源码运行与构建

需要 Python 3.9 或更高版本。Windows 发布版使用 Python 3.9 / PyInstaller 6.17.0 / Inno Setup 6。

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe main.py
~~~

在 PyCharm 配置解释器后运行 `main.py`。已有环境若不希望改动包版本，可执行 `install_dependencies.ps1 -Python '你的 python.exe 路径'`，将依赖装到项目 `.runtime/packages`。

测试：`python -m pytest tests -q`。打包方法、Inno 脚本和校验流程见 [docs/BUILD.md](docs/BUILD.md)。

## 开源

原创代码和图标采用 **AGPL-3.0-only**，详见 [LICENSE.md](LICENSE.md) 与 [LICENSE](LICENSE)。第三方协议见 [THIRD_PARTY.md](THIRD_PARTY.md) 和 [依赖来源](docs/DEPENDENCIES.md)。用户电子书、字体、封面及转换结果不被本项目协议重新授权。

欢迎通过 Issues 反馈，请提供版本、格式、错误信息与可公开的最小示例，不要上传无权公开的书籍全文或私人设备数据。
