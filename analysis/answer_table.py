"""답변별 채점 결과를 한 줄씩 펼친 표 (검토용).

사용: python analysis/answer_table.py --store store_a8 [--out reports/answer_table_a8.csv]
한 줄 = 답변 1건: 문항, 정답(또는 key point), 모델, 답변, 최종 판정, 저지별 판정·key point별 상태·사유, 추가 내용 표시.
"""
import argparse, csv, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kcaudit.common import load_yaml, book_of              # noqa: E402
from kcaudit.store import Store                            # noqa: E402
from kcaudit.aggregate import Ctx, Registry, decide_answer # noqa: E402

COLS = ["store", "book", "item_id", "format", "model", "question", "key", "response", "verdict",
        "judge_1", "judge_1_verdict", "judge_1_points", "judge_1_why", "judge_2", "judge_2_verdict", "judge_2_points", "judge_2_why",
        "additional_content", "atom"]


def rows(store_name, config="config.yaml"):
    cfg = load_yaml(ROOT / config); cfg["store"] = store_name
    ctx = Ctx(Store(store_name), cfg, Registry()); dec = decide_answer(ctx)
    ph = ctx.phash[ctx.reg.group("answer")[0]]
    ans = {a["_id"]: a for a in ctx.answers}
    pts, add = {}, {}
    for r in ctx.rows:                                       # 같은 저지의 나중 행이 앞의 행을 대신한다
        if r.get("stage") == "answer" and r.get("prompt_hash") == ph:
            if r["check"] == "KEYPOINTS":
                pts[(r["unit_id"], r["judge"])] = " / ".join((r.get("extra") or {}).get("points") or [])
            elif r["check"] == "ADDITIONAL_CONTENT":
                add[(r["unit_id"], r["judge"])] = r["v"]
    out = []
    for uid, d in dec.items():
        a = ans[uid]; it = a["_item"]
        key = "\n".join(f"{k}. {p}" for k, p in enumerate(it["key_points"], 1)) if it["format"] == "OPEN" else it["answer"]
        row = {"store": store_name, "book": book_of(it["item_id"]), "item_id": it["item_id"], "format": it["format"], "model": d["model"],
               "question": it["question"], "key": key, "response": a["response"], "verdict": d["own"], "atom": it["atom_statement"]}
        if it["format"] == "OPEN":
            r = d["checks"]["KEYPOINTS"]
            for n, j in enumerate(sorted(r["by"]), 1):
                row[f"judge_{n}"] = cfg["judges"][j]["model"]; row[f"judge_{n}_verdict"] = r["by"][j]
                row[f"judge_{n}_points"] = pts.get((uid, j), ""); row[f"judge_{n}_why"] = r["why"].get(j, "")
            row["additional_content"] = " / ".join(f"{cfg['judges'][j]['model']}={add[(uid, j)]}" for j in sorted(r["by"]) if (uid, j) in add)
        else:
            row["judge_1"] = "code"; row["judge_1_verdict"] = d["own"]
        out.append(row)
    order = {"hold": 0, "incorrect": 1, "partial": 2, "correct": 3}
    out.sort(key=lambda r: (order.get(r["verdict"], 9), r["item_id"], r["model"]))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.yaml"); ap.add_argument("--store", required=True); ap.add_argument("--out")
    a = ap.parse_args()
    data = rows(a.store, a.config)
    out = Path(a.out) if a.out else ROOT / "reports" / f"answer_table_{a.store.replace('store_', '')}.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", encoding="utf-8-sig", newline="") as f:      # utf-8-sig: 엑셀에서 한글이 깨지지 않게
        w = csv.DictWriter(f, fieldnames=COLS); w.writeheader(); w.writerows(data)
    print(f"{len(data)}행 → {out}")
