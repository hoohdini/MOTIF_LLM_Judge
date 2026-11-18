"""프롬프트 수정 전(v1)과 후(v2)의 저지 판정을 '보정 기준'에 대해 비교한다.

보정 기준 = 사람 라벨(240개)에서 판정(adjudication)한 42건만 판정 결과로 바꾼 것.
사용: python analysis/compare_v2.py   (v2 보정 실행 뒤)
출력: analysis/results/calib_v1_vs_v2.md

- v2 = 지금 checks.yaml·프롬프트의 해시로 적재된 판정, v1 = 그 이전 해시 중 가장 많이 쓰인 것.
- 사람이 판정하지 않은 체크(NO_OVERLAP, CENTRALITY, NO_INTRA_CARD_OVERLAP)는 뺀다.
- 단위 판정: fail > hold > revise > pass. hold는 비교에서 제외. 이진 = pass 대 비pass.
"""
import csv, json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kcaudit.stats import agreement  # noqa: E402
from kcaudit.aggregate import Registry  # noqa: E402

SKIP = {"NO_OVERLAP", "CENTRALITY", "NO_INTRA_CARD_OVERLAP"}
ORDER = {"fail": 3, "hold": 2, "revise": 1, "pass": 0}
JUDGES = {"judge_a": "GPT", "judge_b": "Gemini"}
GROUP = {"card": "atom_audit", "item": "item_audit"}
b = lambda v: "pass" if v == "pass" else "nonpass"

rows = [json.loads(l) for l in open(Path(sys.argv[1] if len(sys.argv) > 1 else ROOT / "store") / "ledger/verdicts.jsonl", encoding="utf-8")]
ref, ref_src = {}, {}
for r in rows:
    if r["judge"].startswith("human:") and r["check"] == "_UNIT":
        ref[r["unit_id"]] = r["v"]; ref_src[r["unit_id"]] = "human"
adj = {r["unit_id"]: r for r in csv.DictReader(open(ROOT / "analysis/results/adjudication_p1.csv", encoding="utf-8-sig"))}
for u, r in adj.items():
    ref[u] = r["adjudicated_v"]; ref_src[u] = "adjudicated"
stage_of = {}
for st in ("card", "item"):
    for r in csv.DictReader(open(ROOT / f"calib/calib_{st}.csv", encoding="utf-8-sig")):
        stage_of[r["unit_id"]] = st

reg = Registry("checks.yaml", ROOT)
cur = {st: reg.prompt_hash(g) for st, g in GROUP.items()}
per = defaultdict(lambda: defaultdict(lambda: defaultdict(dict)))   # phash -> judge -> unit -> check -> v
latest = {}
for r in rows:
    if r["judge"] in JUDGES and r["unit_id"] in stage_of and r["check"] not in SKIP:
        k = (r.get("prompt_hash"), r["judge"], r["unit_id"], r["check"])
        if k not in latest or r["ts"] >= latest[k]:
            latest[k] = r["ts"]; per[r.get("prompt_hash")][r["judge"]][r["unit_id"]][r["check"]] = r["v"]
old = {}
for st in GROUP:
    c = Counter(ph for ph, js in per.items() if ph != cur[st] for u in js.get("judge_a", {}) if stage_of[u] == st)
    old[st] = c.most_common(1)[0][0] if c else None


def unit_dec(ph, j, st):
    return {u: max(cs.values(), key=lambda v: ORDER.get(v, 2)) for u, cs in per.get(ph, {}).get(j, {}).items()
            if stage_of[u] == st and cs}


out = ["# 프롬프트 수정 전후 비교 (보정 기준 = 사람 라벨 + 판정 42건)", ""]
for st in GROUP:
    out += [f"## {st}", "", "| 저지 | 버전 | n | κ (이진) | 일치 | 판정 42건 중 맞음 | 심각도 일치(카드) | hold 수 |", "|---|---|---|---|---|---|---|---|"]
    for j, name in JUDGES.items():
        for ver, ph in (("v1", old[st]), ("v2", cur[st])):
            d = unit_dec(ph, j, st)
            if not d:
                out.append(f"| {name} | {ver} | 0 | – | – | – | – | – |"); continue
            pairs = [(b(ref[u]), b(v)) for u, v in d.items() if u in ref and ref[u] != "hold" and v != "hold"]
            a = agreement(pairs)
            au = [u for u in d if u in adj and stage_of[u] == st and d[u] != "hold"]
            ok = sum(b(d[u]) == b(ref[u]) for u in au)
            sev = f"{sum(d[u] == ref[u] for u in au)}/{len(au)}" if st == "card" else "–"
            out.append(f"| {name} | {ver} | {a['n']} | {a['kappa']} | {a['agree']} | {ok}/{len(au)} | {sev} | {sum(v == 'hold' for v in d.values())} |")
    out.append("")
miss = ["IVFLUID-C04-S1-03-M3-YN", "NACHR-C15-S1-02-M2-TF"]
out += ["## 사람이 맞았던 2건 (v2에서 비pass가 나와야 함)", ""]
for u in miss:
    out.append(f"- {u}: " + ", ".join(f"{JUDGES[j]} {unit_dec(cur['item'], j, 'item').get(u, '미실행')}" for j in JUDGES))
p = ROOT / "analysis/results/calib_v1_vs_v2.md"
p.write_text("\n".join(out) + "\n", encoding="utf-8")
print("\n".join(out))
