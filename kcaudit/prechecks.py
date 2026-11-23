"""LLM 없이 코드로 잡는 검사. 판정은 judge='code'로 같은 원장에 쌓인다."""
import re
from .common import now

CODE_VERSION = "code.v1"
# severity: blocker는 단위 판정에 반영, warn은 표시만
CODE_CHECKS = {
    "card": {"A_SCHEMA": "blocker", "REVISE_FAILED": "blocker", "A_EVIDENCE_LE3": "warn", "A_GARBLED": "warn",
             "A_ATTRIBUTION": "warn", "A_NUMBER_REF": "warn"},
    "item": {"I_SCHEMA": "blocker", "I_ID": "blocker", "I_KEY_FORMAT": "blocker", "I_SOURCE_REGEX": "warn", "I_GARBLED": "warn"},
    "answer": {"ANSWER_LABEL": "blocker"},
}
ATTRIB = re.compile(r"\b(the|these) (authors?|editors?)\b|\bauthors'|\baccording to the (book|handbook|text|chapter)\b|\bhas been (called|termed|said)\b|\bwas said to\b", re.I)
NUMREF = re.compile(r"\b(Lemma|Theorem|Proposition|Corollary|Section|Table|Figure|Fig\.|Equation|Chapter)\s+\d", re.I)
SOURCE = re.compile(r"\baccording to\b|\bthe authors?\b|\bet al\b|\b(the|this) (book|handbook|text|chapter|review|study|monograph|paper)\b", re.I)


def _row(stage, utype, uid, uhash, check, ok, why=""):
    return {"ts": now(), "run_id": "precheck", "stage": stage, "group": "code", "unit_type": utype, "unit_id": uid,
            "unit_hash": uhash, "check": check, "v": "pass" if ok else "fail", "why": why, "judge": "code", "rep": 0,
            "prompt_hash": CODE_VERSION}


def atoms(cards):
    rows = []
    for c in cards:
        for a in c["atoms"]:
            r = lambda ck, ok, why="": rows.append(_row("card", "atom", a["atom_id"], a["_hash"], ck, ok, why))
            ev = a.get("evidence") or []
            r("A_SCHEMA", bool(a.get("statement", "").strip()) and a.get("scope") in ("S1", "S2", "S3") and len(ev) >= 1, "빈 문장·S 라벨·근거 없음")
            r("A_EVIDENCE_LE3", len(ev) <= 3, f"근거 문장 {len(ev)}개")
            r("A_GARBLED", not a["_garbled"], "근거 텍스트에 깨진 기호")
            r("A_ATTRIBUTION", not ATTRIB.search(a["statement"]), "저자 의견·전언 표현")
            r("A_NUMBER_REF", not NUMREF.search(a["statement"]), "정리·표·절 번호 인용")
    return rows


def items(items_):
    rows = []
    for it in items_:
        r = lambda ck, ok, why="": rows.append(_row("item", "item", it["item_id"], it["_hash"], ck, ok, why))
        f, ans, opts = it.get("format"), it.get("answer"), it.get("options") or {}
        r("I_SCHEMA", all(it.get(k) for k in ("item_id", "atom_id", "format", "question", "atom_statement")), "필수 필드 누락")
        r("I_ID", it["item_id"] == f"{it['atom_id']}-{it.get('mode')}-{f}", "item_id가 atom·모드·형식과 불일치")
        ok = {"TF": ans in ("True", "False"), "YN": ans in ("Yes", "No"),
              "MCQ": sorted(opts) == list("ABCD") and len(set(opts.values())) == 4 and ans in opts,
              "OPEN": 1 <= len(it.get("key_points") or []) <= 3}.get(f, False)
        r("I_KEY_FORMAT", ok, "정답 라벨·보기·key_points 형식 오류")
        m = SOURCE.search(it["question"])
        r("I_SOURCE_REGEX", not m, f"출처 표현 후보: {m.group(0)}" if m else "")
        r("I_GARBLED", not it["_garbled"], "근거 텍스트에 깨진 기호")
    return rows


def _label(fmt, text):
    """답변에서 라벨 하나를 읽는다. 확실하지 않으면 None(보류). 틀리게 읽느니 사람에게 넘긴다."""
    t = re.sub(r"[*_`]+", "", text).strip()          # **B**, `True` 같은 마크다운 강조는 벗긴다
    pats = {"TF": ("true", "false", "True", "False"), "YN": ("yes", "no", "Yes", "No")}
    if fmt in pats:
        a, b, la, lb = pats[fmt]
        lead = re.match(rf"\W*({a}|{b})\b", t, re.I)
        if lead:                                              # 첫 단어가 라벨이면 그것을 답으로 본다
            return la if lead.group(1).lower() == a else lb
        ha, hb = re.search(rf"\b{a}\b", t, re.I), re.search(rf"\b{b}\b", t, re.I)
        return None if bool(ha) == bool(hb) else (la if ha else lb)
    found = set(re.findall(r"\b(?:answer|option|choice)\s*(?:is|:)?\s*\(?([A-D])\)?(?![A-Za-z])", t, re.I))
    m = re.match(r"\s*\(?([A-D])(?:\)|[.:])?(?:\s|$)", t)
    if m and (len(t) <= 3 or re.match(r"\s*(\([A-D]\)|[A-D][).:])", t)):
        found.add(m.group(1))
    return found.pop().upper() if len(found) == 1 else None


def answers(answers_):
    """TF·YN·MCQ는 라벨만 파싱해 코드로 채점한다. 라벨을 하나로 못 읽으면 보류."""
    rows = []
    for a in answers_:
        it = a["_item"]
        if it["format"] == "OPEN":
            continue
        lab = _label(it["format"], a["response"])
        v = "hold" if lab is None else ("correct" if lab == it["answer"] else "incorrect")
        row = _row("answer", "answer", a["_id"], a["_hash"], "ANSWER_LABEL", True, "" if lab else "라벨을 하나로 읽지 못함")
        row["v"] = v; row["extra"] = {"parsed": lab}
        rows.append(row)
    return rows


def write_new(store, rows):
    """처음 보는 단위이거나, 코드가 바뀌어 값이 달라진 경우만 덧붙인다 (같은 키는 나중 행이 앞의 행을 대신한다)."""
    seen = {}
    for r in store.all_verdicts():
        if r["judge"] == "code":
            seen[(r["unit_id"], r["unit_hash"], r["check"])] = r["v"]
    new = [r for r in rows if seen.get((r["unit_id"], r["unit_hash"], r["check"])) != r["v"]]
    store.add_verdicts(new)
    return len(new)
