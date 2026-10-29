#!/usr/bin/env python3
"""Repair two MinerU OCR defects in Latin-script PDFs, using pypdf as the oracle.

  1. ff-ligature loss  — `souffle` -> `soufle`, `affronter` -> `afronter`
  2. missing spaces    — `Ilfallait` -> `Il fallait`, `Leforgeron` -> `Le forgeron`

Both are detected by "the token is not in pypdf's vocabulary, but a repaired
form is". Repairs are only applied when the confidence is high; the space
heuristic is deliberately conservative because it misfires on real words
(`Toutefois`, `Mal-Tourment`, elisions like `d'Amérique`).

Usage:
    python3 fix_ocr.py <book.pdf> <mineru.md> <out.md> [--report]
"""
import argparse, re, sys

import pypdf

# words the space-splitter must never touch (proper nouns, valid compounds)
SPACE_SKIP = {
    "toutefois", "pourtour", "pareil", "querelleur", "pardonne", "discontinue",
    "mal-tourment", "trente-quatre",
}
# elisions are split by an apostrophe, never by a space
ELISION = re.compile(r"^[a-zà-ÿ]{1,2}[’']")


def vocab_from_pdf(path):
    r = pypdf.PdfReader(path, strict=False)
    txt = "".join((p.extract_text() or "") for p in r.pages)
    return {w.lower() for w in re.findall(r"[A-Za-zÀ-ÿ'’\-]{2,}", txt)}


def repair_ff(text, vocab):
    toks = set(re.findall(r"[A-Za-zÀ-ÿ'’\-]{2,}", text))
    fixes = {}
    for w in toks:
        lw = w.lower()
        if lw in vocab:
            continue
        for i in range(len(lw) + 1):
            cand = lw[:i] + "f" + lw[i:]
            if cand in vocab:
                fixes[w] = (w[0].upper() + cand[1:]) if w[0].isupper() else cand
                break
    return apply(text, fixes), fixes


def repair_spaces(text, vocab):
    toks = set(re.findall(r"[A-Za-zÀ-ÿ'’\-]{5,}", text))
    fixes = {}
    for w in toks:
        lw = w.lower()
        if lw in vocab or lw in SPACE_SKIP or ELISION.match(lw):
            continue
        for i in range(2, len(lw) - 1):
            if lw[:i] in vocab and lw[i:] in vocab:
                fixes[w] = f"{lw[:i]} {lw[i:]}"
                break
    return apply(text, fixes), fixes


def apply(text, fixes):
    for w, f in sorted(fixes.items(), key=lambda x: -len(x[0])):
        text = re.sub(rf"(?<![A-Za-zÀ-ÿ'’\-]){re.escape(w)}(?![A-Za-zÀ-ÿ'’\-])", f, text)
    return text


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf")
    ap.add_argument("src")
    ap.add_argument("out")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()

    vocab = vocab_from_pdf(a.pdf)
    t = open(a.src, encoding="utf-8").read()

    t, f1 = repair_ff(t, vocab)
    t, f2 = repair_spaces(t, vocab)
    # strip MinerU inline markup that breaks headings
    t = re.sub(r"</?su[bp]>", "", t)

    open(a.out, "w", encoding="utf-8").write(t)
    print(f"ff 连字修复 {len(f1)} 处，丢空格修复 {len(f2)} 处 -> {a.out}")
    if a.report:
        for w, f in sorted(f1.items()):
            print(f"  ff  {w} -> {f}")
        for w, f in sorted(f2.items()):
            print(f"  sp  {w} -> {f}")


if __name__ == "__main__":
    main()
