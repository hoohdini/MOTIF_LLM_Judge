"""사람 검수. 사람은 (1) 저지가 엇갈리거나 보류한 것, (2) 만장일치 판정의 무작위 표본만 본다.
사람의 결정도 judge='human:<이름>'으로 같은 원장에 쌓이고, 합산 때 최우선으로 적용된다."""
import csv, random
from .common import now, book_of
from .aggregate import DECIDE

COLS = ["stage", "kind", "unit_id", "unit_hash", "check", "llm", "why", "content", "human_v", "human_note"]


def _content(ctx, stage, uid):
    if stage == "card":
        for c in ctx.cards:
            for a in c["atoms"]:
                if a["atom_id"] == uid:
                    return f"[{c['concept_name']}] ({a['scope']}) {a['statement']}\n근거: " + " | ".join(e["text"] for e in a["evidence"])
    if stage == "item":
        it = ctx.items_by_id[uid]
        return f"{it['question']}\n정답: {it['answer'] or it.get('key_points')}\natom: {it['atom_statement']}"
    a = next(x for x in ctx.answers if x["_id"] == uid); it = a["_item"]
    return f"Q: {it['question']}\nkey: {it.get('key_points') or it['answer']}\n답변: {a['response']}"


def _write(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(rows)


def export(store, ctx, stage, rate=None, blind=True):
    dec = DECIDE[stage](ctx); rows = []
    rate = ctx.cfg["policy"]["human_sample_rate"] if rate is None else rate
    rng = random.Random(f"{ctx.cfg['policy']['seed']}:sample:{stage}")
    for uid, d in dec.items():
        if d["decision"] == "hold" or (stage == "answer" and d["own"] == "hold"):
            for n, r in d["checks"].items():
                if r["v"] == "hold":
                    rows.append({"stage": stage, "kind": "queue", "unit_id": uid, "unit_hash": d["unit_hash"], "check": n,
                                 "llm": " ".join(f"{j}={v}" for j, v in r["by"].items()) or r["src"],
                                 "why": " / ".join(f"{j}: {w}" for j, w in r["why"].items()), "content": _content(ctx, stage, uid)})
        elif d["decision"] in ("pass", "fail", "revise", "correct", "partial", "incorrect") and not d.get("human") and rng.random() < rate:
            rows.append({"stage": stage, "kind": "sample", "unit_id": uid, "unit_hash": d["unit_hash"], "check": "_UNIT",
                         "llm": "" if blind else d["decision"], "why": "", "content": _content(ctx, stage, uid)})   # 표본은 LLM 판정을 가리고 본다
    path = store.root / "human" / f"queue_{stage}_{now()[:10]}.csv"
    _write(path, rows)
    print(f"{path}: 보류 {sum(r['kind'] == 'queue' for r in rows)}행, 표본 {sum(r['kind'] == 'sample' for r in rows)}행")
    return path


def calib_sample(store, ctx, stage, n):
    """저지 선정용 보정 세트. 책별로 고르게, 절반은 문제 소지가 있는 단위(사전 점검·코드 플래그)에서 뽑는다."""
    rng = random.Random(f"{ctx.cfg['policy']['seed']}:calib:{stage}")
    if stage == "card":
        units = [(a["atom_id"], a["_hash"]) for c in ctx.cards for a in c["atoms"]]
    else:
        units = [(i["item_id"], i["_hash"]) for i in ctx.items]
    flagged = {r["unit_id"] for r in ctx.rows if r["v"] != "pass" and "GARBLED" not in r["check"]      # 깨진 수식은 책 전체에 걸려서 제외
               and (r["judge"] == "code" or r["judge"].startswith("preaudit:"))}
    if stage == "item":
        flagged |= {i["item_id"] for i in ctx.items if i["atom_id"] in flagged or i.get("flags")}
    picked = []
    for pool, k in (([u for u in units if u[0] in flagged], n // 2), ([u for u in units if u[0] not in flagged], n - n // 2)):
        by_book = {}
        for u in pool:
            by_book.setdefault(book_of(u[0]), []).append(u)
        for b in by_book.values():
            rng.shuffle(b)
        while k > 0 and any(by_book.values()):
            for b in sorted(by_book):
                if by_book[b] and k > 0:
                    picked.append(by_book[b].pop()); k -= 1
    rng.shuffle(picked)                                             # 앞에서부터 일부만 채워도 책·플래그가 섞이도록
    rows = [{"stage": stage, "kind": "calib", "unit_id": u, "unit_hash": hsh, "check": "_UNIT", "llm": "", "why": "", "content": _content(ctx, stage, u)}
            for u, hsh in picked]
    path = store.root / "human" / f"calib_{stage}.csv"; _write(path, rows)
    ids = store.root / "human" / f"calib_{stage}.ids.txt"; ids.write_text("\n".join(u for u, _ in picked), encoding="utf-8")
    print(f"{path}: {len(rows)}행 (human_v에 pass/revise/fail을 채운 뒤 `human import`). 저지 실행은 `run --only {ids}`")
    return path


def import_csv(store, path, reviewer):
    rows = []
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f):
            v = (r.get("human_v") or "").strip()
            if v:
                rows.append({"ts": now(), "run_id": "human", "stage": r["stage"], "group": "human", "unit_type": {"card": "atom"}.get(r["stage"], r["stage"]),
                             "unit_id": r["unit_id"], "unit_hash": r["unit_hash"], "check": r["check"], "v": v, "why": r.get("human_note", ""),
                             "judge": f"human:{(r.get('reviewer') or '').strip() or reviewer}", "rep": 0, "extra": {"source": r["kind"]}})
    store.add_verdicts(rows)
    print(f"사람 판정 {len(rows)}행 적재: " + ", ".join(f"{k} {v}" for k, v in __import__("collections").Counter(r["judge"] for r in rows).items()))
