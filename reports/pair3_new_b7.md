# 검수 집계 — store_b7 (표본 ids/pair3_new_b7.ids.txt)

## atom

- 원본 atom 9개, 검수 완료 9개, 미검수(pending) 0개
- **최초 통과율**: 0/9 (0.0%)
- 최초 판정 분포: hold 6, fail 2, revise 1
- 자동 수정본 2개 (원본 1개에서): pass 2
- **수정·재검수 후**: 현재 atom 10개 — hold 6, fail 2, pass 2

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| GROUNDED | 7 | 4 |
| A_EVIDENCE_LE3 | 5 | 5 |
| SINGLE_CLAIM | 2 | 1 |
| SCOPE_LABEL | 2 | 1 |
| NO_OVERLAP | 1 | 1 |
| SOURCE_INDEPENDENT | 1 | 0 |

## 문항

- 검수 완료 9개, 미검수 0개
- **최초 통과율** (문항 자체 판정, atom 상태와 무관): 7/9 (77.8%)
- 최초 판정 분포: pass 7, fail 2
- **최종 확보** (atom도 통과한 문항): 0/9 (0.0%) (분모 = 설계 칸)
- 현재 상태: blocked 9
- atom 때문에 막힌 문항: atom_hold 6, atom_fail 2, atom_changed 1

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| NO_INTRA_CARD_OVERLAP | 1 | 1 |
| SINGLE_ANSWER | 1 | 0 |
| ONE_ELEMENT_CHANGE | 1 | 1 |

## 호출·비용

| 단계 | 모델(설정 이름) | 호출 | 실패 | 비용(unit) | 응답 모델 |
| --- | --- | --- | --- | --- | --- |
| card | judge_a | 136 | 0 | 3.944 | gpt-6.1-sol |
| card | judge_b | 136 | 0 | 2.967 | gemini-4-argon |
| item | judge_a | 70 | 1 | 2.018 | gpt-6.1-sol |
| item | judge_b | 70 | 0 | 1.610 | gemini-4-argon |
| revise | reviser | 194 | 0 | 1.357 | claude-sonnet-5-5 |

- 검수·수정 비용 합계 11.896 unit
- 비용은 이 store에 기록된 호출 전체 기준이다 (--only 표본만 따로 나누지 않는다). 생성 비용은 포함하지 않는다.
