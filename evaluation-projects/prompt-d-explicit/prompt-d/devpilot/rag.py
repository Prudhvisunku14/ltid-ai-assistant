"""D4 - Document-grounded RAG with verified citations and abstention.
Only authorized, approved, in-force, non-superseded documents are searchable.
An answer must be an extracted sentence from a retrieved chunk that satisfies the question's required pattern;
otherwise DevPilot abstains. Every citation is machine-verified against the source file."""
import math, re, datetime as dt
from pathlib import Path
from collections import Counter

STOP = set("a an the of is are was were what who our for to in on and or by do does did current".split())
EVIDENCE_PATTERNS = {  # question trigger -> regex the evidence sentence must contain
    r"\bwho approved\b": re.compile(r"\bapproved by\b|\bapproval (?:was )?(?:given |granted )?by\b|\bapproved the\b", re.I),
    r"\bdeadline\b": re.compile(r"\b\d+\s+(?:calendar\s+|business\s+)?days?\b|\b\d{4}-\d{2}-\d{2}\b", re.I),
}


def _tok(s):
    return [w[:-1] if w.endswith("s") and len(w) > 3 else w for w in re.findall(r"[a-z0-9]+", s.lower()) if w not in STOP]


def parse_doc(path):
    raw = Path(path).read_text()
    meta, body = {}, raw
    if raw.startswith("---"):
        _, fm, body = raw.split("---", 2)
        for line in fm.strip().splitlines():
            k, _, v = line.partition(":")
            meta[k.strip()] = v.strip()
    meta["doc_id"] = Path(path).stem
    meta["path"] = str(path)
    return meta, body.strip()


def chunks_of(body):
    sec, out = "(intro)", []
    for block in re.split(r"\n\s*\n", body):
        lines = block.strip().splitlines()
        if lines and lines[0].startswith("#"):
            sec = lines[0].lstrip("# ").strip(); lines = lines[1:]
        text = " ".join(l.strip() for l in lines).strip()
        if text:
            out.append((sec, text))
    return out


class Corpus:
    def __init__(self, folder, as_of=None):
        self.as_of = as_of or dt.date.today()
        self.docs, self.excluded, self.chunks = {}, [], []
        parsed = [parse_doc(p) for p in sorted(Path(folder).glob("*.md"))]
        approved = [m for m, _ in parsed if m.get("authorized") == "true" and m.get("status") == "approved"
                    and dt.date.fromisoformat(m["effective_date"]) <= self.as_of]
        superseded = {m["supersedes"] for m in approved if m.get("supersedes")}
        for meta, body in parsed:
            why = None
            if meta.get("authorized") != "true": why = "not authorized"
            elif meta.get("status") != "approved": why = f"status={meta.get('status')}"
            elif dt.date.fromisoformat(meta["effective_date"]) > self.as_of: why = "not yet in force"
            elif meta["doc_id"] in superseded: why = "superseded by a newer approved document"
            if why:
                self.excluded.append({"doc_id": meta["doc_id"], "reason": why, "body": body}); continue
            self.docs[meta["doc_id"]] = (meta, body)
            for sec, text in chunks_of(body):
                self.chunks.append({"doc_id": meta["doc_id"], "section": sec, "text": text, "meta": meta})
        df = Counter(w for c in self.chunks for w in set(_tok(c["text"] + " " + c["section"])))
        self.idf = {w: math.log((1 + len(self.chunks)) / (1 + n)) + 1 for w, n in df.items()}

    def _vec(self, text):
        tf = Counter(_tok(text))
        return {w: c * self.idf.get(w, 0) for w, c in tf.items()}

    def retrieve(self, q, k=3):
        qv = self._vec(q); qn = math.sqrt(sum(v * v for v in qv.values())) or 1
        scored = []
        for c in self.chunks:
            cv = self._vec(c["text"] + " " + c["section"]); cn = math.sqrt(sum(v * v for v in cv.values())) or 1
            s = sum(qv[w] * cv.get(w, 0) for w in qv) / (qn * cn)
            scored.append((s, c))
        return [x for x in sorted(scored, key=lambda t: -t[0])[:k] if x[0] > 0.05]


def _entities(question):
    return re.findall(r"\b[A-Z][\w]*(?: [A-Z][\w]*)+\b", question)


def verify_citation(cit):
    _, body = parse_doc(cit["path"])
    norm = lambda s: re.sub(r"\s+", " ", s)
    return norm(cit["quote"]) in norm(body)


def answer(corpus, question):
    ents, hits = _entities(question), corpus.retrieve(question)
    qtok = set(_tok(question)) - {w for e in ents for w in _tok(e)}
    required = [p for trig, p in EVIDENCE_PATTERNS.items() if re.search(trig, question, re.I)]
    best = None
    for score, c in hits:
        for sent in re.split(r"(?<=[.!?])\s+", c["text"]):
            if ents and not all(e.lower() in sent.lower() for e in ents):
                continue
            if required and not all(p.search(sent) for p in required):
                continue
            ov = len(qtok & set(_tok(sent)))
            if ov >= (1 if ents else 2) and (best is None or (ov, score) > best[0]):
                best = ((ov, score), sent, c)
    if best:
        _, sent, c = best
        cit = {"doc_id": c["doc_id"], "title": c["meta"].get("title"), "section": c["section"],
               "effective_date": c["meta"]["effective_date"], "quote": sent, "path": c["meta"]["path"]}
        return {"abstained": False, "answer": sent, "citations": [cit], "citations_verified": verify_citation(cit)}
    notes = [f"{x['doc_id']} ({x['reason']})" for x in corpus.excluded
             if not ents or any(e.lower() in x["body"].lower() for e in ents)]
    close = [{"doc_id": c["doc_id"], "section": c["section"], "quote": c["text"], "path": c["meta"]["path"]}
             for s, c in hits if not ents or all(e.lower() in c["text"].lower() for e in ents)][:1]
    return {"abstained": True,
            "answer": "I cannot answer: no authorized, in-force document establishes this.",
            "closest_authorized_evidence": close,
            "closest_verified": all(verify_citation(x) for x in close),
            "excluded_documents_mentioning_topic": notes}


def render(question, r):
    L = [f"**Q:** {question}"]
    if r["abstained"]:
        L.append(f"**A (abstain):** {r['answer']}")
        for c in r["closest_authorized_evidence"]:
            L.append(f"- Closest authorized evidence [{c['doc_id']} > {c['section']}]: \"{c['quote']}\" (verified={r['closest_verified']})")
        for n in r["excluded_documents_mentioning_topic"]:
            L.append(f"- Excluded, not used as evidence: {n}")
    else:
        c = r["citations"][0]
        L.append(f"**A:** {r['answer']}")
        L.append(f"- Citation: {c['title']} [{c['doc_id']} > {c['section']}], effective {c['effective_date']} (verified={r['citations_verified']})")
    return "\n".join(L)
