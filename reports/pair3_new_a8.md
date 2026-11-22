# 검수 집계 — store_a8 (표본 ids/pair3_new_a8.ids.txt)

## atom

- 원본 atom 18개, 검수 완료 18개, 미검수(pending) 0개
- **최초 통과율**: 5/18 (27.8%)
- 최초 판정 분포: revise 10, pass 5, hold 2, fail 1
- 자동 수정본 13개 (원본 10개에서): pass 8, hold 4, fail 1
- **수정·재검수 후**: 현재 atom 21개 — pass 13, hold 6, fail 2

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| GROUNDED | 9 | 8 |
| SINGLE_CLAIM | 3 | 2 |
| A_GARBLED | 1 | 1 |
| A_EVIDENCE_LE3 | 1 | 1 |
| SOURCE_INDEPENDENT | 1 | 1 |
| NO_OVERLAP | 1 | 1 |

## 문항

- 검수 완료 17개, 미검수 0개
- **최초 통과율** (문항 자체 판정, atom 상태와 무관): 11/17 (64.7%)
- 최초 판정 분포: pass 11, fail 4, hold 2
- **최종 확보** (atom도 통과한 문항): 4/17 (23.5%) (분모 = 설계 칸)
- 현재 상태: blocked 12, pass 4, fail 1
- atom 때문에 막힌 문항: atom_changed 9, atom_hold 2, atom_fail 1

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| NO_LEAK | 2 | 1 |
| G1_SINGLE_ATOM | 1 | 1 |
| I_GARBLED | 1 | 1 |
| KEY_CORRECT | 1 | 0 |
| KP_IN_ATOM | 1 | 1 |
| YN_CASE_FORMAT | 1 | 1 |
| NO_INTRA_CARD_OVERLAP | 1 | 1 |
| SINGLE_ANSWER | 1 | 0 |

## 호출·비용

| 단계 | 모델(설정 이름) | 호출 | 실패 | 비용(unit) | 응답 모델 |
| --- | --- | --- | --- | --- | --- |
| card | judge_a | 149 | 0 | 3.775 | gpt-6.1-sol |
| card | judge_b | 149 | 0 | 2.856 | gemini-4-argon |
| item | judge_a | 80 | 0 | 2.339 | gpt-6.1-sol |
| item | judge_b | 81 | 1 | 1.915 | gemini-4-argon |
| revise | reviser | 166 | 0 | 0.946 | claude-sonnet-5-5 |

- 검수·수정 비용 합계 11.831 unit, 최종 통과 문항당 2.9579 unit
- 비용은 이 store에 기록된 호출 전체 기준이다 (--only 표본만 따로 나누지 않는다). 생성 비용은 포함하지 않는다.
