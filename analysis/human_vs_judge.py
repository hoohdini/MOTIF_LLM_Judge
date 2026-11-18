"""사람 판정 vs LLM 저지 비교표 (생성 프롬프트 튜닝에서 어떤 체크를 지표로 믿을지 정하기 위한 것).

사용: python analysis/human_vs_judge.py [store 경로]
출력: analysis/results/human_vs_judge.md, human_vs_judge.json

사람 판정 출처
- calib: 보정 세트 1인 라벨 (atom 120, 문항 120). 불통과면 메모에 걸린 체크 이름을 적었다.
- adjudication: 사람·LLM이 갈린 42건 재판정 (정답 기준으로 쓴다).
- review: 11/18 통과 문항 사람 검토 (표본 81 = 문항 단위, 보류 7 = 체크 단위).
LLM 판정은 현재 저지 프롬프트(v2) 해시의 판정만 쓴다. 단위 판정은 체크 중 최악값, hold는 비교에서 뺀다.
"""
import csv, json, re, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kcaudit.stats import agreement  # noqa: E402
from kcaudit.aggregate import Registry  # noqa: E402

STORE = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "store"
reg = Registry("checks.yaml", ROOT)
GROUP = {"card": "atom_audit", "item": "item_audit"}
PH = {st: reg.prompt_hash(g) for st, g in GROUP.items()}
CHECKS = {st: [c for c in reg.groups[g]["checks"] if c not in ("NO_OVERLAP", "CENTRALITY", "NO_INTRA_CARD_OVERLAP", "CONCEPT_SCOPE")]
          for st, g in GROUP.items()}
J = {"judge_a": "GPT", "judge_b": "Gemini"}
ORDER = {"fail": 3, "revise": 2, "hold": 1, "pass": 0}
NP = ("fail", "revise")
b = lambda v: "pass" if v == "pass" else "nonpass"

rows = [json.loads(l) for l in open(STORE / "ledger/verdicts.jsonl", encoding="utf-8")]
llm = defaultdict(lambda: defaultdict(dict))        # (stage, unit) -> check -> judge -> (v, why)
human = defaultdict(list)                            # (stage, unit) -> [row]
for r in rows:
    st = r["stage"]
    if r["judge"] in J and r.get("prompt_hash") == PH.get(st):
        llm[(st, r["unit_id"])][r["check"]][r["judge"]] = (r["v"], r.get("why", ""))
    elif r["judge"].startswith("human:"):
        human[(st, r["unit_id"])].append(r)


def judge_unit(st, u, j):
    vs = [cs[j][0] for c, cs in llm[(st, u)].items() if c in CHECKS[st] and j in cs]
    if not vs:
        return None
    return max(vs, key=lambda v: ORDER.get(v, 1))


def combined(st, u):
    """decision 합산: 두 저지의 단위 판정이 같으면 그것, 다르면 hold"""
    a, g = judge_unit(st, u, "judge_a"), judge_unit(st, u, "judge_b")
    if a is None or g is None:
        return None
    return a if b(a) == b(g) else "hold"


def cited(note, st):
    return {c for c in CHECKS[st] if re.search(rf"\b{c}\b", note or "")}


out = ["# 사람 판정 vs LLM 저지 비교표", "",
       "LLM = 현재 저지 프롬프트(v2) 판정. 이진 비교(pass 대 비pass), hold 제외. "
       "**LLM 엄격** = LLM만 비pass, **사람 엄격** = 사람만 비pass.", ""]
res = {}

# ---------- A. 단위 수준 ----------
out += ["## A. 단위(atom·문항) 수준 일치", "",
        "| 단계 | 사람 판정 출처 | n | 사람 비pass | LLM 비pass | 일치율 | κ | LLM 엄격 | 사람 엄격 |",
        "|---|---|---|---|---|---|---|---|---|"]
for st in ("card", "item"):
    for src in ("calib", "adjudication", "sample"):
        pairs = []
        for (s, u), hs in human.items():
            if s != st:
                continue
            h = [r for r in hs if (r.get("extra") or {}).get("source") == src and r["check"] == "_UNIT"]
            if not h or h[-1]["v"] == "hold":
                continue
            c = combined(st, u)
            if c in (None, "hold"):
                continue
            pairs.append((b(h[-1]["v"]), b(c)))
        if not pairs:
            continue
        a = agreement(pairs)
        hs_ = sum(h == "nonpass" for h, _ in pairs); ls_ = sum(l == "nonpass" for _, l in pairs)
        lo = sum(h == "pass" and l == "nonpass" for h, l in pairs); ho = sum(h == "nonpass" and l == "pass" for h, l in pairs)
        name = {"calib": "보정 라벨(1인)", "adjudication": "재판정 결과(정답 기준)", "sample": "11/18 문항 검토 표본"}[src]
        out.append(f"| {st} | {name} | {len(pairs)} | {hs_} | {ls_} | {a['agree']} | {a['kappa']} | {lo} | {ho} |")
        res[f"unit_{st}_{src}"] = {"n": len(pairs), "agree": a["agree"], "kappa": a["kappa"], "llm_only": lo, "human_only": ho}
out += ["", "재판정 결과 행 = 현재 저지(v2)가 재판정 정답과 얼마나 맞는지 (원래 사람 라벨과 LLM이 갈린 단위만 모은 것이라 κ는 의미 없음).", ""]

