"""LLM 검수 실행. 카드·문항은 카드 1장 = 호출 1번(묶음), 답변은 답변 1개 = 호출 1번.
이미 판정이 있는 (단위 해시, 프롬프트 해시, 저지, 반복) 조합은 건너뛰므로 중단 뒤 같은 명령으로 이어 간다."""
import json, random, re, shutil
from concurrent.futures import ThreadPoolExecutor
from string import Template
from .common import ROOT, now, load_prompt, parse_json, book_of
from .aggregate import decide_card, decide_item
from . import judges as J


def _checks_block(defs, batch_defs=None):
    lines = [f"- {n} [{' / '.join(d['values'])}]: {d['desc']}" for n, d in defs.items()]
    if batch_defs:
        lines += ["Whole-card checks (report under \"batch\"):"] + [f"- {n} [{' / '.join(d['values'])}]: {d['desc']}" for n, d in batch_defs.items()]
    return "\n".join(lines)


def _atom_block(a):
    ev = "\n".join(f"    [{e['id']}] {e['text']}" for e in a.get("evidence", []))
    return f"- {a['atom_id']} | {a['scope']}\n  ATOM: {a['statement']}\n  EVIDENCE:\n{ev}"


def _item_block(it, checks):
    kp = f"\n  KEY POINTS: {json.dumps(it['key_points'], ensure_ascii=False)}" if it.get("key_points") else ""
    fl = f"\n  FLAGS: {', '.join(it['flags'])}" if it.get("flags") else ""
    q = it["question"].replace("\n", "\n    ")
    return (f"- {it['item_id']} | FORMAT: {it['format']} | ANSWER KEY: {it['answer'] or '(key points)'}\n  CHECKS: {', '.join(checks)}\n"
            f"  ATOM: {it['atom_statement']}\n  EVIDENCE: {' '.join(it.get('evidence', []))}\n  ITEM:\n    {q}{kp}{fl}")


def _canaries(stage, ctx, n, seed):
    """일부러 망가뜨린 단위. 저지가 이를 잡아내는 비율로 탐지력을 잰다. {원래 id: (망가진 단위, 기대 체크)}"""
    rng = random.Random(f"{seed}:canary:{stage}"); out = {}
    if stage == "card":
        atoms = [(c, a) for c in ctx.cards for a in c["atoms"]]
        for c, a in rng.sample(atoms, min(n, len(atoms))):
            other = rng.choice([x for cc, x in atoms if book_of(cc["card_id"]) != book_of(c["card_id"])])
            out[a["atom_id"]] = ({**a, "evidence": other["evidence"]}, ["GROUNDED"])       # 다른 책의 근거로 바꿔치기
    else:
        pool = [i for i in ctx.items if i["format"] != "OPEN"]
        flip = {"True": "False", "False": "True", "Yes": "No", "No": "Yes", "A": "B", "B": "C", "C": "D", "D": "A"}
        for it in rng.sample(pool, min(n, len(pool))):
            out[it["item_id"]] = ({**it, "answer": flip[it["answer"]]}, ["KEY_CORRECT", "SINGLE_ANSWER"])   # 정답 라벨 뒤집기
    return out


