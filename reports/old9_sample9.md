# 검수 집계 — store (표본 ids/old9_sample9.ids.txt)

## atom

- 원본 atom 81개, 검수 완료 81개, 미검수(pending) 0개
- **최초 통과율**: 15/81 (18.5%)
- 최초 판정 분포: fail 25, hold 21, revise 20, pass 15
- **수정·재검수 후**: 현재 atom 81개 — fail 26, revise 21, pass 18, hold 16

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| SINGLE_CLAIM | 41 | 24 |
| GROUNDED | 41 | 34 |
| SOURCE_INDEPENDENT | 23 | 18 |
| A_GARBLED | 16 | 16 |
| A_ATTRIBUTION | 11 | 11 |
| A_EVIDENCE_LE3 | 8 | 8 |
| SCOPE_LABEL | 7 | 3 |
| NO_OVERLAP | 5 | 2 |
| CENTRALITY | 3 | 1 |

## 문항

- 검수 완료 79개, 미검수 0개
- **최초 통과율** (문항 자체 판정, atom 상태와 무관): 35/79 (44.3%)
- 최초 판정 분포: pass 35, fail 33, hold 11
- **최종 확보** (atom도 통과한 문항): 13/79 (16.5%) (분모 = 설계 칸)
- 현재 상태: blocked 61, pass 13, fail 3, hold 2
- atom 때문에 막힌 문항: atom_fail 25, atom_revise 20, atom_hold 16

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| AUTHOR_OPINION_RESOLVED | 17 | 14 |
| I_GARBLED | 16 | 16 |
| NO_LEAK | 13 | 8 |
| NO_INTRA_CARD_OVERLAP | 11 | 9 |
| ONE_ELEMENT_CHANGE | 9 | 7 |
| KEY_CORRECT | 9 | 4 |
| YN_CASE_FORMAT | 8 | 7 |
| G1_SINGLE_ATOM | 8 | 3 |
| SINGLE_ANSWER | 7 | 0 |
| G2_NO_COMPUTATION | 6 | 0 |
| KP_IN_ATOM | 3 | 3 |
| NO_SOURCE_REF | 2 | 1 |

## 호출·비용

| 단계 | 모델(설정 이름) | 호출 | 실패 | 비용(unit) | 응답 모델 |
| --- | --- | --- | --- | --- | --- |
| card | judge_a | 84 | 0 | 0.783 | gpt-6.1-sol |
| card | judge_b | 87 | 3 | 0.553 | gemini-4-argon |
| item | judge_a | 77 | 0 | 0.809 | gpt-6.1-sol |
| item | judge_b | 83 | 6 | 0.639 | gemini-4-argon |

- 검수·수정 비용 합계 2.785 unit, 최종 통과 문항당 0.2142 unit
- 비용은 이 store에 기록된 호출 전체 기준이다 (--only 표본만 따로 나누지 않는다). 생성 비용은 포함하지 않는다.
