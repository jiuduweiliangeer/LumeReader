# 字体来源与使用

阅读样式中的字体列表包含安装包内置字体与“设置 → 字体文件夹”中的本地 TTF / OTF。内置字体离线可用，不读取或打包 Windows 系统字体。选好后，支持字体的输出格式会嵌入字体；在 Kindle 上选择“出版商字体”。

## 安装包内置

| 字体 | 来源与版本 | 许可记录 |
|---|---|---|
| 霞鹜文楷 Regular | [LXGW WenKai](https://github.com/lxgw/LxgwWenKai)，本地原始 v1.234 文件 | SIL OFL 1.1；附原始 License.txt |
| 汇文明朝（符号修正版） | [bosswnx/huiwenmincho-improved](https://github.com/bosswnx/huiwenmincho-improved)，原作者特里王 | 原字体 name 表声明 Public Domain；保留原文件、版权元数据和来源说明 |
| 悠哉字体 Light | [lxgw/yozai-font](https://github.com/lxgw/yozai-font) | SIL OFL 1.1；附上游 OFL.txt |

这些字体的原始文件、声明与 SHA256 清单位于 `lume/assets/fonts`。字体保留原许可，不因随软件发行而改用 AGPL。

## 自备字体

仓耳今楷、京华老宋、上图东观体等可通过“选择 TTF / OTF 字体文件”使用，也可放入自己的字体目录。软件保留已有的本地字体设置。

- [仓耳今楷官方页面](https://www.tsanger.cn/product/7)含使用授权说明；本项目不把个人下载许可视为公开分发许可。
- [上图东观体官方页面](https://www.library.sh.cn/special/dongguanti/)提供下载与使用说明。用户提到的“上海馆阁”对应的本地文件名称为“上图东观体”，软件沿用文件原名。
- 京华老宋在本软件中保留完整字体嵌入，不生成修改后的字形子集。未将其纳入公开安装包。

自备字体的使用与电子书嵌入范围以各自许可为准。放进字体文件夹不会让软件上传字体；公开安装包只包含上表列出的三个文件。