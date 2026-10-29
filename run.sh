#!/bin/bash
# 用法：把 SRD 的 PDF 放到本目录并命名 srd.pdf，然后 ./run.sh [语言]
set -euo pipefail
LANG_CODE="${1:-en}"
export HTTPS_PROXY="${HTTPS_PROXY:-http://127.0.0.1:7891}"
: "${OPEN_DESIGN_API_KEY:?请先 export OPEN_DESIGN_API_KEY}"

[ -f srd.pdf ] || { echo "缺少 srd.pdf"; exit 1; }

echo "== 1/5 MinerU 解析"
mineru-open-api extract srd.pdf --language "$LANG_CODE" -f md,json -o raw/

MD=$(ls raw/*.md | head -1)
echo "== 2/5 修复 OCR 缺陷（ff 连字 / 丢空格）"
python3 tools/fix_ocr.py "$MD" raw/clean.md

echo "== 3/5 分章"
python3 tools/split.py raw/clean.md . --title "Cthulhu Eternal SRD"

echo "== 4/5 翻译"
[ -f glossary/译名对照表.md ] || { echo "缺少 glossary/译名对照表.md"; exit 1; }
python3 tools/translate.py . --glossary glossary/译名对照表.md --model mimo-v2.6-flash --concurrency 4

echo "== 5/5 校对"
python3 tools/qa.py . --glossary glossary/译名对照表.md
