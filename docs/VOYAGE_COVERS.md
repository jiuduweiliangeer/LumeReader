# Voyage / 旧款 Kindle 的 KFX 书架封面

旧版软件统一把 KFX 输出为 PDOC 个人文档。Voyage 的旧固件不能像新款 Kindle 那样为侧载 PDOC KFX 自动显示书架封面，因此“书内有封面”与“书架有封面”是两件事。

## 如何处理

1. 连接并解锁 Kindle，检查设备栏型号。未自动识别时手动选择 Kindle Voyage。
2. 查看主界面的格式推荐。Voyage 推荐使用 AZW3，软件已内置 KindleGen，无需额外安装或配置。
3. 如果继续使用 KFX，将旧文件重新加入队列，选择 KFX，然后点击“转换并发送”。自动模式会生成 EBOK，并把对应缩略图发送至设备。
4. 未连接设备、仅转换给 Voyage 使用时，在“设置 → KFX 封面兼容”选择“旧款 Kindle / Voyage”。之后通过软件发送文件；仅用文件管理器拖入 documents 不会发送独立书架缩略图。
5. 安全弹出 USB，等待 Kindle 索引。若联网后封面被设备替换，再连接电脑，在软件中刷新书架，恢复本软件缓存的缩略图。

“直接发送”保持原文件字节不变。把旧 PDOC 文件直接重发，不会改变文档类型。软件不会通过替换书籍文件来修复封面，也不会删除阅读记录。

## 实现与限制

- 旧款 KFX 输出写入 EBOK 内容类型；现代 MTP 默认 PDOC。设置中可显式覆盖。
- 缩略图名称与书籍的 ASIN / 内容类型一致。
- USB 设备在 `system/lume-cover-cache` 保存本软件发送的封面副本与校验记录；刷新书架时只恢复仍对应设备书籍的封面。已删除书籍不会重新出现在书架。
- 这修复的是书架缩略图，不是锁屏封面功能。锁屏显示还取决于设备型号、固件与设备设置。
- 无法保证所有固件版本的行为相同，也不处理 DRM 或缺失的 KFX 分包。

依据：[KFX Output 作者的封面兼容说明](https://www.mobileread.com/forums/showthread.php?t=272407)、[Amazon 固件下载说明](https://digprjsurvey.amazon.com/csad/help/node/GKMQC26VQQMM8XSW?theme=light)、[Calibre Kindle 驱动的缩略图约定](https://github.com/kovidgoyal/calibre/blob/master/src/calibre/devices/kindle/driver.py)。Lume 不调用 Calibre。