# 검수 집계 — store_b7 (표본 ids\b7_regen1.ids.txt)

## atom

- 원본 atom 0개, 검수 완료 0개, 미검수(pending) 0개
- **최초 통과율**: 0/0
- 최초 판정 분포: 
- **수정·재검수 후**: 현재 atom 0개 — 

## 문항

- 검수 완료 178개, 미검수 0개
- **최초 통과율** (문항 자체 판정, atom 상태와 무관): 113/178 (63.5%)
- 최초 판정 분포: pass 113, fail 39, hold 26
- **최종 확보** (atom도 통과한 문항): 113/178 (63.5%) (분모 = 설계 칸)
- 현재 상태: pass 113, fail 39, hold 26

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| G1_SINGLE_ATOM | 13 | 4 |
| YN_CASE_FORMAT | 13 | 11 |
| ONE_ELEMENT_CHANGE | 12 | 8 |
| KP_IN_ATOM | 11 | 8 |
| NO_LEAK | 11 | 6 |
| KEY_CORRECT | 8 | 5 |
| SINGLE_ANSWER | 7 | 2 |
| G2_NO_COMPUTATION | 7 | 1 |
| AUTHOR_OPINION_RESOLVED | 3 | 0 |
| NO_INTRA_CARD_OVERLAP | 2 | 0 |

## 호출·비용

| 단계 | 모델(설정 이름) | 호출 | 실패 | 비용(unit) | 응답 모델 |
| --- | --- | --- | --- | --- | --- |
| answer | judge_a | 46 | 0 | 0.154 | gpt-6.1-sol |
| answer | judge_b | 69 | 0 | 0.206 | gemini-4-argon |
| answer | judge_c | 23 | 0 | 0.107 | claude-sonnet-5-5 |
| card | judge_a | 136 | 0 | 3.944 | gpt-6.1-sol |
| card | judge_b | 136 | 0 | 2.967 | gemini-4-argon |
| item | judge_a | 133 | 1 | 2.736 | gpt-6.1-sol |
| item | judge_b | 132 | 0 | 2.169 | gemini-4-argon |
| revise | reviser | 194 | 0 | 1.357 | claude-sonnet-5-5 |

- 검수·수정 비용 합계 13.640 unit, 최종 통과 문항당 0.1207 unit
- 비용은 이 store에 기록된 호출 전체 기준이다 (--only 표본만 따로 나누지 않는다). 생성 비용은 포함하지 않는다.
