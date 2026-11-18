# 보정 세트 라벨링 기준

저지 모델을 고르기 위한 사람 기준표를 만드는 작업이다. 두 사람이 **서로 상의하지 않고** 각자 채운다.

## 방법

1. `calib_card.csv`(atom 120개), `calib_item.csv`(문항 120개)를 각자 복사해서 연다.
2. 행마다 `content`를 읽고 `human_v`에 아래 값 중 하나를 쓴다. 통과가 아니면 `human_note`에 걸린 항목 이름을 적는다.
3. 다른 열은 고치지 않는다 (`unit_hash`가 바뀌면 적재되지 않는다).
4. 끝나면 `python run.py human import --file <파일> --reviewer <이름>`.

시간이 부족하면 위에서부터 60행만 채워도 된다. 순서가 섞여 있어 책과 유형이 고르게 들어간다.
두 사람의 판정이 갈린 행은 기준표에서 빠진다. 나중에 합의해서 다시 넣을 수 있다.

## 판정값

| 값 | 뜻 |
| --- | --- |
| pass | 아래 항목 전부 문제없음 |
| revise | 고치면 살릴 수 있음 (atom만 해당) |
| fail | 버려야 함 |
| hold | 판단할 수 없음 (수식이 깨져 근거를 읽을 수 없음 등). 기준표에서 제외된다 |

확신이 없으면 pass 대신 revise나 fail을 고르고 이유를 적는다.

## atom (calib_card.csv)

`content`에는 [개념] (S 라벨) atom 문장과 근거 원문이 있다. 근거 원문만 보고 판단하고, 자기 지식으로 채워 주지 않는다.

| 항목 | 물음 | 걸리면 |
| --- | --- | --- |
| GROUNDED | 근거 문장이 atom을 그대로 말하는가 | 일부만 맞음, 덧붙임·강화 → revise / 근거에 없음 → fail |
| SINGLE_CLAIM | 주장이 하나인가 (따로 참·거짓이 갈릴 수 있는 주장이 둘 이상 묶이지 않았는가) | revise |
| SCOPE_LABEL | S1 무엇인가 / S2 어떻게 작동하나 / S3 어디까지 성립하나 라벨이 맞는가 | revise |
| L1_ONLY | 아는지 묻는 수준인가 (새 문제에 적용하거나 먼 사실을 결합해야 하지 않는가) | fail |
| SOURCE_INDEPENDENT | 이 책을 안 읽은 전문가도 참·거짓을 가릴 수 있는가 | 출처 표현만 떼면 됨 → revise / 저자 의견·단일 연구 결과 → fail |

예: "the authors propose …", "In this study, X was observed in mice" 같은 문장은 SOURCE_INDEPENDENT를 의심한다.

같은 카드의 다른 atom과 겹치는지(NO_OVERLAP)는 이 파일만으로는 볼 수 없으므로 판정하지 않는다.

## 문항 (calib_item.csv)

`content`에는 문제, 정답(또는 key_points), 대응 atom이 있다. atom을 정답 기준으로 삼는다. 문항은 revise 없이 pass / fail만 쓴다.

| 항목 | 물음 |
| --- | --- |
| G1_SINGLE_ATOM | 이 atom 하나만으로 정답이 나오는가 |
| G2_NO_COMPUTATION | 계산, 증명, 여러 사실의 결합이 필요 없는가 |
| KEY_CORRECT | 정답이 atom과 맞는가. False·No 문항은 문제 내용이 실제로 atom과 어긋나는가 |
| SINGLE_ANSWER | 정답이 하나뿐인가 (다른 보기나 라벨도 맞을 수 있으면 fail) |
| NO_LEAK | 문제가 답을 알려 주지 않는가. TF는 진술 자체가 평가 대상이라 atom의 재서술이어도 된다 |
| KP_IN_ATOM | (OPEN) key_points가 전부 atom 안에 있는가 |
| YN_CASE_FORMAT | (YN) 구체적인 사례를 주고 "이 사례가 해당하는가"를 묻는가. "이 주장·견해가 맞는가"를 물으면 fail |
| ONE_ELEMENT_CHANGE | (TF False, MCQ) 틀린 진술·오답이 정답에서 한 요소만 바꿨는가 |
| NO_SOURCE_REF | 책, 저자, "according to the text" 같은 출처 표현이 없는가 |
| AUTHOR_OPINION_RESOLVED | atom이 저자 의견·단일 연구 결과인데 보편 사실처럼 묻지 않았는가 |

하나라도 걸리면 fail이고, `human_note`에 항목 이름을 적는다 (예: `YN_CASE_FORMAT`).
