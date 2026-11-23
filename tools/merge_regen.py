"""기존 문항에 재생성 문항을 덮어써 검수용 문항 파일 하나로 합친다.

사용: python tools/merge_regen.py --base "data_in/a8/items/items.*.jsonl" --regen "data_in/a8/regen1/items.*.jsonl" --out data_in/a8/items_round1.jsonl

- run.py ingest는 활성 문항 스냅샷을 통째로 바꾸므로, 재생성 문항만 넣으면 기존 문항이 사라진다. 그래서 합친 파일을 넣는다.
- regenerate: 같은 item_id의 기존 문항을 새 문항으로 바꾼다 (새 내용이라 해시가 달라져 다시 검수된다).
- new_atom / fill_empty_cell: 새 item_id로 추가한다.
- 기존 문항 중 atom이 수정·폐기된 것은 그대로 둔다. 판정 단계에서 blocked(atom_changed)로 남아 승인되지 않는다.
"""
import argparse, glob, json
from collections import Counter

ap = argparse.ArgumentParser()
ap.add_argument("--base", required=True); ap.add_argument("--regen", required=True); ap.add_argument("--out", required=True)
a = ap.parse_args()
read = lambda pat: [json.loads(l) for p in sorted(glob.glob(pat)) for l in open(p, encoding="utf-8") if l.strip()]
base, regen = read(a.base), read(a.regen)
ids = [r["item_id"] for r in regen]
dup = {i for i in ids if ids.count(i) > 1}
if dup:
    raise SystemExit(f"재생성 문항에 중복 id: {sorted(dup)[:5]}")
by = {r["item_id"]: r for r in base}
stat = Counter()
for r in regen:
    act = r.get("regen_action", "?")
    if r["item_id"] in by:
        stat[f"{act}: 기존 문항 교체"] += 1
    else:
        stat[f"{act}: 새 문항 추가"] += 1
    by[r["item_id"]] = r
with open(a.out, "w", encoding="utf-8") as f:
    for r in by.values():
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"기존 {len(base)} + 재생성 {len(regen)} → {len(by)}개 ({a.out})")
for k, v in sorted(stat.items()):
    print(f"  {k} {v}")
