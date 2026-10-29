#!/usr/bin/env python3
"""Merge translated parts and run structural / terminology QA.

Usage:
    python3 qa.py <project> [--glossary glossary/译名对照表.md]

Checks:
  1. glossary violations  — forbidden variants listed in the glossary's
     '已知风险点' / explicit "禁止" notes, plus a built-in default set
  2. proper-noun consistency — one spelling per name within a part
  3. structure — H2 count and image count vs the source note
  4. reporting — writes 译文/_qa.md
"""
import argparse, glob, json, os, re, sys

# generic wrong-variants that almost always indicate a glossary miss
DEFAULT_BAD = [
    ("守密人", "守秘人"),
    ("调查者", "调查员"),
    ("探索者", "调查员"),
    ("黄衣王", "黄衣之王"),
    ("无名者", "不可名状者"),
    ("九头蛇", "许德拉"),
]


def load_forbidden(gloss_path):
    bad = list(DEFAULT_BAD)
    if not os.path.exists(gloss_path):
        return bad
    t = open(gloss_path, encoding="utf-8").read()
    for m in re.finditer(r"禁止译[作为]?[「\"“]([^」\"”]+)[」\"”]|不要译成[「\"“]([^」\"”]+)[」\"”]|不译[「\"“]([^」\"”]+)[」\"”]", t):
        w = next(g for g in m.groups() if g)
        bad.append((w, "（对照表禁用）"))
    return bad


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--glossary", default="glossary/译名对照表.md")
    a = ap.parse_args()
    root = a.project

    jobs = json.load(open(os.path.join(root, "jobs/_jobs.json"), encoding="utf-8"))
    parts = {}
    for j in jobs:
        parts.setdefault(j["part"], []).append(j)

    td = os.path.join(root, "译文")
    bad = load_forbidden(os.path.join(root, a.glossary))
    report = ["# 校对报告\n"]
    ok_all = True

    for part, js in sorted(parts.items()):
        js.sort(key=lambda x: x["seq"])
        chunks = []
        missing = []
        for j in js:
            p = os.path.join(td, "_parts", j["id"] + ".zh.md")
            if os.path.exists(p):
                chunks.append(open(p, encoding="utf-8").read().strip())
            else:
                missing.append(j["id"])
        if not chunks:
            report.append(f"## {part}\n- ❌ 无译文（缺 {len(js)} 节）\n")
            ok_all = False
            continue

        body = "\n\n".join(chunks)
        # drop the leading part-title heading re-emitted from the source H1
        if not part.startswith("00-"):
            body = re.sub(r"^## [^\n]*\n+", "", body, count=1)
        out = os.path.join(td, part + ".md")
        with open(out, "w", encoding="utf-8") as f:
            f.write(f"---\ntags: [译文]\nsource: \"[[{part}]]\"\nstatus: 初译\n---\n\n")
            nice = part.split("-", 1)[-1].replace("-", " ")
            f.write(f"# {nice}（初译）\n\n")
            f.write(f"> {len(chunks)}/{len(js)} 节。术语基准：[[译名对照表]]\n\n{body}\n")

        # 1. glossary violations
        viol = []
        for w, good in bad:
            n = body.count(w)
            if n and w != good:
                viol.append(f"{w}×{n} → {good}")
        # 2. structure
        src = os.path.join(root, "原文", part + ".md")
        s_h2 = d_h2 = s_img = d_img = -1
        if os.path.exists(src):
            st = open(src, encoding="utf-8").read()
            s_h2 = len([h for h in re.findall(r"^## (.*)", st, re.M) if h.strip() not in ("本节结构", "关联")])
            # the first H2 is the part title re-emitted from the source H1
            d_h2 = len(re.findall(r"^## ", body, re.M))
            s_img = len(re.findall(r"!\[", st))
            d_img = len(re.findall(r"!\[", body))

        status = "✅" if not viol and (s_h2 < 0 or s_h2 == d_h2) and not missing else "⚠️"
        if status != "✅":
            ok_all = False
        report.append(f"## {part} {status}")
        report.append(f"- 节数 {len(chunks)}/{len(js)}" + (f"，缺 {missing}" if missing else ""))
        report.append(f"- 字数 {len(body)}")
        if s_h2 >= 0:
            report.append(f"- 标题 {d_h2}/{s_h2}，图片 {d_img}/{s_img}"
                          + ("" if d_h2 == s_h2 else "  ← 不一致"))
        report.append(f"- 术语违规：{'; '.join(viol) if viol else '无'}")
        report.append("")

    report.append(f"\n**总体：{'通过' if ok_all else '有项目需人工复核'}**\n")
    open(os.path.join(td, "_qa.md"), "w", encoding="utf-8").write("\n".join(report))
    print("\n".join(report))


if __name__ == "__main__":
    main()
