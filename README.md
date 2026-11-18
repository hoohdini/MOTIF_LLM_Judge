# kc_audit — Knowledge Card 검수 파이프라인

## 빠른 시작 (처음 받은 사람용)

### 1. 설치 (한 번만)

압축을 풀고 터미널에서 `kc_audit` 폴더로 이동한다. Python 3.10 이상이 필요하다.

```bash
cd kc_audit
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Windows에서는 아래 명령의 `python3`를 `python`으로 바꿔 쓴다.

### 2. 키 넣기

`.env.example`을 복사해 `.env`를 만들고 `LETSUR_API_KEY=` 뒤에 발급받은 키를 붙인다.
`.env`는 절대 공유하거나 git에 올리지 않는다(.gitignore에 이미 빠져 있다).

### 3. 모델 고르고 연결 확인

```bash
python3 check_letsur.py                  # 쓸 수 있는 모델 코드와 단가 목록
python3 check_letsur.py <GPT 모델 코드>    # 테스트 호출 1번 (비용 확인)
python3 check_letsur.py <Gemini 모델 코드>
```

`config.yaml`에서
- `judge_a`의 `model:`에 GPT 코드, `judge_b`의 `model:`에 Gemini 코드를 넣는다.
- 테스트 호출 끝에 나온 `token_param` 값을 각 저지에 맞춰 둔다.

### 4. 데이터 넣기와 사람 라벨 적재

```bash
python3 run.py ingest cards data_in/cards.jsonl --label "연욱 v2"
python3 run.py ingest items data_in/items/items.*.jsonl --label "윤상 v2"
python3 run.py human import --file calib/calib_human_labels.csv
```

### 5. 보정 세트 240개 돌리기 (저지 검증)

```bash
python3 run.py run --stage card --only calib/calib_card.ids.txt --limit 2   # 먼저 2번만 호출해 확인
python3 run.py run --stage card --only calib/calib_card.ids.txt
python3 run.py run --stage item --only calib/calib_item.ids.txt --include-blocked
python3 run.py stats --stage card
python3 run.py stats --stage item
```

- `--only`를 붙이면 보정 세트 단위만 보낸다. 빼면 전체를 돌리니 주의.
- 중간에 끊기거나 한도에 걸려도 같은 명령을 다시 실행하면 빠진 것만 이어서 돈다.
- `stats`의 `[사람 기준 대비]`가 사람 라벨과의 일치도다(`kappa`, `ac1`, `fail_recall`).
- 응답 원문과 비용(`estimated_cost`)은 `store/runs/<실행ID>/raw/`에 남는다.

### 6. 전체 검수 (보정 결과를 보고 저지를 확정한 뒤)

```bash
python3 run.py run --stage card --workers 4
python3 run.py decide --stage card
python3 run.py revise && python3 run.py run --stage card     # reviser 모델 코드를 넣어야 함
python3 run.py run --stage item --workers 4
python3 run.py release build v1 --note "1차 검수"
```

API 없이 흐름만 보고 싶으면 명령마다 `--config config.mock.yaml`을 붙인다(가짜 판정).

---

카드 검수, 문항 검수, 답변 채점을 같은 엔진으로 돌린다. 모든 판정은
**단위 × 체크 × 저지 → 판정** 한 줄로 원장(`store/ledger/verdicts.jsonl`)에 쌓이고, 지우거나 덮어쓰지 않는다.

## 단계

| 단계 | 단위 | 누가 | 결과 |
| --- | --- | --- | --- |
| precheck | atom, 문항, 답변 | 코드 | 형식 오류, 출처 정규식, 깨진 수식 표시, TF·YN·MCQ 답변 채점 |
| card | atom (카드 1장 = 호출 1번) | 저지 2개 | pass / revise / fail / hold |
| revise | revise 받은 atom | reviser | 분리·수정본 → card 단계에서 다시 검수 (1회 한도) |
| item | 문항 (카드 1장 = 호출 1번) | 저지 2개 | pass / fail / hold, 재생성 목록 |
| answer | OPEN 답변 | 저지 2개 | correct / partial / incorrect / hold |
| human | 보류 + 무작위 표본 | 사람 | 최우선 판정으로 적재 |
| stats | 저지 | 코드 | 일치도, 사람 대비 정확도, 카나리아 탐지율, 오류율 상한 |
| release | 승인본 | 코드 | 태그별 보관, 롤백, 재현 확인 |

합산 규칙: 사람 판정이 있으면 그것. 없으면 저지 전원이 같은 값일 때만 그 값, 엇갈리면 hold.
단위 판정은 blocker 체크 기준 fail > pending > hold > revise > pass.
문항은 자기 atom이 pass일 때만 유효하고, atom이 수정되면 자동으로 `blocked`가 된다.

## 처음 한 번: API 없이 흐름 확인

```bash
python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
C="--config config.mock.yaml"
python run.py $C ingest cards data_in/cards.jsonl --label "연욱 v2"
python run.py $C ingest items data_in/items/items.*.jsonl --label "윤상 v2"
python run.py $C ingest preaudit data_in/audit_v2.csv --label opus-5.5
python run.py $C run --stage card --canaries 20
python run.py $C decide --stage card
python run.py $C revise && python run.py $C run --stage card
python run.py $C run --stage item --canaries 20
python run.py $C stats --stage card
python run.py $C release build demo-1 && python run.py $C release verify demo-1
```

mock 저지의 판정은 무작위라 숫자에 의미는 없다. 흐름만 본다. 끝나면 `store_mock/`을 지운다.

## 실제 실행 순서

1. `cp .env.example .env` 후 키 입력. `config.yaml`의 `judge_a`, `judge_b`에 모델명 입력 (생성 모델과 다른 계열).
2. `ingest` 세 줄 (위와 같음, `--config` 없이).
3. **저지 선정**: 보정 세트는 `calib/`에 이미 뽑아 두었다 (atom 120, 문항 120, 기준은 `calib/LABELING.md`).
   두 사람이 각자 `human_v`를 채움 → `human import --file … --reviewer 이름` (사람마다 한 번씩)
   → `run --stage card --only calib/calib_card.ids.txt --repeat 3` → `stats --stage card` (문항도 같은 방식).
   `human_pairwise`(사람 간 일치도)가 저지에게 기대할 수 있는 상한이다. `vs_human`의 kappa·AC1·fail_recall과 `flip_rate`를 보고 저지를 확정한다.
   다시 뽑으려면 `calib --stage card --n 120`.
4. **카드 검수**: `run --stage card --canaries 20 --workers 4` → `decide` → `revise` → `run --stage card` (수정본만 다시 돈다).
5. **문항 검수**: `run --stage item --canaries 20 --workers 4`. 카드 검수를 기다리지 않고 돌리려면 `--include-blocked`.
6. **사람 검수**: `human export --stage card` → CSV 채움 → `human import`. 보류된 것과 만장일치 표본 8%만 나온다.
7. **릴리스**: `release build v1 --note "…"`. `cards_approved.jsonl`, `items_approved.jsonl`, `regen_requests.jsonl`이 나온다.
8. **답변**: `ingest answers answers.jsonl` → `run --stage answer` → `human export --stage answer` → `release build v2`.

중단되거나 일부 실패해도 같은 명령을 다시 실행하면 빠진 것만 이어서 돈다. 자동 재시도는 없다(중복 과금 방지).

## 입력 형식

- 카드, 문항: 기존 `cards.jsonl`, `items.<책>.jsonl` 그대로.
- 답변: 한 줄에 `{"item_id": "...", "model": "...", "response": "...", "rep": 0}`.
  TF·YN·MCQ는 라벨로 답하게 수집해야 코드 채점이 된다. 라벨을 하나로 읽지 못하면 보류로 간다.

## 바꿀 때 고치는 곳

| 바꾸려는 것 | 고칠 곳 |
| --- | --- |
| 체크 추가·기준 수정 | `checks.yaml` (desc가 프롬프트에 그대로 들어감) |
| 저지 모델, 저지 수 | `config.yaml`의 `judges`, `stages` |
| 사람 표본 비율, 수식 근거 정책, 수정 횟수 | `config.yaml`의 `policy` |
| 프롬프트 문구 | `prompts/*.md` |

체크 설명이나 프롬프트가 바뀌면 그 그룹의 기존 LLM 판정은 자동으로 무효(pending)가 되고 다시 돌릴 대상이 된다.
사람 판정과 코드 판정은 유지된다.

## 적재 구조와 롤백

```
store/
  snapshots/<종류>/<해시>/   원본 스냅샷 (불변)      ACTIVE.json이 현재 쓰는 것을 가리킴
  ledger/verdicts.jsonl      모든 판정 (추가만)
  ledger/revisions.jsonl     atom 수정 기록 (추가만)
  runs/<run_id>/             실행별 설정·프롬프트 사본, 모델 응답 원문(raw/), 실패 응답(failed/)
  human/                     사람 검수 CSV
  releases/<태그>/           승인본 + manifest   CURRENT가 현재 릴리스
  derived/                   조회용 파생물 (index.sqlite 등, 지워도 됨)
```

- `release rollback <태그>`: CURRENT 포인터만 옮긴다. 이력은 `releases/history.jsonl`.
- `release verify <태그>`: manifest(스냅샷 해시, 원장 위치, 프롬프트 해시)만으로 다시 만들어 파일 해시를 비교한다.
- 새 카드 묶음(b2 등)은 `ingest cards`로 새 스냅샷을 만들면 된다. 내용이 같은 atom은 해시가 같아 다시 판정하지 않는다.
- 코드, `checks.yaml`, `prompts/`는 git으로 관리한다. `store/`는 `.gitignore`에 있으니 따로 백업한다.

## 아직 안 된 것

- 실제 Letsur 호출은 아직 실행해 보지 못했다. 첫 실행은 `check_letsur.py`와 `--limit 2`로 확인할 것.
- 수학책 PDF 페이지 첨부는 없다. 지금은 저지가 깨진 근거를 읽을 수 없으면 hold를 내게 되어 있다
  (`policy.math_evidence: hold`로 바꾸면 해당 체크를 전부 사람에게 보낸다. atom 170개, 문항 165개 규모).
- 문항 재생성 자체는 itemgen 쪽 일이다. 여기서는 `regen_requests.jsonl`(사유 포함)까지만 만든다.
- 1안(자유 서술)의 주장 분해와 카드 전체 매칭은 없다. 지금 답변 단계는 문항별 key_points 매칭이다.
- 프롬프트는 초안이다. 보정 세트 결과를 보고 고쳐야 한다.
