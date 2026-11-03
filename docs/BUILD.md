# Windows 构建与发布

## 工具

- Windows x64、[Python](https://www.python.org/downloads/windows/) 3.9 或更高版本，首版使用现有 Python 3.9 环境。
- [Inno Setup 官方下载](https://jrsoftware.org/isdl.php)，首版使用 6.7.3。
- PyInstaller 6.17.0；运行依赖由 requirements.txt 固定。
- KindleGen 只用于额外验证 MOBI / AZW3，不能复制进安装包。

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
- `release/LumeReader-1.0.0-Setup-x64.exe`：安装包。

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
