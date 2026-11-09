"""Deterministic, verifiable diffing. Everything produced here is a FACT derived
from the two texts (line numbers, before/after text). No interpretation."""
import difflib, hashlib, re

MD_HEAD = re.compile(r'^(#{1,6})\s+(.*\S)\s*$')
NUM_HEAD = re.compile(r'^(\d+(?:\.\d+)*)[.)]?\s+([A-Z][^.]{2,80})$')  # "3.1 Performance" (plain-text exports)


def parse_sections(text):
    """Split into sections: [{title, level, start, body:[(lineno, text)]}]."""
    secs, cur = [], {"title": "(preamble)", "level": 0, "start": 1, "body": []}
    for no, line in enumerate(text.splitlines(), 1):
        m = MD_HEAD.match(line)
        if m:
            level, title = len(m.group(1)), m.group(2)
        else:
            n = NUM_HEAD.match(line.strip())
            level, title = (n.group(1).count(".") + 1, line.strip()) if n else (0, None)
        if title:
            secs.append(cur)
            cur = {"title": title, "level": level, "start": no, "body": []}
        elif line.strip():
            cur["body"].append((no, line.rstrip()))
    secs.append(cur)
    return [s for s in secs if s["body"] or s["title"] != "(preamble)"]


def _word_diff(a, b):
    ta, tb = a.split(), b.split()
    out = []
    for op, i1, i2, j1, j2 in difflib.SequenceMatcher(None, ta, tb, autojunk=False).get_opcodes():
        if op == "equal":
            out.append(["eq", " ".join(ta[i1:i2])])
        else:
            if i2 > i1: out.append(["del", " ".join(ta[i1:i2])])
            if j2 > j1: out.append(["ins", " ".join(tb[j1:j2])])
    return out


def _cid(*parts):
    return hashlib.sha1("|".join(map(str, parts)).encode()).hexdigest()[:10]


def _match_sections(old, new):
    """Pair sections by exact title, then by fuzzy title (renames)."""
    pairs, used_new = [], set()
    new_by_title = {}
    for j, s in enumerate(new): new_by_title.setdefault(s["title"], j)
    unmatched_old = []
    for i, s in enumerate(old):
        j = new_by_title.get(s["title"])
        if j is not None and j not in used_new:
            pairs.append((i, j)); used_new.add(j)
        else:
            unmatched_old.append(i)
    for i in list(unmatched_old):
        best, bj = 0.0, None
        for j, s in enumerate(new):
            if j in used_new: continue
            ot, nt = old[i]["title"].lower(), s["title"].lower()
            r = difflib.SequenceMatcher(None, ot, nt).ratio()
            ob = " ".join(x[1] for x in old[i]["body"]); nb = " ".join(x[1] for x in s["body"])
            if ob and nb and difflib.SequenceMatcher(None, ob, nb, autojunk=False).ratio() >= 0.6:
                r = max(r, 0.8)  # same content under a new heading ("Rate Limits" -> "Throttling")
            if len(ot) >= 6 and (nt.startswith(ot) or ot.startswith(nt)): r = max(r, 0.9)  # "2. Auth" -> "2. Auth and Access"
            if r > best: best, bj = r, j
        if bj is not None and best >= 0.75:
            pairs.append((i, bj)); used_new.add(bj); unmatched_old.remove(i)
    return pairs, unmatched_old, [j for j in range(len(new)) if j not in used_new]


def compare(old_text, new_text, old_name="old", new_name="new"):
    old, new = parse_sections(old_text), parse_sections(new_text)
    pairs, gone, added = _match_sections(old, new)
    changes = []

    def mk(kind, section, before, after, old_lines, new_lines, renamed_from=None):
        c = {"id": _cid(kind, section, before, after), "kind": kind, "section": section,
             "before": before, "after": after,
             "old_source": {"file": old_name, "section": renamed_from or section, "lines": old_lines},
             "new_source": {"file": new_name, "section": section, "lines": new_lines}}
        if kind == "modified":
            c["word_diff"] = _word_diff(" ".join(before), " ".join(after))
        changes.append(c)

    rng = lambda ls: [ls[0][0], ls[-1][0]] if ls else None
    for i, j in sorted(pairs, key=lambda p: p[1]):
        o, n = old[i], new[j]
        renamed = o["title"] if o["title"] != n["title"] else None
        if renamed:
            mk("section_renamed", n["title"], [o["title"]], [n["title"]], [o["start"], o["start"]], [n["start"], n["start"]], renamed)
        ol, nl = o["body"], n["body"]
        sm = difflib.SequenceMatcher(None, [x[1].strip() for x in ol], [x[1].strip() for x in nl], autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal": continue
            b, a = [x[1] for x in ol[i1:i2]], [x[1] for x in nl[j1:j2]]
            kind = {"replace": "modified", "delete": "removed", "insert": "added"}[op]
            mk(kind, n["title"], b, a, rng(ol[i1:i2]), rng(nl[j1:j2]), renamed)
    for i in gone:
        o = old[i]; b = [x[1] for x in o["body"]]
        mk("section_removed", o["title"], [f"# {o['title']}"] + b, [], [o["start"], o["body"][-1][0] if o["body"] else o["start"]], None)
    for j in added:
        n = new[j]; a = [x[1] for x in n["body"]]
        mk("section_added", n["title"], [], [f"# {n['title']}"] + a, None, [n["start"], n["body"][-1][0] if n["body"] else n["start"]])
    return changes


def summarize(changes):
    """Factual summary (counts + per-section list). Verified."""
    counts = {}
    for c in changes: counts[c["kind"]] = counts.get(c["kind"], 0) + 1
    sections = sorted({c["section"] for c in changes})
    if not changes:
        return {"counts": {}, "sections": [], "text": "No textual differences found."}
    parts = ", ".join(f"{v} {k.replace('_', ' ')}" for k, v in sorted(counts.items()))
    return {"counts": counts, "sections": sections,
            "text": f"{len(changes)} change(s) across {len(sections)} section(s): {parts}."}
