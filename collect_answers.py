"""승인된 문항을 평가 대상 모델에게 풀게 하고 답변을 answers.jsonl로 모은다 (파일럿용).

사용:
  python collect_answers.py --store store_a8 --per-book 6
  python collect_answers.py --store store_a8                      # 승인 문항 전체
  python collect_answers.py --store store_a8 --models claude-haiku-5-5,gpt-6.1-terra

- 문항은 그 store의 현재 승인본(releases/CURRENT)의 items_approved.jsonl에서 읽는다.
- 응시자에게는 질문과 보기만 보낸다 (atom·근거·정답은 보내지 않는다).
- 이미 받은 (문항, 모델) 답변은 건너뛴다. 실패한 호출은 같은 명령을 다시 실행하면 이어서 받는다.
- 결과: answers/<store>/answers.jsonl (한 줄 = {item_id, model, response, rep, usage}).
"""
import argparse, hashlib, json, random, sys, threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
from kcaudit.common import load_env, read_jsonl, book_of, now   # noqa: E402
from kcaudit import judges                                      # noqa: E402

DEFAULT_MODELS = "claude-haiku-5-5,gpt-6.1-terra,deepseek-v4-flash"
SYSTEM = "You are taking a closed-book knowledge test. Answer from your own knowledge. Follow the answer format exactly."
TAIL = {"TF": "Answer with exactly one word: True or False.",
        "YN": "Answer with exactly one word: Yes or No.",
        "MCQ": "Answer with exactly one letter: A, B, C, or D.",
        "OPEN": "Answer in one to three sentences."}


def build_prompt(it):
    q = it["question"].strip()
    if it["format"] == "MCQ" and not all(v.strip() in q for v in it["options"].values()):   # 질문에 보기가 이미 들어 있으면 다시 붙이지 않는다
        q += "\n\n" + "\n".join(f"{k}. {v}" for k, v in sorted(it["options"].items()))
    return f"{q}\n\n{TAIL[it['format']]}"


def model_cfg(model, max_tokens):
    low = model.lower()
    cfg = {"provider": "openai_compat", "model": model, "base_url_env": "LETSUR_BASE_URL", "key_env": "LETSUR_API_KEY", "max_tokens": max_tokens}
    if low.startswith(("gpt", "o3", "o4", "gemini")):
        cfg["token_param"] = "max_completion_tokens"            # 추론 모델은 이 이름으로 출력 상한을 받는다
    return cfg


def mock_answer(it, model):
    r = random.Random(f"{model}:{it['item_id']}")
    if it["format"] == "OPEN":
        return " ".join(it["key_points"]) if r.random() < 0.6 else "I am not sure about this."
    pool = {"TF": ["True", "False"], "YN": ["Yes", "No"], "MCQ": list("ABCD")}[it["format"]]
    return it["answer"] if r.random() < 0.7 else r.choice(pool)


ap = argparse.ArgumentParser()
ap.add_argument("--store", required=True)
ap.add_argument("--models", default=DEFAULT_MODELS, help="쉼표로 구분한 Letsur 모델 코드")
ap.add_argument("--per-book", type=int, help="책마다 이 개수만 뽑는다 (seed 고정). 생략하면 승인 문항 전체")
ap.add_argument("--workers", type=int, default=4)
ap.add_argument("--max-tokens", type=int, default=8000)
ap.add_argument("--seed", type=int, default=7)
ap.add_argument("--mock", action="store_true", help="API 없이 가짜 답변으로 흐름만 확인")
a = ap.parse_args()
load_env()

rel = ROOT / a.store / "releases"
cur = (rel / "CURRENT").read_text(encoding="utf-8").strip()
items = list(read_jsonl(rel / cur / "items_approved.jsonl"))
if a.per_book:
    by = defaultdict(list)
    for it in items:
        by[book_of(it["item_id"])].append(it)
    key = lambda it: hashlib.sha256(f"{a.seed}:{it['item_id']}".encode()).hexdigest()
    items = [it for b in sorted(by) for it in sorted(by[b], key=key)[: a.per_book]]
models = [m.strip() for m in a.models.split(",") if m.strip()]
out = ROOT / "answers" / a.store / "answers.jsonl"; out.parent.mkdir(parents=True, exist_ok=True)
done = {(r["item_id"], r["model"]) for r in read_jsonl(out)} if out.exists() else set()
todo = [(it, m) for m in models for it in items if (it["item_id"], m) not in done]
print(f"승인본 {cur}: 문항 {len(items)}개 × 모델 {len(models)}개 = {len(items) * len(models)}건, 이미 받은 것 {len(items) * len(models) - len(todo)}건, 이번에 받을 것 {len(todo)}건")
print("형식:", dict(Counter(it["format"] for it in items)))

lock = threading.Lock(); stat = Counter(); cost = defaultdict(float); errs = []


def work(job):
    it, m = job
    try:
        if a.mock:
            text, usage = mock_answer(it, m), {"mock": True}
        else:
            text, usage = judges.call(m, model_cfg(m, a.max_tokens), SYSTEM, build_prompt(it))
        row = {"item_id": it["item_id"], "model": m, "response": text.strip(), "rep": 0, "ts": now(), "usage": usage}
        with lock:
            with open(out, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            stat[(m, "ok")] += 1
            try: cost[m] += float(((usage or {}).get("estimated_cost") or {}).get("amount") or 0)
            except Exception: pass
    except Exception as e:                                         # 실패는 기록만 하고 넘어간다. 다시 실행하면 이어서 받는다
        with lock:
            stat[(m, "fail")] += 1; errs.append(f"{m} {it['item_id']}: {str(e)[:160]}")


with ThreadPoolExecutor(max_workers=a.workers) as ex:
    list(ex.map(work, todo))
for m in models:
    print(f"{m}: 성공 {stat[(m, 'ok')]}, 실패 {stat[(m, 'fail')]}, 비용 {cost[m]:.3f} unit")
for e in errs[:5]:
    print("  실패:", e)
print(f"\n저장: {out.relative_to(ROOT)}")
