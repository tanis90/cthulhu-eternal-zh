#!/usr/bin/env python3
"""Split a MinerU markdown export into chapter notes + translation jobs.

Usage:
    python3 split.py <raw.md> <outdir> [--max-chunk 4200] [--title "书名"]

Produces:
    <outdir>/原文/NN-<slug>.md   Obsidian notes (frontmatter + TOC + body + links)
    <outdir>/jobs/<part>__NN.src.md   translation units
    <outdir>/jobs/_jobs.json
"""
import argparse, json, os, re, sys

MAX_CHUNK = 4200


def slugify(s, limit=34):
    s = re.sub(r"[^\w\u4e00-\u9fff\-]+", "-", s, flags=re.U)
    s = re.sub(r"-{2,}", "-", s).strip("-")
    if len(s) > limit:
        cut = s[:limit]
        if "-" in cut:
            cut = cut.rsplit("-", 1)[0]
        s = cut.strip("-")
    return s or "part"


def split_sections(lines):
    """Split at any heading (H1-H3). Empty-body headings are preserved: the
    source legally contains stacked label headings and dropping them silently
    loses structure (see skill: 'empty heading' pitfall)."""
    out, cur, buf = [], None, []
    for ln in lines:
        if re.match(r"^#{1,3} ", ln):
            if cur is not None:
                out.append((cur, "\n".join(buf).strip()))
            cur, buf = re.sub(r"^#+\s*", "", ln).strip(), []
        else:
            buf.append(ln)
    if cur is not None:
        out.append((cur, "\n".join(buf).strip()))
    return out


def group_parts(lines):
    """Top-level parts start at H1."""
    idx = [i for i, l in enumerate(lines) if l.startswith("# ")]
    if not idx:
        return [("00-正文", lines)]
    parts = []
    if idx[0] > 0 and any(l.strip() for l in lines[:idx[0]]):
        parts.append(("00-前言", lines[:idx[0]]))
    for n, i in enumerate(idx):
        j = idx[n + 1] if n + 1 < len(idx) else len(lines)
        title = re.sub(r"^#+\s*", "", lines[i]).strip()
        parts.append((f"{n+1:02d}-{slugify(title)}", lines[i:j]))
    return parts


def chunk_sections(secs, max_chunk):
    chunks, cur, size = [], [], 0
    for head, body in secs:
        blk = f"## {head}\n\n{body}\n"
        if cur and size + len(blk) > max_chunk:
            chunks.append(cur)
            cur, size = [], 0
        cur.append((head, blk))
        size += len(blk)
    if cur:
        chunks.append(cur)
    return chunks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("outdir")
    ap.add_argument("--max-chunk", type=int, default=MAX_CHUNK)
    ap.add_argument("--title", default="")
    ap.add_argument("--image-prefix", default="../assets/images/")
    a = ap.parse_args()

    text = open(a.src, encoding="utf-8").read()
    # normalise image refs
    text = re.sub(r"\]\((?:\.\./)?(?:raw/)?images/", f"]({a.image_prefix}", text)
    lines = text.split("\n")

    src_dir = os.path.join(a.outdir, "原文")
    job_dir = os.path.join(a.outdir, "jobs")
    os.makedirs(src_dir, exist_ok=True)
    os.makedirs(job_dir, exist_ok=True)

    jobs, index = [], []
    for name, body in group_parts(lines):
        # drop the leading H1: it is the part title, already used as note title
        if body and body[0].startswith("# "):
            body = body[1:]
        secs = split_sections(body)
        note = os.path.join(src_dir, name + ".md")
        toc = "\n".join(f"- {h}" for h, _ in secs if h)
        with open(note, "w", encoding="utf-8") as f:
            f.write(f"---\ntags: [原文]\nsource: {os.path.basename(a.src)}\nstatus: 待译\n---\n\n")
            f.write(f"# {a.title or name.split('-', 1)[-1]}\n\n")
            if toc:
                f.write("## 本节结构\n" + toc + "\n\n---\n\n")
            f.write("\n".join(body))
            f.write(f"\n\n## 关联\n- [[../译文/{name}|译文]]\n- [[译名对照表]]\n")
        index.append({"part": name, "sections": len(secs), "chars": len("\n".join(body))})

        for n, grp in enumerate(chunk_sections(secs, a.max_chunk), 1):
            payload = "\n".join(blk for _, blk in grp)
            jid = f"{name}__{n:02d}"
            jp = os.path.join(job_dir, jid + ".src.md")
            open(jp, "w", encoding="utf-8").write(payload)
            jobs.append({"id": jid, "part": name, "seq": n,
                         "sections": [h for h, _ in grp if h],
                         "chars": len(payload), "src": jp})

    json.dump(jobs, open(os.path.join(job_dir, "_jobs.json"), "w"),
              ensure_ascii=False, indent=1)
    print(f"parts={len(index)} jobs={len(jobs)}")
    for p in index:
        print(f"  {p['part']:28s} {p['sections']:3d} 节 {p['chars']:7d} 字符")


if __name__ == "__main__":
    main()
