"""릴리스 = 원본 스냅샷 + 원장의 특정 시점 + 정책으로 만든 승인본. 지우지 않고 쌓으며, 롤백은 CURRENT 포인터만 옮긴다.
manifest에 스냅샷 해시·원장 위치·프롬프트 해시가 남아서 `verify`로 같은 결과가 다시 나오는지 확인할 수 있다."""
import json, shutil
from collections import Counter
from .common import ROOT, now, fhash, load_yaml
from .aggregate import Ctx, Registry, decide_card, decide_item, decide_answer


def _clean(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


def _files(ctx):
    ad, idec = decide_card(ctx), decide_item(ctx)
    cards = []
    for c in ctx.cards:
        keep = [_clean(a) for a in c["atoms"] if ad[a["atom_id"]]["decision"] == "pass"]
        cards.append({**_clean(c), "atoms": keep, "status": "audited"})
    brief = lambda d: {"unit_id": d["unit_id"], "unit_hash": d["unit_hash"], "decision": d["decision"], "blocked_by": d.get("blocked_by", ""),
                       "checks": {n: {"v": r["v"], "src": r["src"], "by": r["by"], "why": r["why"]} for n, r in d["checks"].items() if r["v"] != "pass"}}
    act = {"atom_changed": "regenerate_for_new_atom", "atom_fail": "drop"}      # atom이 아직 보류·수정 대기면 목록에 넣지 않는다
    regen = [{"item_id": u, "action": act.get(d["blocked_by"], "regenerate"), "reason": d["blocked_by"] or "audit_fail",
              "failed": {n: " / ".join(r["why"].values()) for n, r in d["checks"].items() if r["v"] == "fail" or "fail" in r["by"].values()}}
             for u, d in idec.items() if d["decision"] == "fail" or d["blocked_by"] in act]
    out = {"cards_approved.jsonl": cards,
           "items_approved.jsonl": [_clean(i) for i in ctx.items if idec[i["item_id"]]["decision"] == "pass"],
           "atoms_status.jsonl": [brief(d) for d in ad.values()],
           "items_status.jsonl": [brief(d) for d in idec.values()],
           "regen_requests.jsonl": regen}                              # 문항 생성 쪽에 넘길 재생성 목록과 사유
    if ctx.answers:
        an = decide_answer(ctx)
        out["answers_scored.jsonl"] = [{k: d[k] for k in ("unit_id", "item_id", "model", "format", "decision", "own")} for d in an.values()]
    counts = {"atoms": dict(Counter(d["decision"] for d in ad.values())), "items": dict(Counter(d["decision"] for d in idec.values()))}
    return out, counts


def code_hash():
    import hashlib
    return hashlib.sha256(b"".join(p.read_bytes() for p in sorted((ROOT / "kcaudit").glob("*.py")))).hexdigest()[:12]


def _dump(rows):
    return "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)


def build(store, cfg, reg, tag, note=""):
    d = store.root / "releases" / tag
    if d.exists():
        raise SystemExit(f"릴리스 {tag}가 이미 있습니다. 릴리스는 덮어쓰지 않습니다.")
    from . import prechecks
    c0 = Ctx(store, cfg, reg)
    prechecks.write_new(store, prechecks.atoms(c0.cards) + prechecks.items(c0.items) + prechecks.answers(c0.answers))
    offsets = store.offsets(); ctx = Ctx(store, cfg, reg, as_of=offsets)
    files, counts = _files(ctx)
    d.mkdir(parents=True)
    for name, rows in files.items():
        (d / name).write_text(_dump(rows), encoding="utf-8")
    shutil.copy(ROOT / "checks.yaml", d / "checks.yaml")
    (d / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copytree(ROOT / "prompts", d / "prompts")
    man = {"tag": tag, "created_at": now(), "note": note, "snapshots": store.active(), "offsets": offsets, "prompt_hashes": ctx.phash, "code": code_hash(),
           "counts": counts, "files": {n: fhash(d / n) for n in files}}
    (d / "manifest.json").write_text(json.dumps(man, ensure_ascii=False, indent=1), encoding="utf-8")
    store.set_current(tag, f"build: {note}")
    print(f"릴리스 {tag}: {counts}")
    return man


def verify(store, tag):
    """릴리스를 manifest만으로 다시 만들어 파일 해시가 같은지 확인."""
    d = store.root / "releases" / tag
    man = json.loads((d / "manifest.json").read_text())
    cfg = json.loads((d / "config.json").read_text(encoding="utf-8")); reg = Registry(base=d)
    ctx = Ctx(store, cfg, reg, as_of=man["offsets"], snaps=man["snapshots"], prompt_hashes=man["prompt_hashes"])
    files, _ = _files(ctx)
    import hashlib
    bad = [n for n, rows in files.items() if hashlib.sha256(_dump(rows).encode()).hexdigest() != man["files"].get(n)]
    if man.get("code") != code_hash():
        print(f"  주의: 릴리스 당시와 코드가 다릅니다 ({man.get('code')} → {code_hash()}). 불일치가 나오면 git에서 당시 코드로 확인하세요.")
    print(f"{tag}: " + ("재현 일치" if not bad else f"불일치 {bad}"))
    return not bad
