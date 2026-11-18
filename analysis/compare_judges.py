"""보정 세트(사람 라벨 240개) 기준으로 LLM 저지들을 비교한다.

사용: python analysis/compare_judges.py
입력: store/ledger/verdicts.jsonl (GPT·Gemini 판정과 사람 판정),
      analysis/data/claude_pilot_calib.json (11/17 Claude 예비 판정, 사람 라벨을 보지 않은 에이전트가 판정)
출력: analysis/results/calib_agreement.md, calib_agreement.json, adjudication_queue.csv

비교 규칙
- 사람이 판정하지 않은 체크(NO_OVERLAP, CENTRALITY, NO_INTRA_CARD_OVERLAP)는 LLM 단위 판정에서 뺀다.
- 단위 판정: 체크 중 fail > hold > revise > pass 순으로 가장 무거운 값.
- 사람·LLM 어느 쪽이든 hold면 그 단위는 해당 비교에서 제외한다.
- 이진 비교: pass 대 비pass(revise·fail).
"""
import csv, json, random, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kcaudit.stats import agreement  # noqa: E402

OUT = ROOT / "analysis" / "results"; OUT.mkdir(parents=True, exist_ok=True)
SKIP = {"NO_OVERLAP", "CENTRALITY", "NO_INTRA_CARD_OVERLAP"}
JUDGES = {"judge_a": "GPT (gpt-6.1-sol)", "judge_b": "Gemini (gemini-4-argon)", "claude": "Claude (예비, 11/17)"}
ORDER = {"fail": 3, "hold": 2, "revise": 1, "pass": 0}

rows = [json.loads(l) for l in open(ROOT / "store/ledger/verdicts.jsonl", encoding="utf-8")]
human = {}
for r in rows:
    if r["judge"].startswith("human:") and r["check"] == "_UNIT":
        human[r["unit_id"]] = {"v": r["v"], "who": r["judge"][6:], "note": r.get("why", ""), "stage": r["stage"]}
content = {}
for st in ("card", "item"):
    for r in csv.DictReader(open(ROOT / f"calib/calib_{st}.csv", encoding="utf-8-sig")):
        content[r["unit_id"]] = r["content"]

per = defaultdict(lambda: defaultdict(dict))    # judge -> unit -> check -> v
why = defaultdict(lambda: defaultdict(dict))
latest = {}
for r in rows:
    if r["judge"] in ("judge_a", "judge_b") and r["unit_id"] in human and r["check"] not in SKIP and not r["unit_id"].startswith("CANARY::"):
        k = (r["judge"], r["unit_id"], r["check"])
        if k not in latest or r["ts"] >= latest[k]:
            latest[k] = r["ts"]; per[r["judge"]][r["unit_id"]][r["check"]] = r["v"]
            if r.get("why"): why[r["judge"]][r["unit_id"]][r["check"]] = r["why"]
cl = json.load(open(ROOT / "analysis/data/claude_pilot_calib.json", encoding="utf-8"))
for u, d in cl.items():
    per["claude"][u] = {k: v for k, v in d["per"].items() if k not in SKIP}
    why["claude"][u] = d.get("why", {})

dec = {j: {u: max(c.values(), key=lambda v: ORDER.get(v, 2)) for u, c in us.items() if c} for j, us in per.items()}
b = lambda v: "pass" if v == "pass" else "nonpass"
fmt = lambda u: u.rsplit("-", 1)[1] if human[u]["stage"] == "item" else "atom"


def boot(pairs, key="kappa", n=2000):
    rng = random.Random(7); xs = []
    for _ in range(n):
        a = agreement([pairs[rng.randrange(len(pairs))] for _ in pairs])[key]
        if a == a: xs.append(a)
    xs.sort()
    return [round(xs[int(.025 * len(xs))], 3), round(xs[int(.975 * len(xs)) - 1], 3)] if xs else None


