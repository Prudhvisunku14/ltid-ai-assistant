from . import differ, analyzer

def compare_versions(src, doc, a, b):
    ta, tb = src.read_text(doc, a), src.read_text(doc, b)
    changes = differ.compare(ta, tb, f"{doc}/{a}", f"{doc}/{b}")
    meta = {v["id"]: v for v in src.versions(doc)}
    origin = lambda v: {"origin": meta[v].get("origin", "unknown"), "drive_id": meta[v].get("drive_id"), "file": meta[v]["file"]}
    return {"doc": doc, "v_old": a, "v_new": b, "origins": {"old": origin(a), "new": origin(b)},
            "verified": {"label": "VERIFIED - computed by exact text comparison", "summary": differ.summarize(changes)},
            "changes": changes, "interpretation": analyzer.analyze(changes)}

def scan_all(src, store):
    n = 0
    for d in src.documents():
        vs = d["versions"]
        for x, y in zip(vs, vs[1:]):
            store.save(d["name"], x["id"], y["id"], compare_versions(src, d["name"], x["id"], y["id"])); n += 1
    return n
