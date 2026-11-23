# 재생성 문항 재검수 (1회차, 11/23)

윤상이 만든 재생성 문항(A 174개, B 178개)을 검수한다. 생성 쪽 설명은 `data_in/<a8|b7>/regen1/README_REGEN.md`.

- 입력: `data_in/<묶음>/regen1/` (윤상 결과 그대로), `data_in/<묶음>/items_round1.jsonl` (기존 문항 + 재생성 문항을 합친 것, `tools/merge_regen.py`로 만듦)
- 합친 파일을 넣는 이유: `ingest`는 활성 문항 스냅샷을 통째로 바꾼다. 재생성 문항만 넣으면 기존 승인 문항이 사라진다.
- regenerate는 같은 item_id의 기존 문항을 교체하고, new_atom·fill_empty_cell은 새 item_id로 추가된다.
- 이미 판정된 기존 문항은 다시 호출하지 않는다. 호출은 재생성 문항만 (A 65장, B 약 70장 × 저지 2개).
- 주말 기준(자동 수정·재생성 1회 후 재검수)에 따라 이번에 탈락한 문항은 다시 만들지 않고 탈락·보류로 둔다.

## A묶음

```bash
python run.py --store store_a8 ingest items data_in/a8/items_round1.jsonl --label "재생성 1회차"
python run.py --store store_a8 run --stage item --only ids/a8_regen1.ids.txt --workers 4
python run.py --store store_a8 decide --stage item
python run.py --store store_a8 release build a8-v3 --note "재생성 1회차 반영"
python analysis/weekend_report.py --store store_a8 --only ids/a8_regen1.ids.txt --out reports/a8_regen1.md
python analysis/weekend_report.py --store store_a8 --data data_in/a8 --out reports/a8.md
```

## B묶음

`a8` → `b7`, `a8-v3` → `b7-v3`으로 바꿔 똑같이 실행한다.