def build_batches(stage, ctx, books=None, only=None, include_blocked=False, n_canary=0):
    gname, g = ctx.reg.group(stage)
    P = load_prompt(g["prompt"]); batches = []
    sel = lambda cid: (not books or book_of(cid) in books)
    if stage == "card":
        can = _canaries(stage, ctx, n_canary, ctx.cfg["policy"]["seed"])
        for c in ctx.cards:
            if not sel(c["card_id"]) or not c["atoms"] or (only and not any(a["atom_id"] in only for a in c["atoms"])):
                continue
            def mk(atoms, canary=None, c=c):
                units = [{"id": a["atom_id"], "hash": a["_hash"], "checks": g["checks"], "cite_pool": [e["id"] for e in a["evidence"]]} for a in atoms]
                user = Template(P["user"]).safe_substitute(concept=c["concept_name"], scope=c.get("assessment_scope", ""),
                                                           units_block="\n".join(_atom_block(a) for a in atoms))
                system = Template(P["system"]).safe_substitute(checks_block=_checks_block(g["checks"], g.get("batch_checks")))
                return {"batch_id": c["card_id"], "group": gname, "unit_type": "atom", "units": units, "system": system, "user": user,
                        "batch_checks": g.get("batch_checks") or {}, "canary": canary}
            sub = [a for a in c["atoms"] if not only or a["atom_id"] in only]   # --only면 지정한 단위만 보낸다 (보정 세트 비용 절약)
            batches.append(mk(sub))
            for a in sub:
                if a["atom_id"] in can:
                    bad, expect = can[a["atom_id"]]
                    batches.append(mk([bad if x["atom_id"] == a["atom_id"] else x for x in c["atoms"]], {"id": a["atom_id"], "expect": expect}))
    elif stage == "item":
        dec = decide_item(ctx); can = _canaries(stage, ctx, n_canary, ctx.cfg["policy"]["seed"])
        concept = {c["card_id"]: c["concept_name"] for c in ctx.cards}
        by_card = {}
        for it in ctx.items:
            if sel(it["card_id"]) and (include_blocked or dec[it["item_id"]]["decision"] != "blocked"):
                by_card.setdefault(it["card_id"], []).append(it)
        for cid, its in by_card.items():
            if only and not any(i["item_id"] in only for i in its):
                continue
            def mk(its, canary=None, cid=cid):
                units = [{"id": i["item_id"], "hash": i["_hash"], "checks": ctx.reg.applicable(g, i)} for i in its]
                user = Template(P["user"]).safe_substitute(concept=concept.get(cid, ""), units_block="\n".join(
                    _item_block(i, list(u["checks"])) for i, u in zip(its, units)))
                system = Template(P["system"]).safe_substitute(checks_block=_checks_block(g["checks"]))
                return {"batch_id": cid, "group": gname, "unit_type": "item", "units": units, "system": system, "user": user,
                        "batch_checks": {}, "canary": canary}
            its = [i for i in its if not only or i["item_id"] in only]
            batches.append(mk(its))
            for i in its:
                if i["item_id"] in can:
                    bad, expect = can[i["item_id"]]
                    batches.append(mk([bad if x["item_id"] == i["item_id"] else x for x in its], {"id": i["item_id"], "expect": expect}))
    else:  # answer: OPEN만 LLM 저지. 어느 모델의 답변인지는 프롬프트에 넣지 않는다.
        dec = decide_item(ctx)
        for a in ctx.answers:
            it = a["_item"]
            if it["format"] != "OPEN" or not sel(it["card_id"]) or (only and a["_id"] not in only):
                continue
            if dec[it["item_id"]]["decision"] != "pass" and not include_blocked:
                continue
            kps = "\n".join(f"{k}. {p}" for k, p in enumerate(it["key_points"], 1))
            user = Template(P["user"]).safe_substitute(question=it["question"], atom=it["atom_statement"], key_points=kps, response=a["response"])
            system = Template(P["system"]).safe_substitute(unit_id=a["_id"])
            batches.append({"batch_id": a["_id"], "group": gname, "unit_type": "answer", "units": [{"id": a["_id"], "hash": a["_hash"], "checks": g["checks"]}],
                            "system": system, "user": user, "batch_checks": {}, "canary": None, "answer": a,
                            "judges": ctx.answer_judges(a["model"])})
    return batches


_norm = lambda s: re.sub(r"\s+", " ", s or "").strip().lower()


