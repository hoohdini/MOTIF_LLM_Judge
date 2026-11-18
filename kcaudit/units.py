"""검수 단위(atom, item, answer)와 내용 해시. 수정본(revision)은 원본 위에 덧씌워 읽는다."""
import re
from .common import h

GARBLED = re.compile("[�-]")


def atom_hash(card, a):
    return h([card["concept_name"], a["scope"], a["statement"], [(e["id"], e["text"]) for e in a.get("evidence", [])]])


def load_cards(store, as_of=None, sha=None):
    """활성 카드 스냅샷 + 자동 분리/수정 결과. 부모 atom의 해시가 수정 당시와 같을 때만 교체한다."""
    cards = store.snapshot("cards", sha)
    revs = {}
    for r in store.all_revisions(as_of):
        revs[(r["parent_atom_id"], r["parent_hash"])] = r           # 같은 부모는 마지막 기록이 유효
    for c in cards:
        out = []
        for a in c["atoms"]:
            r = revs.get((a["atom_id"], atom_hash(c, a)))
            if r is None:
                out.append(a)
            else:
                out += r["new_atoms"]                               # 빈 목록이면 atom 폐기
        c["atoms"] = out
        for a in c["atoms"]:
            a["_hash"] = atom_hash(c, a)
            a["_garbled"] = any(GARBLED.search(e["text"]) for e in a.get("evidence", []))
    return cards


def item_hash(it):
    return h([it["format"], it["question"], it["answer"], it.get("options"), it.get("key_points"), it["atom_statement"]])


def load_items(store, sha=None):
    items = store.snapshot("items", sha)
    for it in items:
        it["_hash"] = item_hash(it)
        it["_garbled"] = any(GARBLED.search(e) for e in it.get("evidence", []))
    return items


def answer_id(a):
    return f"{a['item_id']}::{a['model']}::{a.get('rep', 0)}"


def load_answers(store, items_by_id, sha=None):
    """answers.jsonl 한 줄: {item_id, model, response, rep(선택)}"""
    out = []
    for a in store.snapshot("answers", sha):
        it = items_by_id.get(a["item_id"])
        if it is None:
            continue
        a["_id"] = answer_id(a); a["_hash"] = h([a["response"], it["_hash"]]); a["_item"] = it
        out.append(a)
    return out