def vs_human(j, units):
    pairs = [(b(human[u]["v"]), b(dec[j][u])) for u in units if u in dec[j] and human[u]["v"] != "hold" and dec[j][u] != "hold"]
    a = agreement(pairs)
    if not pairs: return a
    bad = [p for p in pairs if p[0] == "nonpass"]; good = [p for p in pairs if p[0] == "pass"]
    a.update(kappa_ci95=boot(pairs), llm_nonpass_rate=round(sum(p[1] == "nonpass" for p in pairs) / len(pairs), 3),
             human_nonpass_rate=round(len(bad) / len(pairs), 3),
             catches_human_flag=round(sum(p[1] == "nonpass" for p in bad) / len(bad), 3) if bad else None,
             flags_human_pass=round(sum(p[1] == "nonpass" for p in good) / len(good), 3) if good else None)
    return a


R = {"note": __doc__.strip().splitlines()[0], "stages": {}}
for st in ("card", "item"):
    units = [u for u in human if human[u]["stage"] == st]
    S = {"n_units": len(units), "human_dist": dict(Counter(human[u]["v"] for u in units))}
    S["llm_dist"] = {JUDGES[j]: dict(Counter(dec[j].get(u, "missing") for u in units)) for j in JUDGES}
    S["vs_human"] = {JUDGES[j]: vs_human(j, units) for j in JUDGES}
    S["between_llms"] = {}
    js = list(JUDGES)
    for i, a in enumerate(js):
        for c in js[i + 1:]:
            pr = [(b(dec[a][u]), b(dec[c][u])) for u in units if u in dec[a] and u in dec[c] and "hold" not in (dec[a][u], dec[c][u])]
            S["between_llms"][f"{JUDGES[a]} vs {JUDGES[c]}"] = agreement(pr)
    S["by_reviewer"] = {rv: {JUDGES[j]: agreement([(b(human[u]["v"]), b(dec[j][u])) for u in units if human[u]["who"] == rv and u in dec[j] and "hold" not in (human[u]["v"], dec[j][u])]) for j in JUDGES}
                        for rv in sorted({human[u]["who"] for u in units})}
    if st == "item":
        S["by_format"] = {f: {JUDGES[j]: agreement([(b(human[u]["v"]), b(dec[j][u])) for u in units if fmt(u) == f and u in dec[j] and "hold" not in (human[u]["v"], dec[j][u])]) for j in JUDGES} for f in ("OPEN", "TF", "MCQ", "YN")}
    hck = lambda u: set(human[u]["note"].split("|")[0].split())
    checks = sorted({c for j in JUDGES for u in units for c in per[j].get(u, {})})
    S["per_check"] = {}
    for c in checks:
        row = {}
        for j in JUDGES:
            pr = [("flag" if c in hck(u) else "ok", "flag" if per[j][u].get(c) not in ("pass", "hold") else "ok") for u in units if c in per[j].get(u, {}) and human[u]["v"] != "hold" and per[j][u][c] != "hold"]
            cnt = Counter(pr)
            row[JUDGES[j]] = {"human_flag": cnt[("flag", "flag")] + cnt[("flag", "ok")], "llm_flag": cnt[("flag", "flag")] + cnt[("ok", "flag")], "both": cnt[("flag", "flag")], "n": len(pr)}
        S["per_check"][c] = row
    # 세 모델이 모두 같은 방향인데 사람과 다른 단위 = 재판정 우선순위 1
    agree3 = [u for u in units if all(u in dec[j] and dec[j][u] != "hold" for j in JUDGES) and human[u]["v"] != "hold"
              and len({b(dec[j][u]) for j in JUDGES}) == 1 and b(dec["judge_a"][u]) != b(human[u]["v"])]
    S["all_three_vs_human"] = {"n": len(agree3), "direction": dict(Counter(f"사람 {b(human[u]['v'])} / LLM {b(dec['judge_a'][u])}" for u in agree3))}
    R["stages"][st] = S

# 재판정 큐
q = []
for u, h in human.items():
    ds = {j: dec[j].get(u) for j in JUDGES}
    valid = [d for d in ds.values() if d and d != "hold"]
    if h["v"] == "hold" or not valid: continue
    llm_non = sum(b(d) == "nonpass" for d in valid)
    if all(b(d) == b(h["v"]) for d in valid): continue
    unanimous = len({b(d) for d in valid}) == 1 and len(valid) == 3
    q.append({"priority": 1 if unanimous else 2, "stage": h["stage"], "unit_id": u, "reviewer": h["who"], "human_v": h["v"], "human_note": h["note"],
              **{f"{k}_v": ds[k] or "" for k in JUDGES},
              **{f"{k}_flags": " ".join(f"{c}={v}" for c, v in per[k].get(u, {}).items() if v != "pass") for k in JUDGES},
              "gpt_why": " | ".join(f"{c}: {w}" for c, w in why["judge_a"].get(u, {}).items()),
              "gemini_why": " | ".join(f"{c}: {w}" for c, w in why["judge_b"].get(u, {}).items()),
              "content": content.get(u, ""), "adjudicated_v": "", "who_was_right": "", "adjudication_note": ""})