def _rows_from(parsed, b, judge, rep, meta):
    """응답 검증 → 원장 행. 빠뜨린 판정·허용되지 않은 값·확인되지 않는 인용은 hold로 내려 사람에게 보낸다."""
    rows, ids = [], {u["id"] for u in b["units"]}
    base = {"ts": now(), **meta, "group": b["group"], "unit_type": b["unit_type"], "judge": judge, "rep": rep}
    for u in b["units"]:
        got = (parsed.get("units") or {}).get(u["id"]) or {}
        is_canary = bool(b["canary"]) and b["canary"]["id"] == u["id"]
        if b["canary"] and not is_canary:
            continue                                              # 카나리아 묶음에서는 카나리아 판정만 기록
        uid = f"CANARY::{u['id']}" if is_canary else u["id"]
        for name, d in u["checks"].items():
            e = got.get(name) if isinstance(got.get(name), dict) else {}
            v, why, cite, extra = e.get("v"), e.get("why", ""), e.get("cite") or [], {}
            if b["unit_type"] == "answer" and name == "KEYPOINTS":
                pts = e.get("points") or []; resp = _norm(b["answer"]["response"]); n_kp = len(b["answer"]["_item"]["key_points"])
                st = {p.get("kp"): p for p in pts if isinstance(p, dict)}
                states = []
                for k in range(1, n_kp + 1):
                    p = st.get(k) or {}; s = p.get("s", "absent")
                    if s in ("present", "contradicted") and (not p.get("quote") or _norm(p["quote"]) not in resp):
                        s = "unverified"                           # 답변에 없는 인용 → 판정 불인정
                    states.append(s)
                v = ("hold" if "unverified" in states or not pts else "incorrect" if "contradicted" in states or "present" not in states
                     else "correct" if all(s == "present" for s in states) else "partial")
                extra = {"points": states}
            elif v is None:
                v, why = "hold", "judge_omitted"
            elif v != "hold" and v not in d["values"]:
                v, why = "hold", f"invalid_value:{v}"
            elif d.get("cite") == "evidence_id" and v == d["values"][0] and not (cite and set(cite) <= set(u.get("cite_pool", []))):
                v, why = "hold", "invalid_citation"
            elif d.get("cite") == "unit_id" and v == "fail" and not (set(cite) & (ids - {u["id"]})):
                v, why = "hold", "invalid_citation"
            row = {**base, "unit_id": uid, "unit_hash": u["hash"], "check": name, "v": v, "why": why}
            if cite: row["cite"] = cite
            if is_canary: extra = {**extra, "expect": b["canary"]["expect"]}
            if extra: row["extra"] = extra
            rows.append(row)
    if not b["canary"]:
        for name, d in b["batch_checks"].items():
            e = (parsed.get("batch") or {}).get(name) or {}
            rows.append({**base, "unit_type": "card", "unit_id": b["batch_id"], "unit_hash": "-", "check": name,
                         "v": e.get("v") if e.get("v") in d["values"] else "hold", "why": e.get("why", "")})
    return rows


