# 검수 집계 — store (표본 ids/pair3_old.ids.txt)

## atom

- 원본 atom 27개, 검수 완료 27개, 미검수(pending) 0개
- **최초 통과율**: 7/27 (25.9%)
- 최초 판정 분포: revise 9, pass 7, hold 7, fail 4
- **수정·재검수 후**: 현재 atom 27개 — revise 9, pass 8, hold 5, fail 5

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| SINGLE_CLAIM | 13 | 9 |
| GROUNDED | 12 | 8 |
| A_GARBLED | 7 | 7 |
| SOURCE_INDEPENDENT | 2 | 1 |
| NO_OVERLAP | 2 | 1 |
| A_EVIDENCE_LE3 | 1 | 1 |
| CENTRALITY | 1 | 0 |
| SCOPE_LABEL | 1 | 0 |

## 문항

- 검수 완료 26개, 미검수 0개
- **최초 통과율** (문항 자체 판정, atom 상태와 무관): 16/26 (61.5%)
- 최초 판정 분포: pass 16, fail 6, hold 4
- **최종 확보** (atom도 통과한 문항): 7/26 (26.9%) (분모 = 설계 칸)
- 현재 상태: blocked 18, pass 7, fail 1
- atom 때문에 막힌 문항: atom_revise 8, atom_hold 5, atom_fail 5

| 체크 | 한 저지 이상 비통과 | 두 저지 모두 비통과 |
| --- | --- | --- |
| I_GARBLED | 7 | 7 |
| NO_INTRA_CARD_OVERLAP | 4 | 3 |
| NO_LEAK | 3 | 3 |
| YN_CASE_FORMAT | 3 | 2 |
| SINGLE_ANSWER | 3 | 0 |
| G1_SINGLE_ATOM | 3 | 1 |
| KEY_CORRECT | 3 | 1 |
| ONE_ELEMENT_CHANGE | 1 | 1 |
| G2_NO_COMPUTATION | 1 | 0 |

## 호출·비용

| 단계 | 모델(설정 이름) | 호출 | 실패 | 비용(unit) | 응답 모델 |
| --- | --- | --- | --- | --- | --- |
| card | judge_a | 84 | 0 | 0.783 | gpt-6.1-sol |
| card | judge_b | 87 | 3 | 0.553 | gemini-4-argon |
| item | judge_a | 77 | 0 | 0.809 | gpt-6.1-sol |
| item | judge_b | 83 | 6 | 0.639 | gemini-4-argon |

- 검수·수정 비용 합계 2.785 unit, 최종 통과 문항당 0.3978 unit
- 비용은 이 store에 기록된 호출 전체 기준이다 (--only 표본만 따로 나누지 않는다). 생성 비용은 포함하지 않는다.
