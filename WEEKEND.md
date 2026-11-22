# 주말 검수 실행 순서 (11/21~23)

기준: 회의 #4 수정본 프롬프트, 저지 `gpt-6.1-sol` + `gemini-4-argon`, reviser `claude-sonnet-5-5`, 합산 `judge_final`.
묶음마다 store를 따로 쓴다: 기존 9권 = `store`(그대로), A묶음 = `store_a8`, B묶음 = `store_b7`.
호출이 실패(503 등)하면 같은 명령을 다시 실행한다. 이미 받은 판정은 건너뛴다.

## 0. 준비

```bash
git fetch && git checkout weekend/audit-v3
python check_letsur.py            # 모델 목록·잔액 확인
```

## 1. 기존 9권 표본 9장 (비교 실험의 기존 쪽)

```bash
python run.py run --stage card --only ids/old9_sample9.ids.txt
python run.py run --stage item --only ids/old9_sample9.ids.txt --include-blocked
python analysis/weekend_report.py --store store --only ids/old9_sample9.ids.txt --out reports/old9_sample9.md
```

## 2. A묶음 (B묶음은 a8 → b7, 라벨만 바꿔 똑같이)

```bash
python run.py --store store_a8 ingest cards data_in/a8/cards.jsonl --label "연욱 a8"
python run.py --store store_a8 ingest items "data_in/a8/items/items.*.jsonl" --label "재현 a8 v3"

# 책당 첫 카드 1장만 먼저 (공통 오류 확인)
python run.py --store store_a8 run --stage card --only ids/a8_first_card.ids.txt
python run.py --store store_a8 run --stage item --only ids/a8_first_card.ids.txt --include-blocked
python run.py --store store_a8 decide --stage card
python run.py --store store_a8 decide --stage item

# 이상 없으면 전체
python run.py --store store_a8 run --stage card --workers 4
python run.py --store store_a8 run --stage item --include-blocked --workers 4

# 자동 수정 1회 → 수정본만 재검수
python run.py --store store_a8 revise
python run.py --store store_a8 run --stage card --workers 4

# 승인본·재생성 요청 목록, 집계표
python run.py --store store_a8 release build a8-v1 --note "주말 1차"
python analysis/weekend_report.py --store store_a8 --data data_in/a8 --out reports/a8.md
```

- `store_a8/releases/a8-v1/regen_requests.jsonl` = 재생성 요청 목록(사유 포함). 재현·윤상에게 넘긴다.
- 집계표는 최초 결과(자동 수정 전)와 수정 후 결과를 한 번에 따로 낸다. 생성 생략은 `data_in/<묶음>/omitted/`에서 읽는다.
- `--include-blocked`: atom이 아직 통과 전이어도 문항을 검수한다(문항 최초 통과율을 전체 문항 기준으로 내기 위해).
  최종 확보에는 atom도 통과한 문항만 들어간다.

## 3. 같은 개념 3쌍 비교 (9장 재추출 대신)

| 기존 | 신규 | 개념 |
| --- | --- | --- |
| LAPINF-C04 | MATH-ANA-C04 (B) | Markovian uniqueness |
| FPPROG-C05 | CS-PL-C03 (A) | Probabilistic coupling |
| IVFLUID-C03 | MED-PHYS-C10 (A) | Fluid responsiveness |

```bash
python analysis/weekend_report.py --store store    --only ids/pair3_old.ids.txt    --out reports/pair3_old.md
python analysis/weekend_report.py --store store_a8 --only ids/pair3_new_a8.ids.txt --out reports/pair3_new_a8.md
python analysis/weekend_report.py --store store_b7 --only ids/pair3_new_b7.ids.txt --out reports/pair3_new_b7.md
```

표본 3쌍이고 입력 페이지·카드 생성 경로가 기존과 다르다. 프롬프트 효과만 분리한 비교가 아니므로 참고용으로만 쓴다.

## 이번 브랜치에서 바뀐 것

- 검수·수정 프롬프트를 회의 #4 수정본으로 교체 (`atom_audit.v2`, `item_audit.v3`, `atom_revise.v2`, `checks.yaml`). GROUNDED·KEY_CORRECT에 hold 허용.
- 합산 규칙 `judge_final` 추가 (11/18 결정). `config.yaml`의 `policy.aggregate`로 바꾼다.
- 책 코드에 `-`가 들어가도 인식 (`CS-COMP`, `MATH-ANA` …).
- `--store` 옵션, reviser 모델 입력, 응답 모델 ID·전송 파라미터 저장.
- 생성 쪽 플래그(`DRAFT_REQUIRES_AUDIT` 등)는 저지 프롬프트에 넣지 않음 (A·B를 같은 조건으로 판정).
- 입력 위치 변경: 기존 9권 `data_in/old9/`, A묶음 `data_in/a8/`, B묶음 `data_in/b7/`.

## 기록해 둘 설정 차이

- A묶음 카드는 Claude Code 서브에이전트로 생성(effort·max_tokens 미설정), B묶음 카드는 Letsur API(effort high). 문항 생성은 A·B 모두 Letsur, temperature 0, max_tokens 12000, 프롬프트 v3.
- 저지 요청값: `max_completion_tokens` 16000, reasoning_effort·temperature 미전송(게이트웨이 기본값).