def run_stage(stage, store, ctx, judge_ids=None, books=None, only=None, repeat=1, n_canary=0, include_blocked=False,
              limit=None, workers=1, stop_on_error=False, allow_same_family=False):
    cfg = ctx.cfg
    judge_ids = judge_ids or ctx.stage_judges(stage)
    if stage in ("card", "item") and not allow_same_family:
        same = [j for j in judge_ids if cfg["judges"][j]["family"] == cfg.get("generator_family")]
        if same:
            raise SystemExit(f"{same}: 생성 모델과 같은 계열입니다. 다른 계열 저지를 쓰거나 --allow-same-family를 붙이세요.")
    batches = build_batches(stage, ctx, books, only, include_blocked, n_canary)
    gname = ctx.reg.group(stage)[0]; phash = ctx.phash[gname]
    done = {(r["unit_id"], r["unit_hash"], r["judge"], r.get("rep", 0)) for r in ctx.rows if r.get("prompt_hash") == phash}
    tasks = []
    for b in batches:
        for j in (b.get("judges") if stage == "answer" and not judge_ids_given(judge_ids, ctx, stage) else judge_ids):
            for rep in range(repeat):
                pre = "CANARY::" if b["canary"] else ""
                need = [u for u in b["units"] if (not b["canary"] or u["id"] == b["canary"]["id"])
                        and (pre + u["id"], u["hash"], j, rep) not in done]
                if need:
                    tasks.append((b, j, rep))
    if limit:
        tasks = tasks[:limit]
    if not tasks:
        print("할 일 없음 (모두 판정됨)"); return None
    run_id, rdir = store.new_run(stage, {"judges": {j: cfg["judges"][j] for j in {t[1] for t in tasks}}, "group": gname,
                                         "prompt_hash": phash, "repeat": repeat, "n_canary": n_canary, "tasks": len(tasks)})
    shutil.copy(ROOT / "checks.yaml", rdir / "checks.yaml")
    (rdir / "config.json").write_text(json.dumps(cfg, ensure_ascii=False, indent=1), encoding="utf-8")
    shutil.copytree(ROOT / "prompts", rdir / "prompts")
    meta = {"run_id": run_id, "stage": stage, "prompt_hash": phash}

    def work(t):
        b, j, rep = t
        spec = None
        if cfg["judges"][j]["provider"] == "mock":
            if stage == "answer":
                spec = {"kind": "answer", "unit_id": b["batch_id"], "n_kp": len(b["answer"]["_item"]["key_points"]), "response": b["answer"]["response"]}
            else:
                spec = {"kind": "audit", "batch_id": b["batch_id"], "units": {u["id"]: u["checks"] for u in b["units"]},
                        "cite_pool": {u["id"]: u.get("cite_pool", []) for u in b["units"]}, "batch": b["batch_checks"],
                        "canary": {b["canary"]["id"]: b["canary"]["expect"]} if b["canary"] else {}}
        try:
            raw, usage = J.call(j, cfg["judges"][j], b["system"], b["user"], spec)
            return t, raw, usage, None
        except Exception as e:                                      # noqa: BLE001 — 실패는 기록하고 계속
            return t, None, {}, repr(e)

    ok = fail = nrows = 0
    pool = ThreadPoolExecutor(max_workers=workers)
    for (b, j, rep), raw, usage, err in pool.map(work, tasks):
        tag = f"{b['batch_id']}{'.canary-' + b['canary']['id'] if b['canary'] else ''}.r{rep}".replace("::", "__").replace("/", "_")
        parsed = parse_json(raw, "units") if raw else None
        rec = {"batch_id": b["batch_id"], "judge": j, "rep": rep, "canary": b["canary"], "system": b["system"], "user": b["user"],
               "raw": raw, "usage": usage, "error": err, "ts": now()}
        sub = "raw" if parsed else "failed"                         # 실패한 응답도 버리지 않고 저장
        p = rdir / sub / j / f"{tag}.json"; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        if not parsed:
            fail += 1; print(f"  실패 {b['batch_id']} [{j}]: {err or 'JSON 파싱 실패'} → {p}")
            if stop_on_error:
                break
            continue
        rows = [r for r in _rows_from(parsed, b, j, rep, meta) if (r["unit_id"], r["unit_hash"], j, rep) not in done]
        store.add_verdicts(rows); ok += 1; nrows += len(rows)
    pool.shutdown(cancel_futures=True)
    print(f"run {run_id}: 호출 성공 {ok}, 실패 {fail}, 판정 {nrows}행 적재")
    if fail:
        raise SystemExit(1)                                         # 실패가 있으면 종료 코드로 알린다. 같은 명령을 다시 실행하면 실패분만 이어 간다
    return run_id


def judge_ids_given(judge_ids, ctx, stage):
    """--judges로 직접 지정했는지 (답변 단계에서 계열 자동 선택을 건너뛸지)."""
    return judge_ids != ctx.stage_judges(stage)
