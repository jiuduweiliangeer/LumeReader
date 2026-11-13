# Windows 构建与发布

## 工具

- Windows x64、[Python](https://www.python.org/downloads/windows/) 3.9 或更高版本。
- [Inno Setup](https://jrsoftware.org/isdl.php)，当前使用 6.7.3。
- PyInstaller 6.17.0；运行依赖由 requirements.txt 固定。
- 构建安装包需要已有的 `kindlegen.exe`，放入 `tools/`，或通过 `-KindleGen` 指定。最终用户无需另行安装。

## 构建

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.17.0 pytest==8.4.2
.\.venv\Scripts\python.exe -m pytest tests -q
powershell -File packaging\build.ps1 -Python .\.venv\Scripts\python.exe -KindleGen '.\tools\kindlegen.exe'
~~~

`-ISCC` 可指定 Inno 编译器路径，`-DistPath` 与 `-WorkPath` 可指定项目内的独立构建目录。

也可直接调用构建工具：

~~~powershell
$env:LUME_BUNDLE_KINDLEGEN = (Resolve-Path '.\tools\kindlegen.exe').Path
.\.venv\Scripts\python.exe -m PyInstaller --noconfirm packaging\LumeReader.spec
& 'C:\Program Files (x86)\Inno Setup 6\ISCC.exe' packaging\LumeReader.iss
~~~

产物：

- `dist/LumeReader/LumeReader.exe`：GUI。
- `dist/LumeReader/LumeWorker.exe`：后台转换与命令行入口，不能单独拆走。
- `release/LumeReader-1.1.0-Setup-x64.exe`：包含 KindleGen 的安装包。

采用目录式 EXE 由 Inno 安装，避免每次启动重复解压。最终用户不需要 Python 开发环境。

## KindleGen 组件

构建时将原始 EXE、SHA-256 清单及组件说明放入 `_internal/tools/`；不修改编译器内容。运行时自动使用内置副本，也可在设置中指定其他有效编译器。旧配置路径失效时自动回退。

KindleGen 仍按 Amazon 独立条款使用，不受本项目 AGPL 重新授权。该 EXE 不存入源码仓库；源码运行时可使用被 Git 忽略的 `tools/kindlegen.exe`。直接调用 spec 时通过 `LUME_BUNDLE_KINDLEGEN` 指定文件，留空则使用项目 `tools/kindlegen.exe`；缺少组件时构建报错。

## 数据与检查

资源来自安装目录；设置、缓存、任务和输出写入 `%LOCALAPPDATA%\LumeReader`。开发时可用 `LUME_DATA_DIR` 指向独立临时目录。源码模式默认使用项目目录。

~~~powershell
dist\LumeReader\LumeWorker.exe --self-check
dist\LumeReader\LumeWorker.exe --convert examples\阅读示例.txt --to azw3 --output build-support\smoke-output
~~~

设置 `LUME_VERIFY_EXE` 指向打包的 LumeWorker.exe、`LUME_VERIFY_BUNDLED_KINDLEGEN=1`，运行 `packaging/verify_bundle.py`，可检查内置组件和跨格式转换。脚本清理外部 KINDLEGEN 环境变量及 PATH，核对组件来源和哈希。字体通过 `LUME_TEST_FONT` 指定。

发布包含版本 tag、安装包、对应源码和 `SHA256SUMS-1.1.0.txt`。修改版本时同步 lume/__init__.py、packaging/version_info.txt 和 Inno AppVersion。

许可和源码链接见 [DEPENDENCIES.md](DEPENDENCIES.md)。用户小说、个人设置、备份、缓存和私人字体不属于发布内容。
