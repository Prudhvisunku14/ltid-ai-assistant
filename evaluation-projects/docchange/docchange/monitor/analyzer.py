"""INTERPRETATION layer. Rule-based heuristics that flag changes possibly affecting
software requirements. Output is advisory and always labelled as unverified.
Swap `analyze_change` for an LLM call if desired; keep the 'interpretation' label."""
import re

LABEL = "AI/heuristic interpretation - not verified, review the evidence"
STRONG = re.compile(r"\b(shall|must|required?|requires|mandatory)\b", re.I)
NEGATED = re.compile(r"\b(?:not|never|no longer)\s+(?:be\s+)?(?:required|mandatory)\b", re.I)
REQ_SECTION = re.compile(r"requirement|acceptance|functional|evidence", re.I)  # lines here are normative even without shall/must
WEAK = re.compile(r"\b(should|may|might|can|optional|recommended|where possible)\b", re.I)
NUM = re.compile(r"(?:\b(?:JPY|USD|EUR|GBP|INR)\s?|[$¥€£])\d[\d,]*(?:\.\d+)?|\b\d+(?:[.,]\d+)?\s?(?:(?:calendar|working|business)\s)?(?:ms|s|sec|seconds?|minutes?|min|hours?|hrs?|days?|months?|years?|%|gb|mb|tb|kb|users?|requests?|rps|vehicles?|devices?|characters?|chars)?\b", re.I)
REQ_ID = re.compile(r"\b[A-Z]{2,6}-\d{1,4}\b")
CATS = {
    "performance": r"latency|response time|throughput|uptime|availability|\bsla\b|scal|concurren|\bms\b",
    "security": r"encrypt|authenticat|authoriz|password|\bmfa\b|\b2fa\b|token|\btls\b|\bssl\b|access control|vulnerab|audit log",
    "privacy/compliance": r"gdpr|retention|personal data|\bpii\b|consent|compliance|regulat|iso ?\d+|delet|anonymi",
    "integration/API": r"\bapi\b|endpoint|webhook|integration|schema|protocol|\brest\b|oauth|deprecat",
    "data": r"database|storage|backup|\bdata\b|record|export|import|migration",
    "user interface": r"\bui\b|screen|dashboard|display|notification|report",
    "constraints/schedule": r"deadline|milestone|release|budget|platform|supported|browser|android|\bios\b",
}


def _nums(lines):
    """Numbers with a unit always count; bare numbers only on lines with mandatory/advisory wording
    (avoids noise such as 'Draft 2' -> 'Draft 3')."""
    out = []
    for l in lines:
        l = re.sub(r"\d{4}-\d{2}-\d{2}", "", l)  # ignore ISO dates
        modal = bool(STRONG.search(l) or WEAK.search(l))
        for m in NUM.finditer(REQ_ID.sub("", l)):
            t = m.group(0).strip()
            if re.search(r"\d", t) and (modal or re.search(r"[a-z%¥$€£]", t, re.I)): out.append(t)
    return out


def analyze_change(c):
    before, after = " ".join(c["before"]), " ".join(c["after"])
    text = before + " " + after
    reasons, score = [], 0
    rs = bool(REQ_SECTION.search(c["section"]))
    is_strong = lambda l: rs or bool(STRONG.search(NEGATED.sub("", l)))
    nsb, nsa = sum(map(is_strong, c["before"])), sum(map(is_strong, c["after"]))
    sb, sa = nsb > 0, nsa > 0
    wb, wa = bool(WEAK.search(NEGATED.sub("", before))), bool(WEAK.search(NEGATED.sub("", after)))
    nb, na = _nums(c["before"]), _nums(c["after"])

    if c["kind"] in ("removed", "section_removed") and sb:
        reasons.append("A mandatory statement (shall/must/required) was removed - a requirement may have been dropped."); score += 4
    elif c["kind"] in ("added", "section_added") and sa:
        reasons.append("A new mandatory statement (shall/must/required) was added - a new requirement may exist."); score += 3
    elif c["kind"] == "modified":
        if sb and not sa and wa:
            reasons.append("Obligation weakened (mandatory -> advisory wording)."); score += 3
        elif wb and not sb and sa:
            reasons.append("Obligation strengthened (advisory -> mandatory wording)."); score += 3
        if nb != na and (nb or na):
            reasons.append(f"Numeric value(s) changed: {', '.join(nb) or '-'} -> {', '.join(na) or '-'}. Thresholds/limits may need re-implementation or re-testing."); score += 2
        if nsa > nsb:
            reasons.append(f"{nsa - nsb} more mandatory statement(s) after the change ({nsb} -> {nsa}) - new obligations may have been introduced."); score += 2
        elif nsb > nsa:
            reasons.append(f"{nsb - nsa} fewer mandatory statement(s) after the change ({nsb} -> {nsa}) - obligations may have been dropped."); score += 3
        if sb and sa and not reasons:
            reasons.append("Wording of a mandatory statement changed; check whether scope or behaviour differs."); score += 2
    if c["kind"] in ("modified", "added", "section_added") and re.search(r"deprecat|will be removed|no longer (?:supported|available)|end of life", after, re.I) \
            and not re.search(r"deprecat|will be removed|no longer", before, re.I):
        reasons.append("Deprecation / removal notice introduced - dependent features or integrations may need changes."); score += 3
    pb, pa = set(re.findall(r"/v\d+/\w+", before)), set(re.findall(r"/v\d+/\w+", after))
    if c["kind"] == "modified" and pb != pa:
        reasons.append(f"API endpoint path(s) changed: {', '.join(sorted(pb - pa)) or '-'} -> {', '.join(sorted(pa - pb)) or '-'}. Clients/contract tests are affected."); score += 3
    if c["kind"] == "section_renamed":
        reasons.append("Section renamed; traceability links to this heading may break."); score += 1
    if c["kind"] in ("added", "removed", "section_added", "section_removed") and not reasons:
        reasons.append("Content added/removed; relevance to requirements unclear."); score += 1

    cats = [k for k, rx in CATS.items() if re.search(rx, text, re.I)]
    if cats and score and any(k in cats for k in ("security", "privacy/compliance", "integration/API")):
        score += 1
    ids = sorted(set(REQ_ID.findall(text)))
    sev = "high" if score >= 4 else "medium" if score >= 2 else "low"
    return {"change_id": c["id"], "severity": sev, "score": score, "categories": cats,
            "requirement_ids": ids, "reasons": reasons, "requirement_impact": score >= 2, "label": LABEL}


def analyze(changes):
    items = [analyze_change(c) for c in changes]
    order = {"high": 0, "medium": 1, "low": 2}
    imp = [i for i in items if i["requirement_impact"]]
    hi = sum(i["severity"] == "high" for i in items)
    txt = (f"{len(imp)} of {len(items)} change(s) may affect software requirements ({hi} high severity)."
           if items else "No changes to interpret.")
    cats = sorted({c for i in imp for c in i["categories"]})
    if cats: txt += " Areas touched: " + ", ".join(cats) + "."
    return {"items": {i["change_id"]: i for i in items},
            "summary": {"text": txt, "label": LABEL, "high": hi, "impacting": len(imp),
                        "max_severity": min((i["severity"] for i in items), key=order.get, default="none")}}
