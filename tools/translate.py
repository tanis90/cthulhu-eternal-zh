#!/usr/bin/env python3
"""Dispatch translation jobs to an OpenAI-compatible endpoint.

Usage:
    export OPEN_DESIGN_API_KEY=...
    export HTTPS_PROXY=http://127.0.0.1:7891
    python3 translate.py <project> [--glossary glossary/译名对照表.md]
                                   [--model mimo-v2.6-flash]
                                   [--base https://amr-link.open-design.ai/v1]
                                   [--concurrency 4] [--only PART__01 ...]

Design notes (learned the hard way):
  * concurrency >5 destabilises the upstream; 4 is the tested ceiling
  * max_tokens must be large: reasoning eats the budget and yields empty content
  * reasoning_effort=low keeps cost down for translation work
"""
import argparse, json, os, queue, sys, threading, time, urllib.request

SYS_TMPL = """你是资深 TRPG 模组译者，专精《克苏鲁的呼唤》，母语中文。
本次任务：把跑团模组译成简体中文。原文由出版社免费公开发行，仅供跑团桌上使用。

硬性要求：
1. 严格遵守随附的《译名对照表》，表内词条一字不改。
2. 保留 Markdown 结构：标题层级、项目符号、加粗、斜体、图片占位全部原样保留，**逐个标题照搬，不得合并或省略**。
3. 规则数据保持数字不变，属性缩写按对照表换成中文（如 "S 30" → "力量 30"）。
4. 第二人称朗读段落用"你"；守秘人提示用"守秘人"。
5. 中文要像人写的中文：长句拆开、被动改主动、少用"的的的"。
6. 只输出译文，不要前言、不要说明。
"""


def call(op, base, key, model, prompt, max_tokens, effort, timeout, tries):
    body = json.dumps({
        "model": model,
        "messages": [{"role": "system", "content": SYS_TMPL},
                     {"role": "user", "content": prompt}],
        "max_tokens": max_tokens,
        "temperature": 0.25,
        "reasoning_effort": effort,
        "stream": False,
    }).encode()
    last = "?"
    for i in range(tries):
        req = urllib.request.Request(f"{base}/chat/completions", data=body,
                                     headers={"Authorization": f"Bearer {key}",
                                              "Content-Type": "application/json"})
        try:
            t0 = time.time()
            d = json.loads(op.open(req, timeout=timeout).read())
            el = time.time() - t0
            if "error" in d:
                last = str(d["error"])[:160]
                time.sleep(3 * (i + 1)); continue
            ch = d["choices"][0]
            txt = (ch["message"].get("content") or "").strip()
            if not txt:
                last = f"empty content finish={ch.get('finish_reason')}"
                time.sleep(3 * (i + 1)); continue
            u = d.get("usage", {})
            return {"ok": True, "text": txt, "secs": el,
                    "in": u.get("prompt_tokens"), "out": u.get("completion_tokens"),
                    "reasoning": (u.get("completion_tokens_details") or {}).get("reasoning_tokens")}
        except Exception as e:
            last = f"{type(e).__name__}: {e}"[:160]
            time.sleep(3 * (i + 1))
    return {"ok": False, "err": last}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--glossary", default="glossary/译名对照表.md")
    ap.add_argument("--model", default="mimo-v2.6-flash")
    ap.add_argument("--base", default="https://amr-link.open-design.ai/v1")
    ap.add_argument("--key-env", default="OPEN_DESIGN_API_KEY")
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--max-tokens", type=int, default=16000)
    ap.add_argument("--effort", default="low")
    ap.add_argument("--timeout", type=int, default=300)
    ap.add_argument("--tries", type=int, default=3)
    ap.add_argument("--only", nargs="*", default=None)
    a = ap.parse_args()

    key = os.environ.get(a.key_env, "")
    if not key:
        sys.exit(f"set {a.key_env}")
    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("https_proxy")
    op = (urllib.request.build_opener(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
          if proxy else urllib.request.build_opener())

    root = a.project
    jobs = json.load(open(os.path.join(root, "jobs/_jobs.json"), encoding="utf-8"))
    if a.only:
        jobs = [j for j in jobs if any(o in j["id"] for o in a.only)]
    gloss = open(os.path.join(root, a.glossary), encoding="utf-8").read()
    outdir = os.path.join(root, "译文", "_parts")
    os.makedirs(outdir, exist_ok=True)

    q = queue.Queue()
    for j in jobs:
        dst = os.path.join(outdir, j["id"] + ".zh.md")
        if os.path.exists(dst) and os.path.getsize(dst) > 200:
            continue
        q.put(j)

    results, lock, done = {}, threading.Lock(), [0]
    total = q.qsize()
    print(f"jobs pending: {total}", flush=True)

    def worker():
        while True:
            try:
                j = q.get_nowait()
            except queue.Empty:
                return
            src = open(os.path.join(root, j["src"]), encoding="utf-8").read()
            r = call(op, a.base, key, a.model,
                     f"【译名对照表】\n{gloss}\n\n【待译原文】\n{src}",
                     a.max_tokens, a.effort, a.timeout, a.tries)
            with lock:
                done[0] += 1
                if r["ok"]:
                    open(os.path.join(outdir, j["id"] + ".zh.md"), "w",
                         encoding="utf-8").write(r["text"])
                    results[j["id"]] = {k: v for k, v in r.items() if k != "text"}
                    results[j["id"]]["chars"] = len(r["text"])
                    print(f"[{done[0]}/{total}] {j['id']} OK {r['secs']:.0f}s "
                          f"out={r['out']} zh={len(r['text'])}", flush=True)
                else:
                    results[j["id"]] = {"ok": False, "err": r["err"]}
                    print(f"[{done[0]}/{total}] {j['id']} FAIL {r['err']}", flush=True)
            q.task_done()

    ts = [threading.Thread(target=worker) for _ in range(min(a.concurrency, max(1, total)))]
    for t in ts: t.start()
    for t in ts: t.join()

    p = os.path.join(outdir, "_results.json")
    old = json.load(open(p, encoding="utf-8")) if os.path.exists(p) else {}
    old.update(results)
    json.dump(old, open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    ok = sum(1 for v in results.values() if v.get("ok"))
    print(f"\ndone {ok}/{len(results)}")
    if ok:
        t = [v["secs"] for v in results.values() if v.get("ok")]
        print(f"total {sum(t):.0f}s avg {sum(t)/len(t):.0f}s/job")


if __name__ == "__main__":
    main()
