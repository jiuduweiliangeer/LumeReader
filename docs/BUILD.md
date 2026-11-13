# Windows 构建与发布

## 工具

- Windows x64、[Python](https://www.python.org/downloads/windows/) 3.9 或更高版本，首版使用现有 Python 3.9 环境。
- [Inno Setup 官方下载](https://jrsoftware.org/isdl.php)，首版使用 6.7.3。
- PyInstaller 6.17.0；运行依赖由 requirements.txt 固定。
- 默认构建不包含 KindleGen；本地集成构建可显式传入已有的 `kindlegen.exe`，见下文。

## 构建

~~~powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt pyinstaller==6.17.0 pytest==8.4.2
.\.venv\Scripts\python.exe -m pytest tests -q
powershell -File packaging\build.ps1 -Python .\.venv\Scripts\python.exe
~~~

Inno 自定义路径使用 `-ISCC '路径\ISCC.exe'`。

产物：
- `dist/LumeReader/LumeReader.exe`：GUI。
- `dist/LumeReader/LumeWorker.exe`：后台转换与命令行入口，不能单独拆走。
- `release/LumeReader-1.1.1-Setup-x64.exe`：安装包。

采用目录式 EXE 由 Inno 安装，避免每次启动重复解压。最终用户不需要 Python 开发环境。

## 数据

资源来自安装目录；设置、缓存、任务和输出写入 `%LOCALAPPDATA%\LumeReader`。验证时可用 `LUME_DATA_DIR` 指向独立临时目录。源码模式默认使用项目目录。

## 验证与发布

~~~powershell
dist\LumeReader\LumeWorker.exe --self-check
dist\LumeReader\LumeWorker.exe --convert examples\阅读示例.txt --to kfx --output release\smoke-output
~~~

继续验证非 TXT 输入、GUI 队列、目录字体封面、MTP 只读检测及 Inno 安装 / 卸载。不要发布用户书籍或字体。

发布包含版本 tag、安装包、对应源码和 `SHA256SUMS.txt`。修改版本时同步 lume/__init__.py、packaging/version_info.txt 和 Inno AppVersion。

许可和源码链接见 [DEPENDENCIES.md](DEPENDENCIES.md)。测试小说、个人设置、备份、缓存、商业字体及 KindleGen 不属于发布内容。

字体测试可通过 `LUME_TEST_FONT` 指定中文 TTF / OTF，Windows 默认寻找黑体；缺少合适字体时跳过对应测试。KindleGen 测试在缺少编译器时也会跳过。

## 本地集成 KindleGen

将已有的 KindleGen 随本地安装包一起安装，用户无需单独安装或填写路径：

~~~powershell
powershell -File packaging\build.ps1 -Python .\.venv\Scripts\python.exe -KindleGen 'D:\tools\kindlegen.exe'
~~~

集成产物为 `release/LumeReader-1.1.1-Integrated-Setup-x64.exe`，不覆盖标准安装包。`-DistPath` 与 `-WorkPath` 可指定项目内的独立构建目录。

PyInstaller 将原始 EXE、SHA-256 清单及组件说明放入 `_internal/tools/`。运行时优先使用此副本；仍可在设置中指定其他有效编译器。旧配置路径失效时自动回退到内置组件。源码运行时也可使用被 Git 忽略的 `tools/kindlegen.exe`。

直接调用 spec 时设置 `LUME_BUNDLE_KINDLEGEN` 为该文件路径。不传参数的构建不会把本机自动发现的编译器带入安装包。KindleGen 仍按 Amazon 条款使用；集成功能不授予再分发权，本次集成安装包仅在本地生成。

验证集成构建时设置 `LUME_VERIFY_EXE` 指向打包的 LumeWorker.exe、`LUME_VERIFY_BUNDLED_KINDLEGEN=1`，运行 `packaging/verify_bundle.py`。验证会移除外部 KINDLEGEN 环境变量、清理 PATH，检查组件来源与哈希，并执行包含 MOBI / AZW3 的转换矩阵。