q.sort(key=lambda r: (r["priority"], r["stage"], r["unit_id"]))
with open(OUT / "adjudication_queue.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.DictWriter(f, fieldnames=list(q[0].keys())); w.writeheader(); w.writerows(q)
R["adjudication_queue"] = {"n": len(q), "priority1_all_three_llms_agree": sum(r["priority"] == 1 for r in q)}
json.dump(R, open(OUT / "calib_agreement.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)


def f3(x): return "–" if x is None or x != x else f"{x:.2f}"


md = ["# 보정 세트 LLM 저지 비교", "", f"생성: `python analysis/compare_judges.py`. 사람 라벨 {len(human)}개 기준.", ""]
for st, name in (("card", "atom"), ("item", "문항")):
    S = R["stages"][st]
    md += [f"## {name} ({S['n_units']}개)", "", f"사람 판정 분포: {S['human_dist']}", "",
           "| 저지 | n | 일치율 | κ (95% CI) | AC1 | LLM 비pass율 | 사람 지적을 잡은 비율 | 사람 pass를 거른 비율 |", "| --- | --- | --- | --- | --- | --- | --- | --- |"]
    for j, a in S["vs_human"].items():
        md.append(f"| {j} | {a['n']} | {f3(a.get('agree'))} | {f3(a.get('kappa'))} {a.get('kappa_ci95')} | {f3(a.get('ac1'))} | {f3(a.get('llm_nonpass_rate'))} | {f3(a.get('catches_human_flag'))} | {f3(a.get('flags_human_pass'))} |")
    md += ["", "LLM끼리:", ""] + [f"- {k}: κ {f3(v.get('kappa'))}, 일치 {f3(v.get('agree'))} (n={v.get('n')})" for k, v in S["between_llms"].items()]
    md += ["", "검수자별 κ (사람 vs LLM):", "", "| 검수자 | " + " | ".join(JUDGES.values()) + " |", "| --- |" + " --- |" * len(JUDGES)]
    for rv, d in S["by_reviewer"].items():
        md.append(f"| {rv} | " + " | ".join(f"{f3(d[j].get('kappa'))} (n={d[j].get('n')})" for j in JUDGES.values()) + " |")
    if "by_format" in S:
        md += ["", "형식별 κ:", "", "| 형식 | " + " | ".join(JUDGES.values()) + " |", "| --- |" + " --- |" * len(JUDGES)]
        for fm, d in S["by_format"].items():
            md.append(f"| {fm} | " + " | ".join(f"{f3(d[j].get('kappa'))} (n={d[j].get('n')})" for j in JUDGES.values()) + " |")
    md += ["", "체크별 지적 수 (사람 / LLM / 둘 다):", "", "| 체크 | " + " | ".join(JUDGES.values()) + " |", "| --- |" + " --- |" * len(JUDGES)]
    for c, d in S["per_check"].items():
        md.append(f"| {c} | " + " | ".join(f"{d[j]['human_flag']} / {d[j]['llm_flag']} / {d[j]['both']}" for j in JUDGES.values()) + " |")
    md += ["", f"세 모델이 같은 판정인데 사람과 다른 단위: {S['all_three_vs_human']['n']}개 {S['all_three_vs_human']['direction']}", ""]
md += [f"재판정 큐: `analysis/results/adjudication_queue.csv` {R['adjudication_queue']['n']}개 (우선순위 1 = 세 모델 일치: {R['adjudication_queue']['priority1_all_three_llms_agree']}개)", ""]
open(OUT / "calib_agreement.md", "w", encoding="utf-8").write("\n".join(md))
print("\n".join(md))
