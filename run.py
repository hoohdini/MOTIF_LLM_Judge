#!/usr/bin/env python3
"""Knowledge Card 검수 파이프라인 CLI. 사용법은 README.md."""
import argparse, csv, json, sqlite3, sys
from collections import Counter
from pathlib import Path
from kcaudit.common import ROOT, load_yaml, load_env, now
from kcaudit.store import Store
from kcaudit.aggregate import Ctx, Registry, DECIDE
from kcaudit import prechecks, runner, revise, human, stats, release

ap = argparse.ArgumentParser(description=__doc__)
ap.add_argument("--config", default="config.yaml", help="설정 파일 (모의 실행은 config.mock.yaml)")
sub = ap.add_subparsers(dest="cmd", required=True)
p = sub.add_parser("ingest", help="원본을 불변 스냅샷으로 적재"); p.add_argument("kind", choices=["cards", "items", "answers", "preaudit"]); p.add_argument("paths", nargs="+"); p.add_argument("--label", default="")
p = sub.add_parser("precheck", help="코드 사전검사"); p.add_argument("--stage", choices=["card", "item", "answer"], required=True)
p = sub.add_parser("run", help="LLM 저지 실행 (이어 하기 가능)")
p.add_argument("--stage", choices=["card", "item", "answer"], required=True); p.add_argument("--judges"); p.add_argument("--books")
p.add_argument("--only", help="단위 id 목록 파일 (보정 세트 등)"); p.add_argument("--repeat", type=int, default=1); p.add_argument("--canaries", type=int, default=0)
p.add_argument("--include-blocked", action="store_true", help="카드 검수가 끝나지 않은 atom의 문항도 검수"); p.add_argument("--limit", type=int)
p.add_argument("--workers", type=int, default=1); p.add_argument("--stop-on-error", action="store_true"); p.add_argument("--allow-same-family", action="store_true")
p = sub.add_parser("decide", help="현재 판정 요약"); p.add_argument("--stage", choices=["card", "item", "answer"], required=True); p.add_argument("--show", help="특정 단위 상세")
p = sub.add_parser("revise", help="revise 판정 atom 자동 분리·수정"); p.add_argument("--judge", default="reviser"); p.add_argument("--limit", type=int); p.add_argument("--workers", type=int, default=1)
p = sub.add_parser("human", help="사람 검수 큐"); p.add_argument("action", choices=["export", "import"]); p.add_argument("--stage", choices=["card", "item", "answer"])
p.add_argument("--file"); p.add_argument("--reviewer"); p.add_argument("--rate", type=float); p.add_argument("--show-llm", action="store_true")
p = sub.add_parser("calib", help="저지 선정용 보정 세트 추출"); p.add_argument("--stage", choices=["card", "item"], required=True); p.add_argument("--n", type=int, default=120)
p = sub.add_parser("stats", help="저지 검증 통계"); p.add_argument("--stage", choices=["card", "item", "answer"], required=True); p.add_argument("--json", action="store_true")
p = sub.add_parser("release", help="승인본 만들기·롤백"); p.add_argument("action", choices=["build", "list", "rollback", "verify"]); p.add_argument("tag", nargs="?"); p.add_argument("--note", default="")
sub.add_parser("index", help="원장을 SQLite로 색인 (조회용, 언제든 다시 만들 수 있음)")
args = ap.parse_args()

load_env()
cfg = load_yaml(ROOT / args.config); reg = Registry(); store = Store(cfg["store"])


def ctx():
    """현재 데이터 + 원장. 새로 들어온 단위(수정본 포함)는 코드 사전검사를 먼저 자동으로 채운다."""
    c = Ctx(store, cfg, reg)
    if prechecks.write_new(store, prechecks.atoms(c.cards) + prechecks.items(c.items) + prechecks.answers(c.answers)):
        c = Ctx(store, cfg, reg)
    return c


