"""답변 채점 집계 (파일럿). 모델별 정답률을 형식·분야로 나눠 낸다.

사용: python analysis/answer_report.py --store store_a8 [--out reports/answers_a8.md]
- TF·YN·MCQ: 코드가 라벨을 읽어 정답과 비교 (correct / incorrect / hold=라벨을 못 읽음).
- OPEN: 저지 2개가 key point별로 대조 (correct / partial / incorrect / hold=저지 불일치 등 / pending=미채점).
- 정답률 = correct / (correct + partial + incorrect). hold·pending은 분모에서 빼고 따로 센다.
"""
import argparse, sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from kcaudit.common import load_yaml, book_of              # noqa: E402
from kcaudit.store import Store                            # noqa: E402
from kcaudit.aggregate import Ctx, Registry, decide_answer # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--config", default="config.yaml"); ap.add_argument("--store", required=True); ap.add_argument("--out")
a = ap.parse_args()
cfg = load_yaml(ROOT / a.config); cfg["store"] = a.store
ctx = Ctx(Store(a.store), cfg, Registry())
dec = decide_answer(ctx)
L = []; P = L.append
ORDER = ["correct", "partial", "incorrect", "hold", "pending"]


def line(rows):
    c = Counter(d["own"] for d in rows); n = c["correct"] + c["partial"] + c["incorrect"]
    acc = f"{100 * c['correct'] / n:.1f}%" if n else "-"
    return f"{len(rows)} | {acc} | " + " | ".join(str(c[k]) for k in ORDER)


def table(title, keyf, keys=None):
    P(""); P(f"## {title}"); P("")
    P("| 모델 | 구분 | 답변 수 | 정답률 | correct | partial | incorrect | hold | pending |"); P("| --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    g = defaultdict(list)
    for d in dec.values():
        g[(d["model"], keyf(d))].append(d)
    for m in sorted({k[0] for k in g}):
        for k in (keys or sorted({k[1] for k in g})):
            if (m, k) in g:
                P(f"| {m} | {k} | {line(g[(m, k)])} |")


P(f"# 답변 채점 집계 — {a.store}"); P("")
P(f"- 답변 {len(dec)}건, 문항 {len({d['item_id'] for d in dec.values()})}개, 모델 {len({d['model'] for d in dec.values()})}개")
ex = sum(1 for d in dec.values() if d["decision"] == "excluded")
if ex:
    P(f"- 승인되지 않은 문항의 답변 {ex}건이 섞여 있다 (아래 표에는 포함).")
table("모델별 전체", lambda d: "전체")
table("형식별", lambda d: d["format"], ["OPEN", "TF", "MCQ", "YN"])
table("분야별", lambda d: book_of(d["item_id"]).split("-")[0])
table("책별", lambda d: book_of(d["item_id"]))
txt = "\n".join(L) + "\n"
print(txt)
if a.out:
    Path(a.out).parent.mkdir(parents=True, exist_ok=True); Path(a.out).write_text(txt, encoding="utf-8")
