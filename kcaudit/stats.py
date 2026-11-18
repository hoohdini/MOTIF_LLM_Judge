"""저지를 검증하는 통계: 저지 간 일치도, 사람 기준 대비 정확도, 카나리아 탐지율, 반복 안정성, 표본 오류율 상한."""
from collections import Counter, defaultdict
from math import comb
from .aggregate import DECIDE, decide_card, decide_item


def agreement(pairs):
    """pairs: [(a, b)] 범주 판정. Cohen's kappa와 Gwet's AC1 (한쪽 범주가 압도적일 때 kappa가 불안정해서 같이 본다)."""
    n = len(pairs)
    if n == 0:
        return {"n": 0}
    cats = sorted({x for p in pairs for x in p})
    pa = sum(a == b for a, b in pairs) / n
    ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    pe_k = sum(ca[c] / n * cb[c] / n for c in cats)
    kappa = (pa - pe_k) / (1 - pe_k) if pe_k < 1 else float("nan")
    q = max(len(cats), 2)
    pi = {c: (ca[c] + cb[c]) / (2 * n) for c in cats}
    pe_g = sum(p * (1 - p) for p in pi.values()) / (q - 1)
    ac1 = (pa - pe_g) / (1 - pe_g) if pe_g < 1 else float("nan")
    return {"n": n, "agree": round(pa, 3), "kappa": round(kappa, 3), "ac1": round(ac1, 3)}


def cp_upper(k, n, conf=0.95):
    """n개 중 k개 오류일 때 오류율의 단측 Clopper–Pearson 상한."""
    if n == 0:
        return None
    lo, hi = k / n, 1.0
    cdf = lambda p: sum(comb(n, i) * p**i * (1 - p) ** (n - i) for i in range(k + 1))
    for _ in range(60):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if cdf(mid) > 1 - conf else (lo, mid)
    return round(hi, 4)


def _b(v):
    return "pass" if v in ("pass", "correct") else "nonpass"