if args.cmd == "ingest":
    if args.kind == "preaudit":      # 연욱의 Opus 사전 점검 CSV → 저지 한 명의 판정으로 적재 (비교·우선순위용, 승인에는 쓰지 않음)
        c = ctx(); hashes = {a["atom_id"]: a["_hash"] for cd in c.cards for a in cd["atoms"]}; rows = []
        m = {"grounded": ("GROUNDED", {"supported": "pass", "partly_supported": "revise", "not_supported": "fail"}),
             "single_claim": ("SINGLE_CLAIM", {"True": "pass", "False": "revise"}), "scope_label_ok": ("SCOPE_LABEL", {"True": "pass", "False": "revise"}),
             "l1_ok": ("L1_ONLY", {"True": "pass", "False": "fail"}), "centrality": ("CENTRALITY", {"central": "pass", "useful": "pass", "peripheral": "fail"})}
        with open(args.paths[0], encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                if r["atom_id"] not in hashes: continue
                base = {"ts": now(), "run_id": "preaudit", "stage": "card", "group": "preaudit", "unit_type": "atom", "unit_id": r["atom_id"],
                        "unit_hash": hashes[r["atom_id"]], "judge": f"preaudit:{args.label or 'opus'}", "rep": 0, "prompt_hash": "preaudit", "why": r["issue"]}
                rows += [{**base, "check": ck, "v": mp[r[col]]} for col, (ck, mp) in m.items()]
                rows.append({**base, "check": "NO_OVERLAP", "v": "fail" if r["overlaps_with"].strip() else "pass", "cite": r["overlaps_with"].split()})
        store.add_verdicts(rows); print(f"사전 점검 {len(rows)}행 적재")
    else:
        sha, n = store.ingest(args.kind, args.paths, args.label); print(f"{args.kind}: {n}행 → 스냅샷 {sha} (활성)")
elif args.cmd == "precheck":
    c = ctx(); rows = {"card": lambda: prechecks.atoms(c.cards), "item": lambda: prechecks.items(c.items), "answer": lambda: prechecks.answers(c.answers)}[args.stage]()
    n = prechecks.write_new(store, rows)
    bad = Counter(r["check"] for r in rows if r["v"] != "pass")
    print(f"사전검사 {len(rows)}건 (신규 적재 {n}). 걸린 것: {dict(bad) or '없음'}")
elif args.cmd == "run":
    only = set(Path(args.only).read_text(encoding="utf-8").split()) if args.only else None
    runner.run_stage(args.stage, store, ctx(), args.judges.split(",") if args.judges else None, set(args.books.split(",")) if args.books else None, only,
                     args.repeat, args.canaries, args.include_blocked, args.limit, args.workers, args.stop_on_error, args.allow_same_family)
elif args.cmd == "decide":
    dec = DECIDE[args.stage](ctx())
    if args.show:
        print(json.dumps(dec[args.show], ensure_ascii=False, indent=1)); sys.exit()
    print(f"{args.stage} 판정:", dict(Counter(d["decision"] for d in dec.values())))
    why = Counter(n for d in dec.values() for n, r in d["checks"].items() if r["v"] in ("fail", "revise", "hold") and d["decision"] != "pass")
    print("걸린 체크:", dict(why.most_common()))
    if args.stage == "item":
        print("차단 사유:", dict(Counter(d["blocked_by"] for d in dec.values() if d["blocked_by"])))
    out = store.root / "derived" / f"decisions_{args.stage}.jsonl"
    out.write_text("".join(json.dumps({k: v for k, v in d.items() if k != "checks"}, ensure_ascii=False) + "\n" for d in dec.values()), encoding="utf-8")
elif args.cmd == "revise":
    revise.run_revise(store, ctx(), args.judge, args.limit, args.workers)
elif args.cmd == "human":
    if args.action == "export":
        human.export(store, ctx(), args.stage, args.rate, blind=not args.show_llm)
    else:
        human.import_csv(store, args.file, args.reviewer or "unknown")   # 라벨링 페이지 CSV는 reviewer 열이 있어 --reviewer 없이 된다
elif args.cmd == "calib":
    human.calib_sample(store, ctx(), args.stage, args.n)
elif args.cmd == "stats":
    rep = stats.report(ctx(), args.stage)
    if args.json:
        print(json.dumps(rep, ensure_ascii=False, indent=1)); sys.exit()
    for pair, d in rep["pairwise"].items():
        print(f"\n[일치도] {pair}")
        for ck, a in d.items():
            if a.get("n"): print(f"  {ck:24s} n={a['n']:4d} 일치={a['agree']:.3f} kappa={a['kappa']:.3f} AC1={a['ac1']:.3f}")
    for k, title in (("human_pairwise", "사람 간 일치도"), ("human_split", "사람끼리 갈린 단위"), ("flip_rate", "반복 시 뒤집힘"), ("canary", "카나리아 탐지"), ("vs_human", "사람 기준 대비"), ("approved_error", "승인본 표본 오류")):
        if rep.get(k): print(f"\n[{title}]", json.dumps(rep[k], ensure_ascii=False))
elif args.cmd == "release":
    if args.action == "build": release.build(store, cfg, reg, args.tag or sys.exit("tag 필요"), args.note)
    elif args.action == "verify": release.verify(store, args.tag or store.current_release())
    elif args.action == "rollback": store.set_current(args.tag, f"rollback: {args.note}"); print(f"CURRENT → {args.tag}")
    else:
        cur = store.current_release()
        for d in sorted((store.root / "releases").iterdir()):
            if d.is_dir():
                m = json.loads((d / "manifest.json").read_text()); print(("* " if d.name == cur else "  ") + f"{d.name}  {m['created_at']}  {m['counts']}  {m['note']}")
elif args.cmd == "index":
    db = store.root / "derived" / "index.sqlite"; db.unlink(missing_ok=True); con = sqlite3.connect(db)
    con.execute("create table verdicts(ts, run_id, stage, grp, unit_type, unit_id, unit_hash, chk, v, why, judge, rep, prompt_hash, extra)")
    rows = store.all_verdicts()
    con.executemany("insert into verdicts values(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", [(r["ts"], r["run_id"], r["stage"], r["group"], r["unit_type"], r["unit_id"], r["unit_hash"],
                    r["check"], r["v"], r.get("why", ""), r["judge"], r.get("rep", 0), r.get("prompt_hash", ""), json.dumps(r.get("extra", {}), ensure_ascii=False)) for r in rows])
    con.execute("create index i1 on verdicts(unit_id)"); con.commit(); print(f"{db}: {len(rows)}행")
