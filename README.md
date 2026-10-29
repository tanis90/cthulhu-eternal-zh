# Cthulhu Eternal SRD — 中文翻译

[Cthulhu Eternal](https://cthulhueternal.com/) 是 Cthulhu Reborn 发布的一套开源 d100 克苏鲁恐怖规则，
以 **OGL 1.0a** 授权，全部内容为 Open Game Content。

本项目把 SRD 译成中文并公开发布——**OGL 明确允许翻译**（其定义中 "Derivative Material" 包含 translations）。

> **状态：等待源文件。**
> SRD 托管在 DriveThruRPG，本机因 Cloudflare ASN 级封锁（error 1005）无法下载。
> 将 `Cthulhu Eternal — Modern Age SRD` 的 PDF 放到本目录并命名 `srd.pdf`，然后执行 `./run.sh`。

## 许可

- 原文：© Cthulhu Reborn，OGL 1.0a
- 译文：同样以 OGL 1.0a 发布，附完整许可与 Section 15
- 脚本：MIT

## 结构

```
原文/       MinerU 解析 + 分章笔记
译文/       分节译文
glossary/   译名对照表
tools/      fix_ocr.py / split.py / translate.py / qa.py
run.sh      一条命令跑完
```
