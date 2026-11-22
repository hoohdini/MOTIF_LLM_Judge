"""revise 판정 atom의 자동 분리·수정. 결과는 revisions 원장에 추가되고, 새 atom은 새 해시를 갖기 때문에
다음 `run --stage card`에서 그 atom만 다시 검수된다. 원본 카드 스냅샷은 건드리지 않는다."""
import json
from string import Template
from .common import now, load_prompt, parse_json
from .aggregate import decide_card
from .prechecks import CODE_VERSION
from . import judges as J


def run_revise(store, ctx, judge_id="reviser", limit=None):
    cfg = ctx.cfg; P = load_prompt("prompts/atom_revise.v2.md")
    dec = decide_card(ctx); done = fail = 0
    targets = [(c, a) for c in ctx.cards for a in c["atoms"] if dec[a["atom_id"]]["decision"] == "revise"]
    run_id, rdir = store.new_run("revise", {"judge": cfg["judges"][judge_id], "targets": len(targets)}) if targets else (None, None)
    for c, a in targets[:limit]:
        d = dec[a["atom_id"]]
        findings = "\n".join(f"- {n}: {'/'.join(sorted(set(r['by'].values()) - {'pass'})) or r['v']} — {' / '.join(f'{j}: {w}' for j, w in r['why'].items())}" for n, r in d["checks"].items()
                             if r["v"] not in ("pass", "pending") and not n.startswith("A_"))
        ev = {e["id"]: e for e in a["evidence"]}
        user = Template(P["user"]).safe_substitute(concept=c["concept_name"], atom_id=a["atom_id"], scope=a["scope"], statement=a["statement"],
                                                   evidence="\n".join(f"[{i}] {e['text']}" for i, e in ev.items()), findings=findings)
        spec = {"kind": "revise", "statement": a["statement"], "scope": a["scope"], "evidence_ids": list(ev)}
        err = None
        try:
            raw, usage = J.call(judge_id, cfg["judges"][judge_id], P["system"], user, spec)
            parsed = parse_json(raw, "atoms")
        except Exception as e:                                      # noqa: BLE001
            raw, usage, parsed, err = None, {}, None, repr(e)
        (rdir / "raw" / f"{a['atom_id']}.json").write_text(json.dumps(
            {"atom_id": a["atom_id"], "system": P["system"], "user": user, "raw": raw, "usage": usage, "error": err}, ensure_ascii=False, indent=1), encoding="utf-8")
        rnd = a.get("rev_round", 0) + 1
        good = [x for x in (parsed or {}).get("atoms", []) if x.get("statement") and x.get("scope") in ("S1", "S2", "S3")
                and x.get("evidence_ids") and set(x["evidence_ids"]) <= set(ev)]
        if not good:                                                # 못 고친 atom은 지우지 않고 사람에게 넘긴다
            store.add_verdicts([{"ts": now(), "run_id": run_id, "stage": "card", "group": "code", "unit_type": "atom", "unit_id": a["atom_id"],
                                 "unit_hash": a["_hash"], "check": "REVISE_FAILED", "v": "hold", "judge": "code", "rep": 0, "prompt_hash": CODE_VERSION,
                                 "why": err or (("reviser_excluded: " + (parsed.get("note") or "")) if parsed is not None and not parsed.get("atoms") else None)
                                 or (parsed or {}).get("note") or "수정본이 규칙(근거 ID·S 라벨)을 만족하지 못함"}])
            fail += 1; continue
        base = a["atom_id"].split(".r")[0]
        new = [{"atom_id": f"{base}.r{rnd}{'abc'[k] if len(good) > 1 else ''}", "scope": x["scope"], "statement": x["statement"],
                "evidence": [ev[i] for i in x["evidence_ids"]], "support": a.get("support"), "flags": sorted(set(a.get("flags") or []) | {"revised"}),
                "revision_of": a["atom_id"], "rev_round": rnd} for k, x in enumerate(good[:3])]
        with store.revisions.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": now(), "run_id": run_id, "parent_atom_id": a["atom_id"], "parent_hash": a["_hash"], "card_id": c["card_id"],
                                "new_atoms": new, "reviser": judge_id, "findings": findings}, ensure_ascii=False) + "\n")
        done += 1
    print(f"revise: 대상 {len(targets)}, 수정 {done}, 실패(사람에게) {fail}")
