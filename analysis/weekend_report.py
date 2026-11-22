"""주말 검수 집계표. 최초 결과와 수정·재검수 후 결과를 따로 낸다 (hold는 pass에 넣지 않는다).

사용: python analysis/weekend_report.py --store store_a8 --data data_in/a8 [--only ids/xxx.txt] [--out report.md]
  --data  : 그 묶음의 입력 폴더. omitted/*.jsonl(생성 생략)과 design.jsonl(설계 칸)이 있으면 분모에 반영한다.
  --only  : 단위 id 목록 파일. 주면 그 atom·문항만 집계한다 (9권 비교의 표본 카드 등).
"""
import argparse, ast, json, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kcaudit.common import load_yaml, read_jsonl          # noqa: E402
from kcaudit.store import Store                           # noqa: E402
from kcaudit.aggregate import Ctx, Registry, decide_card, decide_item   # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="config.yaml"); ap.add_argument("--store", required=True)
ap.add_argument("--data"); ap.add_argument("--only"); ap.add_argument("--out")
a = ap.parse_args()
cfg = load_yaml(ROOT / a.config); cfg["store"] = a.store
store, reg = Store(a.store), Registry()
only = set(Path(a.only).read_text(encoding="utf-8").split()) if a.only else None
keep = lambda u: only is None or u in only
pct = lambda n, d: f"{n}/{d} ({100 * n / d:.1f}%)" if d else f"{n}/0"
L = []; P = L.append

first = Ctx(store, cfg, reg, as_of={"revisions": 0})      # 자동 수정 이전 상태 (원본 atom)
last = Ctx(store, cfg, reg)                               # 지금 상태 (수정본 반영)

# ---- atom ----
d0 = {u: d for u, d in decide_card(first, use_human=False).items() if keep(u)}
d1 = {u: d for u, d in decide_card(last).items() if keep(u.split(".r")[0])}
judged0 = {u: d for u, d in d0.items() if d["decision"] != "pending"}
c0 = Counter(d["decision"] for d in d0.values())
P(f"# 검수 집계 — {a.store}" + (f" (표본 {a.only})" if a.only else "")); P("")
P("## atom"); P("")
P(f"- 원본 atom {len(d0)}개, 검수 완료 {len(judged0)}개, 미검수(pending) {c0['pending']}개")
P(f"- **최초 통과율**: {pct(c0['pass'], len(judged0))}")
P(f"- 최초 판정 분포: " + ", ".join(f"{k} {v}" for k, v in c0.most_common()))
rev = [u for u in d1 if ".r" in u]
if rev:
    cr = Counter(d1[u]["decision"] for u in rev)
    P(f"- 자동 수정본 {len(rev)}개 (원본 {len({u.split('.r')[0] for u in rev})}개에서): " + ", ".join(f"{k} {v}" for k, v in cr.most_common()))
c1 = Counter(d["decision"] for d in d1.values())
P(f"- **수정·재검수 후**: 현재 atom {len(d1)}개 — " + ", ".join(f"{k} {v}" for k, v in c1.most_common()))


def by_check(dec):
    anyf, both = Counter(), Counter()
    for d in dec.values():
        for n, r in d["checks"].items():
            vs = [v for v in r["by"].values() if v != "pending"]
            if any(v not in ("pass",) for v in vs):
                anyf[n] += 1
            if vs and all(v not in ("pass",) for v in vs):
                both[n] += 1
            if not r["by"] and r["v"] not in ("pass", "pending"):
                anyf[n] += 1; both[n] += 1                   # 코드 사전검사
    return anyf, both


def check_table(dec):
    anyf, both = by_check(dec)
    if anyf:
        P(""); P("| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |"); P("| --- | --- | --- |")
        for n, k in anyf.most_common():
            P(f"| {n} | {k} | {both[n]} |")


check_table(d0)

# ---- 문항 ----
i0 = {u: d for u, d in decide_item(first, use_human=False).items() if keep(u)}
i1 = {u: d for u, d in decide_item(last).items() if keep(u)}
omitted = design = None
if a.data:
    om = [r for p in sorted((ROOT / a.data / "omitted").glob("*.jsonl")) for r in read_jsonl(p)] if (ROOT / a.data / "omitted").exists() else []
    omitted = sum(1 for r in om if keep(r["item_id"]))
    dp = ROOT / a.data / "design.jsonl"
    design = sum(1 for r in read_jsonl(dp) if keep(r.get("item_id", ""))) if dp.exists() and only is None else None
gen = len(i0)
if design is None and omitted is not None:
    design = gen + omitted
P(""); P("## 문항"); P("")
if design is not None:
    P(f"- 설계 칸 {design}, 생성 {gen}, 생성 생략 {omitted} → **생성 완료율** {pct(gen, design)}")
own0 = Counter(d["own"] for d in i0.values())
judged = gen - own0["pending"]
P(f"- 검수 완료 {judged}개, 미검수 {own0['pending']}개")
P(f"- **최초 통과율** (문항 자체 판정, atom 상태와 무관): {pct(own0['pass'], judged)}")
P(f"- 최초 판정 분포: " + ", ".join(f"{k} {v}" for k, v in own0.most_common()))
fin = Counter(d["decision"] for d in i1.values())
P(f"- **최종 확보** (atom도 통과한 문항): {pct(fin['pass'], design if design is not None else gen)} (분모 = 설계 칸)")
P(f"- 현재 상태: " + ", ".join(f"{k} {v}" for k, v in fin.most_common()))
blk = Counter(d["blocked_by"] for d in i1.values() if d["blocked_by"])
if blk:
    P(f"- atom 때문에 막힌 문항: " + ", ".join(f"{k} {v}" for k, v in blk.most_common()))
check_table(i0)

# ---- 실패·비용 ----
P(""); P("## 호출·비용"); P("")
cost, calls, fails, models = defaultdict(float), Counter(), Counter(), defaultdict(set)
for run in sorted((store.root / "runs").iterdir()):
    stage = run.name.split("_")[-1] if not run.name.split("_")[-1].isdigit() else run.name.split("_")[-2]
    for p in list(run.glob("raw/**/*.json")) + list(run.glob("failed/**/*.json")):
        r = json.loads(p.read_text(encoding="utf-8"))
        j = r.get("judge") or ("reviser" if stage == "revise" else "?")
        u = r.get("usage") or {}
        if isinstance(u, str):
            try: u = ast.literal_eval(u)
            except Exception: u = {}
        key = (stage, j); calls[key] += 1
        if "failed" in p.parts or r.get("error"):
            fails[key] += 1
        try: cost[key] += float((u.get("estimated_cost") or {}).get("amount") or 0)
        except Exception: pass
        if u.get("response_model"): models[key].add(u["response_model"])
P("| 단계 | 모델(설정 이름) | 호출 | 실패 | 비용(unit) | 응답 모델 |"); P("| --- | --- | --- | --- | --- | --- |")
for k in sorted(calls):
    P(f"| {k[0]} | {k[1]} | {calls[k]} | {fails[k]} | {cost[k]:.3f} | {', '.join(sorted(models[k])) or '-'} |")
tot = sum(cost.values())
P(""); P(f"- 검수·수정 비용 합계 {tot:.3f} unit" + (f", 최종 통과 문항당 {tot / fin['pass']:.4f} unit" if fin["pass"] else ""))
P("- 비용은 이 store에 기록된 호출 전체 기준이다 (--only 표본만 따로 나누지 않는다). 생성 비용은 포함하지 않는다.")
txt = "\n".join(L) + "\n"
print(txt)
if a.out:
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(txt, encoding="utf-8")
