# 검수 집계 — store_a8 (표본 ids\a8_regen1.ids.txt)

## atom

- 원본 atom 0개, 검수 완료 0개, 미검수(pending) 0개
- **최초 통과율**: 0/0
- 최초 판정 분포: 
- **수정·재검수 후**: 현재 atom 0개 — 

## 문항

- 검수 완료 174개, 미검수 0개
- **최초 통과율** (문항 자체 판정, atom 상태와 무관): 118/174 (67.8%)
- 최초 판정 분포: pass 118, fail 33, hold 23
- **최종 확보** (atom도 통과한 문항): 118/174 (67.8%) (분모 = 설계 칸)
- 현재 상태: pass 118, fail 33, hold 23

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| NO_LEAK | 15 | 8 |
| ONE_ELEMENT_CHANGE | 14 | 10 |
| G1_SINGLE_ATOM | 13 | 8 |
| KEY_CORRECT | 12 | 7 |
| G2_NO_COMPUTATION | 9 | 2 |
| YN_CASE_FORMAT | 7 | 2 |
| SINGLE_ANSWER | 6 | 1 |
| NO_INTRA_CARD_OVERLAP | 4 | 2 |
| I_GARBLED | 3 | 3 |
| KP_IN_ATOM | 3 | 3 |
| AUTHOR_OPINION_RESOLVED | 2 | 0 |

## 호출·비용

| 단계 | 모델(설정 이름) | 호출 | 실패 | 비용(unit) | 응답 모델 |
| --- | --- | --- | --- | --- | --- |
| answer | judge_a | 50 | 0 | 0.162 | gpt-6.1-sol |
| answer | judge_b | 75 | 0 | 0.227 | gemini-4-argon |
| answer | judge_c | 25 | 0 | 0.111 | claude-sonnet-5-5 |
| card | judge_a | 149 | 0 | 3.775 | gpt-6.1-sol |
| card | judge_b | 149 | 0 | 2.856 | gemini-4-argon |
| item | judge_a | 145 | 0 | 3.013 | gpt-6.1-sol |
| item | judge_b | 146 | 1 | 2.478 | gemini-4-argon |
| revise | reviser | 166 | 0 | 0.946 | claude-sonnet-5-5 |

- 검수·수정 비용 합계 13.568 unit, 최종 통과 문항당 0.1150 unit
- 비용은 이 store에 기록된 호출 전체 기준이다 (--only 표본만 따로 나누지 않는다). 생성 비용은 포함하지 않는다.
