# 依赖、源码与许可证

Windows 安装包包含下列组件的运行文件，保留各自许可证。项目原创代码采用 AGPL-3.0-only。许可副本随安装包保存在 licenses 目录。

| 组件 | 构建版本 | 授权记录 | 发行与源码 |
|---|---|---|---|
| PyQt6 | 6.6.1 | GPL v3 | [PyPI / source](https://pypi.org/project/PyQt6/6.6.1/#files) |
| PyQt6-Qt6 | 6.6.3 | LGPL v3 | [PyPI / source](https://pypi.org/project/PyQt6-Qt6/6.6.3/#files) |
| PyQt6-sip | 13.6.0 | SIP | [PyPI / source](https://pypi.org/project/PyQt6-sip/13.6.0/#files) |
| lxml | 5.3.2 | BSD-3-Clause | [PyPI / source](https://pypi.org/project/lxml/5.3.2/#files) |
| PyMuPDF | 1.26.5 | Dual Licensed - GNU AFFERO GPL 3.0 or Artifex Commercial License | [PyPI / source](https://pypi.org/project/PyMuPDF/1.26.5/#files) |
| beautifulsoup4 | 4.12.3 | MIT License | [PyPI / source](https://pypi.org/project/beautifulsoup4/4.12.3/#files) |
| soupsieve | 2.7 | MIT | [PyPI / source](https://pypi.org/project/soupsieve/2.7/#files) |
| tinycss2 | 1.4.0 | See bundled notices | [PyPI / source](https://pypi.org/project/tinycss2/1.4.0/#files) |
| cssselect2 | 0.8.0 | See bundled notices | [PyPI / source](https://pypi.org/project/cssselect2/0.8.0/#files) |
| webencodings | 0.5.1 | BSD | [PyPI / source](https://pypi.org/project/webencodings/0.5.1/#files) |
| fonttools | 4.60.1 | MIT | [PyPI / source](https://pypi.org/project/fonttools/4.60.1/#files) |
| reportlab | 5.0.0 | BSD license (see license.txt for details), Copyright (c) 2000-2025, ReportLab Inc. | [PyPI / source](https://pypi.org/project/reportlab/5.0.0/#files) |
| pillow | 11.3.0 | MIT-CMU | [PyPI / source](https://pypi.org/project/pillow/11.3.0/#files) |
| comtypes | 1.4.16 | MIT | [PyPI / source](https://pypi.org/project/comtypes/1.4.16/#files) |
| charset-normalizer | 2.1.1 | MIT | [PyPI / source](https://pypi.org/project/charset-normalizer/2.1.1/#files) |
| pyinstaller | 6.17.0 | GPLv2-or-later with a special exception which allows to use PyInstaller to build and distribute non-free programs (including commercial ones) | [PyPI / source](https://pypi.org/project/pyinstaller/6.17.0/#files) |
| altgraph | 0.17.5 | MIT | [PyPI / source](https://pypi.org/project/altgraph/0.17.5/#files) |
| pefile | 2024.8.26 | MIT | [PyPI / source](https://pypi.org/project/pefile/2024.8.26/#files) |
| packaging | 25.0 | See bundled notices | [PyPI / source](https://pypi.org/project/packaging/25.0/#files) |
| pyinstaller-hooks-contrib | 2025.10 | See bundled notices | [PyPI / source](https://pypi.org/project/pyinstaller-hooks-contrib/2025.10/#files) |
| pywin32-ctypes | 0.2.3 | BSD-3-Clause | [PyPI / source](https://pypi.org/project/pywin32-ctypes/0.2.3/#files) |
| setuptools | 80.9.0 | MIT | [PyPI / source](https://pypi.org/project/setuptools/80.9.0/#files) |
| importlib_metadata | 8.7.0 | See bundled notices | [PyPI / source](https://pypi.org/project/importlib_metadata/8.7.0/#files) |
| zipp | 3.23.0 | MIT | [PyPI / source](https://pypi.org/project/zipp/3.23.0/#files) |

Qt 6.6.3 源码：[Qt archive](https://download.qt.io/archive/qt/6.6/6.6.3/single/)。程序动态链接 QtCore、QtGui、QtWidgets、QtSvg 等，不使用 QtWebEngine。动态库未锁定，可按 LGPLv3 条件替换兼容库。

PyMuPDF 源码：[1.26.5](https://github.com/pymupdf/PyMuPDF/tree/1.26.5)。MuPDF 对应源码由该版本 setup.py / sdist 指定：[MuPDF releases](https://mupdf.com/releases/)。再分发应保证对应版本源码的可获取性，不能仅提供不匹配的新版。

Python 运行时为 Python 3.9，版权和许可见 licenses/Python-LICENSE.txt，源码见 [Python source releases](https://www.python.org/downloads/source/)。确切构建版本记录在 Release 验证报告。

PyInstaller bootloader 使用 GPLv2-or-later 及 bootloader exception；例外不替代应用或依赖的许可证。

vendor/ 内 KindleUnpack、kfxgen、kfxlib、公式组件和字体数据保留上游声明，源码随仓库提供。修订及修改点见 [THIRD_PARTY.md](../THIRD_PARTY.md)。

Amazon KindleGen 不包含在安装包内，由用户按 Amazon 条款另行安装。

每个 Release 的 tag 与源码压缩包对应其二进制版本，packaging/ 提供构建脚本。源代码、许可和依赖信息应随再发布版本提供。

补充解码依赖：pypdf 6.16.1（BSD-3-Clause），[对应源码](https://pypi.org/project/pypdf/6.16.1/#files)，许可见 licenses/pypdf。发布包内 Python 为 3.9.23；MuPDF 运行时为 1.26.10，[对应源码标签](https://github.com/ArtifexSoftware/mupdf/tree/1.26.10)，重建时包含该标签的子模块。

安装器使用 Inno Setup 6.7.3，版权声明见 licenses/Inno-Setup/LICENSE.txt；[上游源码](https://github.com/jrsoftware/issrc/tree/is-6_7_3)。
