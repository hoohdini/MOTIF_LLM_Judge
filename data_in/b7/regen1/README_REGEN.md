# 검수 후 문항 재생성 (A묶음 8권 + B묶음 7권, 윤상)

성하 주말 검수(11/21~23) 결과로 문항을 다시 만든다. **문항 생성 코드는 그대로**다. `itemgen/`, `prompts/item_gen.v3.md`, `config.yaml`은 B묶음 1차 생성과 같고, 입력만 재생성 계획으로 바꿨다. 결과가 기존 결과와 섞이지 않게 `out_regen/v3/<A|B>/`에 따로 쌓는다.

## 입력 (`in/regen/`)
- **성하 승인본:** `cards_approved_*`, `items_approved_*`, `atoms_status_*`, `items_status_*`. 출처는 `검수통과_승인본/`이다. 복사만 하고 내용은 고치지 않았다.
- **성하 재생성 요청:** `regen_requests_A.jsonl`, `regen_requests_B.jsonl`.
- **재생성 계획:** `plan_<A|B>.jsonl`. `tools/regen_plan.py`가 만든다(LLM 0회).

## 무엇을 만드나

| action | A | B | 내용 |
|---|---|---|---|
| `regenerate` | 47 | 26 | atom은 그대로 둔다. 칸·형식·target도 같다. 검수 탈락 사유를 함께 넘긴다. |
| `new_atom` | 135 | 150 | `regenerate_for_new_atom` 요청 문항이다. 승인된 수정 atom(`.r1`, `.r1a` …)마다 원래 칸·형식·target으로 1문항씩 만든다. 쪼개진 atom은 같은 칸에 문항이 2~3개 생긴다. |
| `fill_empty_cell` | 1 | 8 | **요청 목록에는 없다.** 원래 생성 때 생략돼 비어 있던 칸(atom 01~03)의 수정 atom이 승인된 경우라서 선제적으로 만든다. 성하 확인이 필요하다. |
| **합계** | **183** | **184** | |

안 만드는 것은 `plan_<g>.skipped.jsonl`에 이유와 함께 남긴다.
- drop은 A 51개, B 67개다.
- 수정 atom이 재검수에서 hold·fail이라 새 atom이 없는 요청은 A 53개, B 58개다.
- 예비 atom(04~)은 A 7개, B 11개다.

## 형식·target 고정
- 원래 설계(`design.py`, seed 7)와 같은 규칙으로 다시 계산한다. atom 번호가 곧 support 순위라서, S별 원래 atom 수만 알면 설계가 그대로 재현된다.
- 검증 결과는 다음과 같다.
  - B는 `cards_b7.jsonl` 설계 612칸과 대조해 불일치가 0이다.
  - 승인 문항의 TF·YN 정답과 대조해 A 77개, B 49개 모두 불일치가 0이다.
- 쪼개진 atom도 원래 칸의 target을 그대로 쓴다.

## 탈락 사유 전달 방식
`regenerate` 문항만 ITEMS TO WRITE의 해당 문항 아래에 한 줄을 붙인다. 프롬프트 본문(system/user 템플릿)은 바꾸지 않았다.

```
  PREVIOUS VERSION FAILED REVIEW (write a new item that avoids these problems): NO_LEAK: … ; YN_CASE_FORMAT: …
```

이전 문항 원문은 넣지 않는다. A 원래 문항 파일이 없어서, A와 B를 같은 방식으로 맞추려고 사유만 넣었다.

## 실행 (윤상 Mac)
```bash
cd itemgen_b7
./run_regen.sh pilot      # A CS-PL-C03, B MED-IMM-C01 두 장만 호출 (세 action이 다 들어 있는 카드)
./run_regen.sh full       # 나머지 전부. 15권을 동시에 8개씩 (PAR=4 ./run_regen.sh full 로 줄일 수 있음)
./run_regen.sh check      # 점검만
```
- 이미 만든 카드는 건너뛴다. 실패한 카드가 있으면 같은 명령을 다시 실행하면 그 카드만 호출한다. 자동 재시도는 하지 않는다(중복 과금 방지).
- 진행 상황은 `tail -f out_regen/v3/run_logs/full.*.log`로 본다.
- API 한도(429), 인증, 서버, JSON 오류는 `out_regen/v3/check_regen.md`의 '실패'에 종류별로 나온다.

## 결과물 (`out_regen/v3/<A|B>/`)
- `items.<책>.jsonl`: 기존 문항 필드에 `regen_action`, `regen_of`(원래 item_id, fill은 null), `regen_round: 1`을 추가했다.
- `omitted.<책>.jsonl`: 생성기가 생략한 칸이다.
- `logs/<card>.json`: 전체 요청·응답, 프롬프트 해시, 사용량이 들어 있다. 실패한 카드는 `<card>.failed.json`이다.
- mock 결과는 `out_regen/v3/mock_<g>/`에 따로 있다. 흐름 확인용이고, 전달하지 않는다.

## 실행 결과 (11/23)

| | A | B |
|---|---|---|
| regenerate | 41 / 47 | 25 / 26 |
| new_atom | 133 / 135 | 150 / 150 |
| fill_empty_cell | 0 / 1 | 3 / 8 |
| **생성 / 계획** | **174 / 183** | **178 / 184** |
| 생성기 생략 (`omitted`) | 9 | 6 |

- 모든 문항이 v3 프롬프트(sha256 `fbf82afd…`), `claude-sonnet-5-5`로 만들어졌다. API 한도 오류는 없었다.
- Letsur 예상 비용은 2.41 unit이다(성공한 호출 기준). 실패한 호출 4번(약 0.02)은 합계에 들어 있지 않다.
- `MATH-PROB-C13`(A)은 첫 실행에서 실패했고, 다시 실행해서 성공했다.
- `MATH-TOP-C06`(B)은 모델 응답에 `item_id`가 빠져 공용 코드에서 `KeyError`가 났다. temperature가 0이라 같은 응답이 반복됐다.
  - 요청 1문항, 응답 1문항이라 어느 문항인지 모호하지 않았다.
  - 그래서 `tools/fill_missing_id.py`로 이미 받은 응답에 `item_id`만 채웠다. API는 다시 호출하지 않았다.
  - 문항 `flags`에 `item_id_filled_by_script`가 붙어 있다. 원래 실패 로그는 `logs/failed_resolved/`에 있다.
  - 실패한 2장은 둘 다 1문항짜리 카드였다. 공용 코드는 `item_id`가 없는 항목이 하나만 있어도 카드 전체를 실패로 처리한다.
- 검수 입력 파일은 `audit_input.<A|B>.jsonl`이다. 형식은 1차의 `run.py audit-input`과 같고, `regen_action`과 `regen_of`를 추가했다.