def report(ctx, stage):
    gname, g = ctx.reg.group(stage); phash = ctx.phash[gname]; out = {"stage": stage}
    current = {(u["unit_id"], u["unit_hash"]) for u in DECIDE[stage](ctx).values()}
    votes = defaultdict(lambda: defaultdict(dict))                   # judge → (uid, check) → rep → v
    canary = defaultdict(lambda: defaultdict(lambda: [False, False]))
    for r in ctx.rows:
        if r["stage"] != stage or r["judge"] == "code" or r["judge"].startswith("human:") or r["check"] == "_UNIT":
            continue
        if r["unit_id"].startswith("CANARY::"):
            if r.get("prompt_hash") == phash:
                c = canary[r["judge"]][(r["unit_id"], r["rep"])]; c[0] = True
                c[1] = c[1] or (r["check"] in r.get("extra", {}).get("expect", []) and r["v"] != "pass")
            continue
        if r["judge"].startswith("preaudit:") or (r.get("prompt_hash") == phash and (r["unit_id"], r["unit_hash"]) in current):
            votes[r["judge"]][(r["unit_id"], r["check"])][r.get("rep", 0)] = r["v"]
    first = {j: {k: v[min(v)] for k, v in d.items()} for j, d in votes.items()}
    # 1) 저지 쌍별·체크별 일치도 (pass 대 non-pass)
    js = sorted(first); out["pairwise"] = {}
    for i, a in enumerate(js):
        for b in js[i + 1:]:
            per = defaultdict(list)
            for k in first[a].keys() & first[b].keys():
                per[k[1]].append((_b(first[a][k]), _b(first[b][k])))
            allp = [p for v in per.values() for p in v]
            out["pairwise"][f"{a} vs {b}"] = {"ALL": agreement(allp), **{c: agreement(v) for c, v in sorted(per.items())}}
    # 2) 반복 안정성: 같은 프롬프트를 여러 번 돌렸을 때 판정이 뒤집힌 비율
    out["flip_rate"] = {}
    for j, d in votes.items():
        multi = [v for v in d.values() if len(v) > 1]
        if multi:
            out["flip_rate"][j] = {"n": len(multi), "flipped": round(sum(len(set(v.values())) > 1 for v in multi) / len(multi), 3)}
    # 3) 카나리아 탐지율
    out["canary"] = {j: {"n": len(d), "detected": round(sum(c[1] for c in d.values()) / len(d), 3)} for j, d in canary.items() if d}
    # 4) 사람 기준 대비 (단위 판정). 저지 단독 판정과 합산 판정을 각각 비교
    if stage in ("card", "item"):
        fn = decide_card if stage == "card" else decide_item
        by_rev = defaultdict(dict)                                   # 검수자 → 단위 → (판정, 출처)
        for r in ctx.rows:
            if r["stage"] == stage and r["check"] == "_UNIT" and r["judge"].startswith("human:") and r["v"] != "hold":
                by_rev[r["judge"]][(r["unit_id"], r["unit_hash"])] = (r["v"], r.get("extra", {}).get("source"))
        revs = sorted(by_rev); out["human_pairwise"] = {}
        for i, a in enumerate(revs):                                 # 사람끼리의 일치도. 이것이 저지에게 기대할 수 있는 상한이다
            for b in revs[i + 1:]:
                both = by_rev[a].keys() & by_rev[b].keys()
                if both:
                    out["human_pairwise"][f"{a} vs {b}"] = agreement([(_b(by_rev[a][k][0]), _b(by_rev[b][k][0])) for k in both])
        human, split = {}, 0                                         # 기준표: 검수자들이 일치한 단위만 쓴다
        for k in set().union(*[d.keys() for d in by_rev.values()]) if by_rev else []:
            vs = [d[k] for d in by_rev.values() if k in d]
            if len({_b(v) for v, _ in vs}) == 1:
                human[k] = vs[-1]
            else:
                split += 1
        if split:
            out["human_split"] = split                               # 사람끼리 갈린 단위 수 (기준표에서 제외, 합의 후 다시 입력)
        llm_only = fn(ctx, use_human=False); out["vs_human"] = {}
        cands = {"COMBINED": llm_only, **{j: fn(ctx, judges=[j], use_human=False) for j in ctx.stage_judges(stage)}}
        for name, dec in cands.items():
            # 사람이나 LLM 어느 한쪽이라도 hold면 비교에서 뺀다 (판정 불가를 '불통과'로 세지 않도록)
            pairs = [(_b(hv), _b(dec[u]["own"])) for (u, hh), (hv, _) in human.items()
                     if u in dec and dec[u]["unit_hash"] == hh and hv != "hold" and dec[u]["own"] not in ("pending", "hold")]
            if pairs:
                out.setdefault("vs_human_excluded_hold", {})[name] = sum(1 for (u, hh), (hv, _) in human.items() if u in dec and dec[u]["unit_hash"] == hh) - len(pairs)
                bad = [p for p in pairs if p[0] == "nonpass"]; good = [p for p in pairs if p[0] == "pass"]
                out["vs_human"][name] = {**agreement(pairs),
                                         "fail_recall": round(sum(p[1] == "nonpass" for p in bad) / len(bad), 3) if bad else None,
                                         "false_alarm": round(sum(p[1] == "nonpass" for p in good) / len(good), 3) if good else None}
        # 5) 만장일치 pass의 무작위 표본에서 사람이 찾은 오류 → 승인본 오류율 상한
        samp = [(hv, llm_only[u]["own"]) for (u, hh), (hv, src) in human.items() if src == "sample" and u in llm_only and llm_only[u]["unit_hash"] == hh]
        passed = [hv for hv, lv in samp if lv == "pass"]
        if passed:
            k = sum(hv != "pass" for hv in passed)
            out["approved_error"] = {"sampled": len(passed), "errors": k, "upper95": cp_upper(k, len(passed))}
    return out
