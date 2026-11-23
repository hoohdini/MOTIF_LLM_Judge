# 답변 수집·채점 파일럿

승인된 문항을 모델에게 풀게 하고 채점까지 한 바퀴 돌려 보는 시험 실행이다. 문항 풀이 확정 전이라 여기서 나온 정답률은 벤치마크 수치가 아니다.

- 대상 문항: 각 store의 현재 승인본(`releases/CURRENT`)의 `items_approved.jsonl`
- 기본 응시 모델: `claude-haiku-5-5`, `gpt-6.1-terra`, `deepseek-v4-flash` (`--models`로 바꾼다)
- 응시자에게는 질문과 보기만 보낸다. 형식별로 답 형식을 한 줄 붙인다 (True/False, Yes/No, A~D 한 글자, 1~3문장).
- TF·YN·MCQ는 코드가 채점하고, OPEN은 저지 2개가 key point별로 대조한다 (응시 모델과 같은 계열 저지는 빼고 고른다).
- 채점 프롬프트는 회의 #4 수정본 (`prompts/answer_judge.v2.md`).

## A묶음 (책당 6문항 표본)

```bash
python collect_answers.py --store store_a8 --per-book 6
python run.py --store store_a8 ingest answers answers/store_a8/answers.jsonl --label "파일럿 책당6"
python run.py --store store_a8 run --stage answer --workers 4
python run.py --store store_a8 decide --stage answer
python analysis/answer_report.py --store store_a8 --out reports/answers_a8.md
```

## B묶음

```bash
python collect_answers.py --store store_b7 --per-book 6
python run.py --store store_b7 ingest answers answers/store_b7/answers.jsonl --label "파일럿 책당6"
python run.py --store store_b7 run --stage answer --workers 4
python run.py --store store_b7 decide --stage answer
python analysis/answer_report.py --store store_b7 --out reports/answers_b7.md
```

승인 문항 전체로 넓히려면 `--per-book 6`을 빼고 같은 순서로 다시 실행한다. 이미 받은 답변과 판정은 건너뛴다.