# ---------- B. 체크 수준 ----------
adj = {r["unit_id"]: r for r in csv.DictReader(open(ROOT / "analysis/results/adjudication_p1.csv", encoding="utf-8-sig"))}
out += ["## B. 체크별 비교 (보정 세트 + 11/18 문항 검토)", "",
        "- **사람 지적**: 사람이 비pass를 주며 메모에 그 체크를 적은 단위 (보정 라벨), 또는 보류 검토에서 그 체크를 fail로 준 단위",
        "- **LLM 지적**: GPT·Gemini 중 하나라도 그 체크에 fail/revise",
        "- **LLM 지적의 확인 결과**: LLM이 지적한 단위를 ✔ 사람도 비pass / ✔재 재판정에서 LLM이 맞음 / ✘ 재판정에서 사람이 맞음 / ? 사람은 pass, 재판정 안 함 으로 나눔",
        "- **LLM 재현율**: 사람이 그 체크로 지적한 단위 중 LLM도 그 체크를 지적한 비율 (LLM이 놓치는 정도)",
        "- **저지 간 일치**: 현재 프롬프트로 판정된 모든 단위에서 GPT·Gemini가 그 체크에 같은 판정(pass 대 비pass)을 낸 비율",
        "", "| 단계 | 체크 | 사람 지적 | LLM 지적 | ✔ | ✔재 | ✘ | ? | LLM 재현율 | 저지 간 일치 (n) |",
        "|---|---|---|---|---|---|---|---|---|---|"]
for st in ("card", "item"):
    labeled = {}
    for (s, u), hs in human.items():
        if s != st:
            continue
        src_rows = [r for r in hs if (r.get("extra") or {}).get("source") in ("calib", "sample", "queue")]
        if not src_rows:
            continue
        unit_v, flags = None, set()
        for r in src_rows:
            if r["check"] == "_UNIT":
                unit_v = r["v"]; flags |= cited(r.get("why"), st) if r["v"] != "pass" else set()
            elif r["v"] != "pass":
                flags.add(r["check"]); unit_v = "fail"
            elif unit_v is None:
                unit_v = "pass"
        if unit_v in (None, "hold"):
            continue
        labeled[u] = (b(unit_v), flags)
    for c in CHECKS[st]:
        hf = {u for u, (v, f) in labeled.items() if c in f}
        lf = {u for u in labeled if any(v in NP for v, _ in llm[(st, u)].get(c, {}).values())}
        prec = sum(labeled[u][0] == "nonpass" for u in lf)
        aw = [u for u in lf if u in adj and labeled[u][0] == "pass"]
        win = sum(adj[u]["who_was_right"] == "LLM" for u in aw)
        unk = sum(labeled[u][0] == "pass" and u not in adj for u in lf)
        jj = [(b(cs["judge_a"][0]), b(cs["judge_b"][0])) for (s, u), ch in llm.items() if s == st
              for cc, cs in ch.items() if cc == c and "judge_a" in cs and "judge_b" in cs
              and "hold" not in (cs["judge_a"][0], cs["judge_b"][0])]
        jag = round(sum(x == y for x, y in jj) / len(jj), 2) if jj else None
        pr = f"{prec}/{len(lf)} ({prec / len(lf):.0%})" if lf else "–"
        rc = f"{len(hf & lf)}/{len(hf)} ({len(hf & lf) / len(hf):.0%})" if hf else "–"
        out.append(f"| {st} | {c} | {len(hf)} | {len(lf)} | {prec} | {win} | {len(aw) - win} | {unk} | {rc} | {jag} ({len(jj)}) |")
        res[f"check_{st}_{c}"] = {"human": len(hf), "llm": len(lf), "both": len(hf & lf), "llm_confirmed_human": prec, "llm_adj_right": win, "llm_adj_wrong": len(aw) - win, "llm_unresolved": unk,
                                  "llm_recall": [len(hf & lf), len(hf)], "judge_agree": jag}
    res[f"labeled_{st}"] = len(labeled)
out.append("")

# ---------- C. 채점자 편차 ----------
out += ["## C. 보정 라벨 채점자별 일치 (LLM 합산 판정 대비)", "", "| 단계 | 채점자 | n | 사람 비pass | κ | LLM 엄격 | 사람 엄격 |", "|---|---|---|---|---|---|---|"]
for st in ("card", "item"):
    by = defaultdict(list)
    for (s, u), hs in human.items():
        h = [r for r in hs if s == st and (r.get("extra") or {}).get("source") == "calib" and r["check"] == "_UNIT"]
        if not h or h[-1]["v"] == "hold":
            continue
        c = combined(st, u)
        if c in (None, "hold"):
            continue
        by[h[-1]["judge"].split(":", 1)[1]].append((b(h[-1]["v"]), b(c)))
    for who, pairs in sorted(by.items()):
        a = agreement(pairs)
        out.append(f"| {st} | {who} | {len(pairs)} | {sum(h == 'nonpass' for h, _ in pairs)} | {a['kappa']} | "
                   f"{sum(h == 'pass' and l == 'nonpass' for h, l in pairs)} | {sum(h == 'nonpass' and l == 'pass' for h, l in pairs)} |")
out.append("")

(ROOT / "analysis/results/human_vs_judge.md").write_text("\n".join(out) + "\n", encoding="utf-8")
(ROOT / "analysis/results/human_vs_judge.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
print("\n".join(out))
