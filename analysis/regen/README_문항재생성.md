# 문항 재생성 요청 (11/18 검수 1차 결과)

## 배경
800문항 중 76개가 최종 통과했습니다. 나머지는 대부분 문항 자체가 아니라 **바탕 atom이 수정·분리되거나 탈락**해서 무효가 됐습니다.
atom은 자동 수정 후 재검수까지 마쳐 350개가 통과했고, 이 atom들로 문항을 새로 만들어야 합니다.

## 파일: `regen_for_generation.jsonl` (724줄, 한 줄 = 문항 칸 하나)

| status | 개수 | 할 일 |
|---|---|---|
| `ready_same_atom` | 13 | atom은 통과, 문항만 불통과. **같은 atom으로 다시 생성**. `fix_hint`에 탈락 이유 |
| `ready_new_atom` | 180 | 원래 atom이 수정·분리됨. **`atom` 필드의 새 atom으로 생성** |
| `ready_replacement_atom` | 30 | 원래 atom은 탈락. 같은 카드·같은 S의 **다른 통과 atom으로 생성** |
| `wait` | 266 | atom이 아직 보류. **지금은 생성하지 않음** (보류 정리 후 다시 요청) |
| `drop` | 235 | 쓸 atom이 없음. **생성하지 않음** |

→ **생성 대상: `ready_`로 시작하는 223개** (OPEN 79, YN 72, TF 50, MCQ 22)

각 줄의 필드
- `item_id`, `old_atom_id`: 원래 문항과 atom (참고용)
- `card_id`, `concept`, `cell`, `mode`, `format`: **이 칸의 모드·형식 그대로** 만들면 됩니다
- `atom`: 문항을 만들 atom (`atom_id`, `scope`, `statement`, `evidence`)

## 생성 규칙
기존 v2 생성 프롬프트를 그대로 쓰되, 오늘 검수에서 많이 걸린 아래 다섯 가지를 지켜주세요.
1. **정답은 atom 하나만으로 확정돼야 합니다.** False/No 정답도 atom이 그 진술을 직접 배제해야 합니다. 배경지식이 필요하면 탈락입니다.
2. **YN 사례**는 구체적인 대상(환자, 시스템, 수학적 대상)을 묘사하고, "이 대상이 ○○인가/○○를 보이는가"를 묻습니다. "이 주장·방법이 맞는가/적절한가"는 탈락입니다.
3. **질문에 정의나 판정 기준을 써주지 않습니다** (예: 등급표, 정의 문장을 질문에 넣으면 지식 없이 풀림 → NO_LEAK 탈락).
4. **TF False와 MCQ 오답**은 정답에서 정확히 한 요소(수량·방향·조건·대상·부정 중 하나)만 바꿉니다. MCQ 오답 세 개는 서로 다른 요소를 바꿉니다.
5. "according to the authors", "this chapter", "Theorem 3.2" 같은 출처 표현은 쓰지 않습니다.

## 출력 형식 (기존 items.*.jsonl과 같은 스키마)
- `item_id` = `{atom.atom_id}-{mode}-{format}` (예: `CART-C01-S1-02.r1a-M2-TF`). 형식이 다르면 자동 검사에서 탈락합니다.
- `atom_id` = `atom.atom_id`, `atom_statement` = `atom.statement`, `scope` = `atom.scope`
- `card_id`, `cell`, `mode`, `format`은 이 파일의 값 그대로
- `evidence` = `atom.evidence`의 `text`만 뽑은 문자열 리스트
- 정답 형식: TF `True`/`False`, YN `Yes`/`No`, MCQ는 `options`에 A~D 네 개(서로 다름) + `answer`, OPEN은 `key_points` 1~3개
- 나머지(`generated_by`, `model`, `prompt_version`, `generated_at`, `status: "draft"`, `flags: []`)는 기존과 같이

결과는 **`items.regen1.jsonl`** 한 파일로 성하에게 전달해주세요.
